# AI Task Management Platform

Task management platform with an AI intake pipeline.

Current implementation snapshot: extraction is asynchronous and persists both `TaskCandidate` rows and linked `Task` rows during the extraction workflow. The review queue still captures human decisions (`approve` / `reject` / `edit`) and feedback signals.

## What this project does

- Core task management (CRUD, assignee updates, dependencies, labels, archive/unarchive)
- Authenticated multi-tenant hierarchy (`Organization` → `Workspace` → `Project`)
- AI extraction from unstructured sources (`text`, `url`, `email`) via queued jobs
- Assignee recommendations attached to extracted candidates
- Human review queue with batch actions, undo reject window, and provenance timeline
- Feedback analytics, task activity history, and webhook subscriptions
- Optional memory integration (MemPalace) and an external MCP adapter

## Architecture at a glance

Two layers are kept separate:

1. **Core platform layer** — reliable source of record for tasks/workspaces/projects/people
2. **AI layer** — extraction + recommendation + enrichment

AI failures should not take down core CRUD behavior.

## AI pipeline (current behavior)

```text
Source Content (text/url/email)
      |
      v
POST /api/ai/extract-tasks
      |
      v
Job queued (in-memory store)
      |
      v
Agent loop tools:
  1) get_assignee_skills
  2) create_tasks                -> persists Source + TaskCandidates + Tasks + TaskSource links
  3) recommend_assignees         -> updates candidate recommendations (+ linked task assignee)
  4) finalize_extraction
      |
      v
GET /api/ai/jobs/{job_id}
      |
      v
Review queue actions (approve/edit/reject/undo/batch)
```

Notes:

- Job lifecycle: `queued` → `running` → `done|failed`
- Dead-letter support exists with retry endpoints
- Candidate review state is tracked separately from task creation

## Core principles

- Schema-validated AI outputs
- Traceability from source → candidate revisions → approval events → task provenance
- Fail-open behavior around optional memory retrieval
- API-first design with explicit auth and role checks

## Tech stack

- **Backend:** FastAPI, SQLAlchemy, Alembic, PostgreSQL
- **Frontend:** React 19, Vite, TanStack Query, Tailwind CSS
- **AI providers:** Gemini (`google-genai`) and OpenAI-compatible (`openai`)
- **Infra:** Docker Compose (dev), PM2 option for non-container Linux deploys

## Project structure

```text
backend/
  app/
    ai/agent_extraction/    # autonomous extraction agent + tools + policies
    jobs/                   # async extraction + memory ingestion jobs
    routers/                # API routes
    services/               # extraction/memory/webhook/provenance services
    models.py               # SQLAlchemy models
    schemas.py              # Pydantic schemas
  alembic/                  # DB migrations
  scripts/seed.py           # demo seed data

frontend/
  src/
    pages/                  # app screens
    hooks/                  # API hooks
    api/                    # typed API clients
    components/             # reusable UI

integrations/mcp/
  task_mngt_server.py       # standalone MCP adapter over REST API
```

## Quick start (Docker)

### 1) Configure environment

```bash
cp backend/.env.example backend/.env
```

Set required values in `backend/.env`:

- `GEMINI_API_KEY` when `AI_AGENT_PROVIDER=gemini` (default)
- or `OPENAI_API_KEY` when `AI_AGENT_PROVIDER=openai`

### 2) Start services

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5433`

### 3) Optional seed data

```bash
docker compose exec api python scripts/seed.py
```

## Local development (without Docker)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# required for local backend startup
export DATABASE_URL='postgresql://app:password@localhost:5433/taskmanagement'

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

By default Vite proxies `/api` to `http://localhost:8000`.

## API overview

### Auth & session

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Workspaces, projects, people

- `POST /api/workspaces`, `GET /api/workspaces`
- `GET /api/workspaces/{workspace_id}/projects`, `POST /api/workspaces/{workspace_id}/projects`
- `GET /api/workspaces/{workspace_id}/labels`, `POST /api/workspaces/{workspace_id}/labels`
- `POST /api/people`, `GET /api/people`, `PUT /api/people/{person_id}`, `DELETE /api/people/{person_id}`

### Tasks

- `POST /api/tasks`, `GET /api/tasks`, `GET /api/tasks/{task_id}`
- `PUT /api/tasks/{task_id}`, `PATCH /api/tasks/{task_id}`, `DELETE /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/archive`, `POST /api/tasks/{task_id}/unarchive`
- `GET /api/tasks/{task_id}/activity`, `GET /api/tasks/{task_id}/status-history`
- `POST /api/tasks/{task_id}/dependencies`
- `GET /api/tasks/{task_id}/assignee-recommendations`
- `GET /api/tasks/{task_id}/sources`, `GET /api/tasks/{task_id}/provenance`

### AI extraction jobs

- `POST /api/ai/extract-tasks`
- `GET /api/ai/jobs/{job_id}`
- `GET /api/ai/jobs/{job_id}/events`
- `GET /api/ai/jobs/{job_id}/events/stream`
- `GET /api/ai/jobs/{job_id}/dead-letter`
- `POST /api/ai/jobs/{job_id}/dead-letter/retry`

### Task candidates (review queue)

- `GET /api/task-candidates?project_id=...&status=pending`
- `PATCH /api/task-candidates/{candidate_id}`
- `POST /api/task-candidates/{candidate_id}/approve`
- `POST /api/task-candidates/{candidate_id}/reject`
- `POST /api/task-candidates/{candidate_id}/undo-reject`
- `POST /api/task-candidates/batch-approve`
- `POST /api/task-candidates/batch-reject`
- `GET /api/task-candidates/{candidate_id}/provenance`

### Analytics, webhooks, health

- `GET /api/feedback-analytics?project_id=...&period=day|week|month`
- `GET /api/projects/{project_id}/forecast`
- `GET /api/projects/{project_id}/sources`
- `POST /api/webhooks?workspace_id=...`, `GET /api/webhooks?workspace_id=...`
- `PATCH /api/webhooks/{subscription_id}`, `DELETE /api/webhooks/{subscription_id}`
- `GET /api/webhooks/{subscription_id}/deliveries`, `POST /api/webhooks/{subscription_id}/test`
- `GET /api/health`

## Operational notes

- Extraction job and dead-letter stores are in-memory (`backend/app/jobs/store.py`) and have TTL-based eviction.
- Reject undo window is currently `5` seconds.
- Memory integration is optional (`MEMORY_ENABLED=false` by default).
- For Linux non-Docker deployment, see `deployment_guide.md`.
