from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from app.jobs import extraction_job
from app.jobs.store import (
    create_job,
    enqueue_dead_letter,
    get_dead_letter,
    get_job,
    record_ingestion_failure,
    record_ingestion_success,
)
from app.schemas import ExtractTasksCommand

# Requirement mapping:
# - TEST-01: retry/dead-letter/circuit-breaker resilience remains correct on async path


def _settings(**overrides):
    base = {
        "ai_extraction_job_max_attempts": 3,
        "ai_extraction_job_retry_backoff_seconds": 0.0,
        "ai_extraction_job_timeout_seconds": 5.0,
        "ai_extraction_circuit_breaker_failure_threshold": 2,
        "ai_extraction_circuit_breaker_cooldown_seconds": 30,
        "ai_extraction_dead_letter_ttl_seconds": 3600,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _command() -> ExtractTasksCommand:
    return ExtractTasksCommand(
        source_type="text",
        content="source payload",
        project_id="00000000-0000-0000-0000-000000000001",
        job_id="job-1",
    )


def test_extraction_job_retries_then_succeeds(monkeypatch):
    record_ingestion_success()
    create_job("job-1", "00000000-0000-0000-0000-000000000001")

    attempts = {"count": 0}

    async def flaky_extract(_db, _command):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary")
        return SimpleNamespace(created_task_ids=("task-1",))

    monkeypatch.setattr(extraction_job, "extract_tasks", flaky_extract)
    monkeypatch.setattr(extraction_job, "get_settings", lambda: _settings())

    class _Db:
        def close(self):
            return None

    monkeypatch.setattr(extraction_job, "get_db", lambda: iter([_Db()]))

    asyncio.run(extraction_job.run_extraction_job("job-1", _command()))

    entry = get_job("job-1")
    assert entry is not None
    assert entry.status == "done"
    assert entry.attempts == 3
    assert entry.error is None
    assert get_dead_letter("job-1") is None


def test_extraction_job_moves_to_dead_letter_after_max_retries(monkeypatch):
    record_ingestion_success()
    create_job("job-2", "00000000-0000-0000-0000-000000000001")

    async def always_fail(_db, _command):
        raise RuntimeError("boom")

    monkeypatch.setattr(extraction_job, "extract_tasks", always_fail)
    monkeypatch.setattr(extraction_job, "get_settings", lambda: _settings())

    class _Db:
        def close(self):
            return None

    monkeypatch.setattr(extraction_job, "get_db", lambda: iter([_Db()]))

    asyncio.run(extraction_job.run_extraction_job("job-2", _command()))

    entry = get_job("job-2")
    assert entry is not None
    assert entry.status == "failed"
    assert entry.attempts == 3
    assert entry.error is not None
    assert "boom" in entry.error

    dead = get_dead_letter("job-2")
    assert dead is not None
    assert dead.reason == "max_retries_exceeded"
    assert dead.attempts == 3


def test_extraction_job_short_circuits_when_circuit_open(monkeypatch):
    record_ingestion_success()
    create_job("job-3", "00000000-0000-0000-0000-000000000001")

    # Open the breaker with synthetic failures.
    record_ingestion_failure(
        now_ts=time.time(),
        breaker_threshold=1,
        cooldown_seconds=60,
    )

    called = {"value": False}

    async def should_not_run(_db, _command):
        called["value"] = True
        return SimpleNamespace(created_task_ids=())

    monkeypatch.setattr(extraction_job, "extract_tasks", should_not_run)
    monkeypatch.setattr(extraction_job, "get_settings", lambda: _settings())

    class _Db:
        def close(self):
            return None

    monkeypatch.setattr(extraction_job, "get_db", lambda: iter([_Db()]))

    asyncio.run(extraction_job.run_extraction_job("job-3", _command()))

    entry = get_job("job-3")
    assert entry is not None
    assert entry.status == "failed"
    assert entry.error is not None
    assert "circuit breaker is open" in entry.error
    assert called["value"] is False
    dead = get_dead_letter("job-3")
    assert dead is not None
    assert dead.reason == "circuit_open"

    record_ingestion_success()


def test_dead_letter_can_be_enqueued_for_manual_retry():
    enqueue_dead_letter(
        job_id="job-4",
        project_id="00000000-0000-0000-0000-000000000001",
        command={
            "source_type": "text",
            "content": "x",
            "project_id": "00000000-0000-0000-0000-000000000001",
        },
        reason="manual_test",
        attempts=1,
    )
    dead = get_dead_letter("job-4")
    assert dead is not None
    assert dead.reason == "manual_test"
