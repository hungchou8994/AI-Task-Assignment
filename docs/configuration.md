# Configuration

All backend configuration is managed through environment variables loaded via **Pydantic-Settings** (`backend/app/config.py`). The settings object is cached with `@lru_cache`, so it is instantiated once per process.

Copy `backend/.env.example` to `backend/.env` and fill in the required values before starting the server.

---

## Required Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string. Example: `postgresql://user:pass@localhost:5432/tgl_tasks` |
| `SESSION_SECRET_KEY` | Secret used to sign session cookies. **Must be changed in production.** Use a long random string. |
| `GEMINI_API_KEY` | Required when `AI_AGENT_PROVIDER=gemini` (the default) |
| `OPENAI_API_KEY` | Required when `AI_AGENT_PROVIDER=openai` |

---

## Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | Full PostgreSQL DSN |

---

## Security / Session

| Variable | Default | Description |
|---|---|---|
| `SESSION_SECRET_KEY` | `dev-session-secret-change-me` | Cookie signing key. **Change in production.** |
| `SESSION_MAX_AGE` | `86400` | Session lifetime in seconds (default: 24h) |
| `CORS_ALLOWED_ORIGINS` | `["http://localhost:5173"]` | JSON list of allowed CORS origins |

---

## AI Provider

| Variable | Default | Description |
|---|---|---|
| `AI_AGENT_PROVIDER` | `gemini` | `gemini` or `openai` |
| `GEMINI_API_KEY` | — | Google AI API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Gemini model ID |
| `OPENAI_API_KEY` | — | OpenAI-compatible API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL (override for local models) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model ID |

---

## AI Pipeline Behavior

| Variable | Default | Description |
|---|---|---|
| `PROMPT_VERSION` | `v2` | System prompt version (`v1` or `v2`) |
| `AI_MAX_TASKS_PER_EXTRACTION` | `20` | Max tasks the agent may create in one run |
| `AI_ASSIGNEE_AUTO_APPLY_CONFIDENCE_THRESHOLD` | `0.8` | Min confidence (0–1) to auto-assign a recommendation |
| `AI_MAX_SOURCE_CONTENT_LENGTH` | `50000` | Max characters of source content sent to the model |

---

## Extraction Job Resilience

| Variable | Default | Description |
|---|---|---|
| `AI_EXTRACTION_JOB_MAX_ATTEMPTS` | `3` | Total retry attempts per extraction job |
| `AI_EXTRACTION_JOB_TIMEOUT_SECONDS` | `180` | Per-attempt timeout in seconds |
| `AI_EXTRACTION_JOB_RETRY_BACKOFF_SECONDS` | `5` | Base backoff (multiplied by 2^attempt) |
| `AI_EXTRACTION_JOB_TTL_SECONDS` | `3600` | How long completed jobs are kept in memory |
| `AI_EXTRACTION_DEAD_LETTER_TTL_SECONDS` | `86400` | How long failed jobs are kept for manual retry |
| `AI_EXTRACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `4` | Consecutive failures before circuit opens |
| `AI_EXTRACTION_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `120` | How long the circuit stays open before half-open |

---

## Agent Framework Limits

| Variable | Default | Description |
|---|---|---|
| `AGENT_MAX_ITERATIONS` | `20` | Max tool call iterations per agent run |
| `AGENT_MAX_CONTEXT_TURNS` | `28` | Max message turns in the context window |

---

## Memory Integration (Optional)

| Variable | Default | Description |
|---|---|---|
| `MEMORY_ENABLED` | `false` | Enable MemPalace integration |
| `MEMPALACE_BASE_URL` | — | MemPalace server URL |
| `MEMPALACE_API_KEY` | — | MemPalace API key |
| `MEMORY_INGESTION_JOB_TTL_SECONDS` | `3600` | TTL for memory ingestion jobs |

---

## Frontend Environment Variables

The frontend has its own `.env` file at `frontend/.env` (copy from `frontend/.env.example`).

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL (used in production builds) |

In development, the Vite dev server proxies `/api/*` to `http://localhost:8000` automatically (configured in `vite.config.ts`), so `VITE_API_URL` is only needed for production builds.

---

## Configuration File Locations

| File | Purpose |
|---|---|
| `backend/.env` | Backend environment variables |
| `backend/.env.example` | Template — copy and fill in |
| `backend/app/config.py` | `Settings` class definition with all defaults |
| `frontend/.env` | Frontend environment variables |
| `frontend/.env.example` | Template |
| `frontend/vite.config.ts` | Dev server proxy + build config |
| `compose.yml` | Docker Compose service definitions |
| `ecosystem.config.cjs` | PM2 process manager config |

---

## Example `.env` (Backend)

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/tgl_tasks

# Security
SESSION_SECRET_KEY=replace-this-with-a-long-random-string

# AI Provider (choose one)
AI_AGENT_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
# or:
# AI_AGENT_PROVIDER=openai
# OPENAI_API_KEY=your-openai-api-key

# CORS (comma-separated or JSON list)
CORS_ALLOWED_ORIGINS=["http://localhost:3000","https://yourdomain.com"]
```
