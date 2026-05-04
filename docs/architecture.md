# System Architecture

## High-Level Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                   FRONTEND  (React 19 + Vite)                        │
│   Port 3000 (Docker) / 3003 (PM2)                                    │
│                                                                      │
│   Pages: Dashboard · Tasks · ReviewQueue · AIAnalysis                │
│          Sources · Team · Webhooks · Documentation · Auth            │
│                                                                      │
│   State: TanStack Query · React Contexts · react-hook-form           │
│   UI:    shadcn/ui (Radix UI + Tailwind CSS)                         │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  HTTP /api/*  (proxy in dev, direct in prod)
                         │  SSE  /api/ai/jobs/{id}/events
┌────────────────────────▼─────────────────────────────────────────────┐
│                   BACKEND  (FastAPI + Python)                         │
│   Port 8000 (Docker) / 8003 (PM2)                                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  API ROUTERS                                                  │   │
│  │  auth · tasks · people · workspaces · projects               │   │
│  │  task_candidates · ai · feedback_analytics                   │   │
│  │  task_activity · webhooks · health                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  CORE PLATFORM LAYER                                          │   │
│  │  Tasks · Projects · Workspaces · People · Labels             │   │
│  │  Webhooks · Feedback Analytics · Activity · Status History   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AI PIPELINE LAYER                                            │   │
│  │                                                               │   │
│  │  ExtractionService                                            │   │
│  │       ↓                                                       │   │
│  │  Preprocessor  →  Agent Runner (think → act → observe)       │   │
│  │                        ↓ tools                               │   │
│  │                   get_assignee_skills                         │   │
│  │                   create_tasks                                │   │
│  │                   recommend_assignees                         │   │
│  │                   finalize_extraction                         │   │
│  │                                                               │   │
│  │  Background Job Store  (in-memory, TTL eviction)             │   │
│  │  Circuit Breaker · Retry · Dead-Letter Queue                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  OPTIONAL: MemPalace memory integration                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────────┐
│                   PostgreSQL 16                                       │
│   Port 5433 (Docker)  /  standard 5432 (bare-metal)                  │
│   14 Alembic migrations                                              │
└──────────────────────────────────────────────────────────────────────┘
```

## Multi-Tenant Data Hierarchy

```
Organization
  ├── OrgMembership  (owner / admin / member)
  └── Workspace
        ├── WorkspaceMembership  (owner / admin / manager / member / viewer)
        ├── Labels
        ├── WebhookSubscriptions
        └── Project
              ├── Task
              │     ├── Labels
              │     ├── Dependencies
              │     ├── TaskEstimate
              │     ├── TaskSource  (→ Source)
              │     └── TaskActivityEvent / TaskStatusHistory
              └── TaskCandidate  (AI-generated, pending review)
                    ├── TaskCandidateRevision
                    ├── CandidateSourceSpan
                    └── CandidateApprovalEvent
```

## Backend Directory Structure

```
backend/
└── app/
    ├── main.py                 # FastAPI app, middleware, router registration
    ├── config.py               # Pydantic-Settings (all env vars, @lru_cache)
    ├── models.py               # SQLAlchemy ORM models (~887 lines)
    ├── schemas.py              # Pydantic request/response schemas
    ├── database.py             # DB session factory
    ├── dependencies.py         # FastAPI dependency injectors
    ├── auth.py / auth_utils.py # Auth helpers
    ├── errors.py               # Custom error handling
    ├── serialization.py        # Response serialization helpers
    ├── routers/                # 12 router files (one per domain)
    ├── ai/                     # AI layer (see ai-pipeline.md)
    ├── jobs/                   # Background job infrastructure
    └── services/               # Business logic (orchestration)
```

## Frontend Directory Structure

```
frontend/src/
├── main.tsx            # App bootstrap + provider tree
├── routes.tsx          # React Router route definitions
├── types.ts            # All TypeScript interfaces (single source of truth)
├── index.css           # Global styles
├── pages/              # 12 page-level components
├── components/         # Reusable UI components + shadcn/ui primitives
├── hooks/              # ~20 TanStack Query data hooks
├── api/                # Typed API client modules (8 modules)
├── context/            # React contexts (Auth, Workspace, Theme, Sidebar, Project, Language)
├── i18n/               # Translation files (English + Japanese)
├── lib/                # Utilities (api.ts, taskFormatters, decodeEscapedText)
└── constants/          # Shared constants
```

## Request Lifecycle

### Standard REST Request
```
Browser
  → [React component calls hook]
  → [TanStack Query fires API fn]
  → [api/client.ts fetch()]
  → [FastAPI router handler]
  → [dependency injectors: db, current_user, workspace_member]
  → [service / direct ORM query]
  → [SQLAlchemy → PostgreSQL]
  → [serialized Pydantic response]
  → [TanStack Query cache update]
  → [React re-render]
```

### AI Extraction Request
```
Browser (AIAnalysisPage)
  → POST /api/ai/extract   { content, content_type, project_id }
  → ExtractionJob queued (background thread)
  → Response: { job_id }
  
Browser opens SSE stream:
  → GET /api/ai/jobs/{job_id}/events
  → Agent emits: thinking_delta · text_delta · tool_call · tool_result · finalized
  → Frontend AgentLoopTimeline renders live
  
Browser polls job status:
  → GET /api/ai/jobs/{job_id}
  → Returns: pending | running | completed | failed
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| In-memory job store | Simplicity; extraction jobs are ephemeral and do not need to survive restarts |
| Fail-open AI layer | AI failures never crash core CRUD; circuit breaker prevents cascading failures |
| Traceability by design | Source → Revision → SourceSpan → ApprovalEvent → Task provides a full audit trail |
| Idempotent extraction | `content_hash + project_id + source_type` prevents duplicate task creation |
| SSE for agent streaming | Lightweight, HTTP-native; avoids WebSocket complexity for one-way event push |
| Bilingual UI | English + Japanese i18n from the start; browser language auto-detection |
