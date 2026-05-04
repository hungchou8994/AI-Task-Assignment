# AI Pipeline

## Overview

The AI pipeline is the core differentiator of this platform. It transforms unstructured inputs (emails, URLs, plain text) into structured tasks using an autonomous agent loop, with full streaming, resilience, and human review support.

## Pipeline Stages

```
Input (text / URL / email)
        ↓
   [Preprocessor]           Normalize, fetch URL content, parse email headers
        ↓
   [Agent Runner]           Autonomous think → act → observe loop
        │
        ├── get_assignee_skills      Query team member skills
        ├── create_tasks             Write Source + Candidate + Task to DB
        ├── recommend_assignees      Score and rank assignees per task
        └── finalize_extraction      Build and return ExtractionResult
        ↓
   [ExtractionResult]        Structured list of tasks + assignee recommendations
        ↓
   [Review Queue]            Human approves / edits / rejects each candidate
        ↓
   [Task]                    Promoted to a real task in the project
```

## Component Breakdown

### Preprocessor (`backend/app/ai/preprocessor.py`)

Normalizes input before it reaches the agent:
- **Text:** whitespace normalization
- **URL:** fetches page content via `httpx`, strips HTML
- **Email:** extracts subject, sender, body; strips threading/quoted sections

### Agent Framework (`backend/app/ai/agent/`)

A custom, provider-agnostic agent framework inspired by the OpenAI Agents SDK.

#### Core Components

| Component | File | Responsibility |
|---|---|---|
| `Agent` | `agent.py` | Pure config object: name, instructions, tools, model, iteration limits |
| `Runner` | `runner.py` | Owns the think→act→observe loop; streaming and non-streaming paths |
| `Tool` / `@tool` | `tools.py` | Decorator that auto-generates JSON Schema from type hints and docstrings |
| `RunContext[T]` | `run_context.py` | Type-safe dependency injection into tool functions |
| `ToolLoopDetector` | `runner.py` | Detects infinite tool call loops, nudges the model to break out |
| `JobEventEmitter` | `event_emitter.py` | Pushes SSE events to the in-memory event store |
| `GeminiModel` | `models/gemini.py` | Gemini API adapter |
| `OpenAIModel` | `models/openai.py` | OpenAI-compatible API adapter |

#### Agent Loop

```
Runner.run(agent, input, context, event_emitter)
    │
    ├─ [iteration 1]
    │       ↓ model.generate(messages)
    │       ↓ parse tool_call from response
    │       ↓ execute tool(context, **args)
    │       ↓ append tool_result to messages
    │
    ├─ [iteration 2..N]  (same pattern)
    │
    └─ [stop condition]
            - tool sets context.finalized = True  (normal exit)
            - max_iterations reached              (safety exit: default 20)
            - max_context_turns reached           (safety exit: default 28)
```

Every step emits SSE events consumed by the frontend's `AgentLoopTimeline` component.

### Extraction Agent (`backend/app/ai/agent_extraction/`)

The concrete agent configured for task extraction.

#### System Prompt

Built dynamically by `prompts.py` and injected with two **skill files**:

| Skill | File | Purpose |
|---|---|---|
| Extraction Policy | `skills/extraction_policy.md` | 4-step workflow the agent must follow, output language rules, tool call constraints |
| Assignee Policy | `skills/assignee_policy.md` | How to score and rank assignees: skill match, availability, load |

#### 4 Extraction Tools (`tools.py`)

**1. `get_assignee_skills`**
- Queries the `people` table for the current workspace
- Returns up to 50 people with their `role`, `skills` (text field), and `availability`
- Used by the agent in step 1 to understand the team before creating tasks

**2. `create_tasks`**
- Input: list of `TaskInput` objects (title, description, priority, due_date, estimated_hours, assignee_hint, source_spans)
- Validates with Pydantic
- Idempotently creates records in one DB transaction:
  - `Source` (content_hash + project_id + source_type deduplication)
  - `TaskCandidate` (pending review)
  - `Task` (immediately visible in task list)
  - `TaskSource` (links task to its source)
  - `TaskCandidateRevision` (initial revision for audit trail)
- Auto-commits the transaction
- Returns created task IDs for use in subsequent tool calls

