# Testing

## Overview

The test suite is located in `backend/tests/` and uses **pytest**. There are 25 test files covering the core platform, AI pipeline, memory integration, and resilience patterns.

---

## Running Tests

```bash
cd backend

# Activate virtual environment
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows

# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_tasks.py

# Run a specific test function
pytest tests/test_tasks.py::test_create_task

# Run tests matching a keyword
pytest -k "extraction"

# Run with coverage report
pytest --cov=app --cov-report=html
```

Configuration is in `backend/pytest.ini`.

---

## Test File Index

### Core Platform

| File | Coverage Area |
|---|---|
| `test_tasks.py` | Task CRUD, status transitions, archiving, labels, dependencies |
| `test_task_activity.py` | Task activity events and status history |
| `test_task_schema_extensions.py` | Labels, estimates, dependencies |
| `test_task_candidates.py` | Review queue: approve, reject, undo, batch operations |
| `test_workspaces.py` | Workspace and project management, RBAC |
| `test_people.py` | Team member CRUD, skills |
| `test_sources.py` | Source document persistence and retrieval |
| `test_webhooks.py` | Webhook subscription and delivery |
| `test_feedback_analytics.py` | Analytics aggregation and timeline |
| `test_project_forecast.py` | Project-level task forecast calculations |

### AI Pipeline

| File | Coverage Area |
|---|---|
| `test_ai_modules.py` | AI module wiring and integration |
| `test_agent_framework.py` | Agent Runner loop, tool execution, loop detection |
| `test_openai_model_adapter.py` | OpenAI model adapter behavior |
| `test_extraction_service_source_persistence.py` | Source deduplication and persistence in extraction |
| `test_extraction_job_resilience.py` | Retry logic, circuit breaker, dead-letter queue |
| `test_dedup.py` | Content hash deduplication logic |
| `test_email_preprocessor.py` | Email parsing and normalization |
| `test_ai_prompt_language_policy.py` | Prompt language enforcement (English-only output) |

### Memory Integration

| File | Coverage Area |
|---|---|
| `test_memory_service.py` | MemPalace store/retrieve operations |
| `test_memory_policy.py` | Memory storage policy rules |
| `test_memory_ingestion_job.py` | Background memory ingestion job |
| `test_memory_context_builder.py` | Memory context assembly for prompts |
| `test_memory_audit_service.py` | Memory audit trail |

### Acceptance / QA

| File | Coverage Area |
|---|---|
| `test_qa_ait_40.py` | End-to-end acceptance tests (AIT-40 spec) |

### Helpers

| File | Purpose |
|---|---|
| `helpers.py` | Shared test utilities and fixtures |
| `__init__.py` | Package marker |

---

## Test Configuration (`pytest.ini`)

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

Tests use `asyncio_mode = auto` because FastAPI route handlers and some services are async.

---

## Writing Tests

Tests use standard **pytest** patterns with **FastAPI's `TestClient`**:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

For async code:

```python
import pytest

@pytest.mark.asyncio
async def test_something_async():
    result = await some_async_function()
    assert result is not None
```

Shared fixtures (database session, authenticated client, sample workspace/project/task) are defined in `tests/helpers.py`.

---

## Test Database

By default, tests use an **in-memory SQLite** database (configured via `DATABASE_URL` in the test environment) or a separate test PostgreSQL database. Check `helpers.py` for the exact fixture setup.

To run tests against a real PostgreSQL instance, set `DATABASE_URL` in your environment before running pytest:

```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/tgl_test pytest
```