**3. `recommend_assignees`**
- Input: list of `{ task_id, assignee_recommendations: [{ person_id, confidence, reasoning }] }`
- Updates `TaskCandidate.assignee_recommendations` (JSONB column)
- Auto-applies the top recommendation to `Task.assignee_id` if confidence ≥ `AI_ASSIGNEE_AUTO_APPLY_CONFIDENCE_THRESHOLD` (default: 0.8)

**4. `finalize_extraction`**
- Builds the final `ExtractionResult` summary
- Two paths:
  - **Persisted path:** reads fresh data from DB (used when `create_tasks` was called)
  - **Direct path:** uses data provided directly in args (fallback when no tasks were created)
- Sets `deps.finalized = True` which signals the Runner to exit the loop

### Extraction Service (`backend/app/services/extraction_service.py`)

Public API consumed by the AI router:

```python
result = await extract_tasks(db, ExtractionCommand(
    content=...,
    content_type="text" | "url" | "email",
    project_id=...,
    workspace_id=...,
    submitted_by=...
))
```

Orchestrates: preprocess → agent run → result wrapping.

### Job Infrastructure (`backend/app/jobs/`)

Because extraction can take 30–180 seconds, it runs as a **background job**.

#### Flow

```
POST /api/ai/extract
    → ExtractionJob created (state: pending)
    → Background thread started (run_extraction_job)
    → Response: { job_id }

GET /api/ai/jobs/{job_id}
    → Returns job state: pending | running | completed | failed

GET /api/ai/jobs/{job_id}/events
    → SSE stream of agent events emitted in real-time
```

#### Job Store (`jobs/store.py`)

- In-memory dictionary keyed by `job_id`
- TTL eviction (configurable, default varies per job type)
- Stores: job metadata, state, result, error, and the SSE event log
- **Dead-letter queue:** failed jobs are kept separately with their own TTL

#### Resilience in `extraction_job.py`

| Feature | Config variable | Default |
|---|---|---|
| Max retry attempts | `AI_EXTRACTION_JOB_MAX_ATTEMPTS` | 3 |
| Per-attempt timeout | `AI_EXTRACTION_JOB_TIMEOUT_SECONDS` | 180s |
| Retry backoff | `AI_EXTRACTION_JOB_RETRY_BACKOFF_SECONDS` × 2^attempt | — |
| Circuit breaker failures | `AI_EXTRACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 4 |
| Circuit breaker cooldown | `AI_EXTRACTION_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | 120s |
| Dead-letter TTL | `AI_EXTRACTION_DEAD_LETTER_TTL_SECONDS` | 86400s (24h) |

**Retry endpoint for dead-letter jobs:**
```
POST /api/ai/jobs/{job_id}/dead-letter/retry
```

## AI Provider Configuration

The platform supports two AI providers via a common adapter interface:

| Provider | Config | Default model |
|---|---|---|
| Google Gemini | `AI_AGENT_PROVIDER=gemini`, `GEMINI_API_KEY` | `gemini-2.5-flash-lite` |
| OpenAI-compatible | `AI_AGENT_PROVIDER=openai`, `OPENAI_API_KEY` | `gpt-4o-mini` |

Switch providers by changing `AI_AGENT_PROVIDER` in the backend `.env`.

## Traceability Model

Every AI decision is fully traceable:

```
Source (raw input document)
  └── TaskCandidate (AI-extracted, pending review)
        ├── CandidateSourceSpan (character offsets in source)
        ├── TaskCandidateRevision (every edit to the candidate)
        └── CandidateApprovalEvent (approve / reject / undo)
              └── Task (promoted on approval)
                    └── FeedbackEvent (human review decision)
```

This enables:
- Highlighting exactly which sentence in the source produced a given task
- A full audit log of every human edit and decision
- Feedback analytics to measure AI accuracy over time

## Optional: MemPalace Integration

When `MEMORY_ENABLED=true`, the platform integrates with **MemPalace** for persistent memory:
- `memory_service.py` — stores and retrieves contextual memories
- `memory_context_builder.py` — builds context from memory for prompts
- `memory_policy.py` — governs what gets stored
- `memory_ingestion_job.py` — background job for memory ingestion
- `memory_audit_service.py` — audit trail for memory operations

Memory failures are always handled gracefully (fail-open); they never block extraction.
