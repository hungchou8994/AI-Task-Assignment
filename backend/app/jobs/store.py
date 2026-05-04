from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

JobStatus = Literal["queued", "running", "done", "failed"]

_JOB_TTL_SECONDS = 3600  # evict jobs older than 1 hour


@dataclass
class JobEntry:
    job_id: str
    project_id: str
    status: JobStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeadLetterEntry:
    job_id: str
    project_id: str
    command: dict[str, Any]
    reason: str
    last_error: Optional[str] = None
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IngestionCircuitState:
    consecutive_failures: int = 0
    opened_until: Optional[datetime] = None
    recent_failure_timestamps: deque[float] = field(default_factory=deque)


_jobs: dict[str, JobEntry] = {}
_dead_letters: dict[str, DeadLetterEntry] = {}
_ingestion_circuit = IngestionCircuitState()
_lock = threading.Lock()


def create_job(job_id: str, project_id: str) -> JobEntry:
    entry = JobEntry(job_id=job_id, project_id=project_id, status="queued")
    with _lock:
        _jobs[job_id] = entry
    return entry


def update_job(
    job_id: str,
    status: JobStatus,
    *,
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    with _lock:
        entry = _jobs.get(job_id)
        if entry is None:
            return
        entry.status = status
        entry.result = result
        entry.error = error
        entry.updated_at = datetime.now(timezone.utc)


def set_job_attempts(job_id: str, attempts: int) -> None:
    with _lock:
        entry = _jobs.get(job_id)
        if entry is None:
            return
        entry.attempts = max(0, int(attempts))
        entry.updated_at = datetime.now(timezone.utc)


def get_job(job_id: str) -> Optional[JobEntry]:
    with _lock:
        return _jobs.get(job_id)


def enqueue_dead_letter(
    *,
    job_id: str,
    project_id: str,
    command: dict[str, Any],
    reason: str,
    last_error: Optional[str] = None,
    attempts: int = 0,
) -> DeadLetterEntry:
    entry = DeadLetterEntry(
        job_id=job_id,
        project_id=project_id,
        command=command,
        reason=reason,
        last_error=last_error,
        attempts=max(0, int(attempts)),
    )
    with _lock:
        _dead_letters[job_id] = entry
    return entry


def get_dead_letter(job_id: str) -> Optional[DeadLetterEntry]:
    with _lock:
        return _dead_letters.get(job_id)


def is_ingestion_circuit_open() -> tuple[bool, Optional[datetime], int]:
    now = datetime.now(timezone.utc)
    with _lock:
        opened_until = _ingestion_circuit.opened_until
        is_open = opened_until is not None and opened_until > now
        return is_open, opened_until, _ingestion_circuit.consecutive_failures


def record_ingestion_success() -> None:
    with _lock:
        _ingestion_circuit.consecutive_failures = 0
        _ingestion_circuit.opened_until = None
        _ingestion_circuit.recent_failure_timestamps.clear()


def record_ingestion_failure(
    *,
    now_ts: float,
    breaker_threshold: int,
    cooldown_seconds: int,
) -> tuple[int, Optional[datetime], bool]:
    should_open = False
    opened_until: Optional[datetime] = None
    with _lock:
        _ingestion_circuit.consecutive_failures += 1
        _ingestion_circuit.recent_failure_timestamps.append(now_ts)
        cutoff = now_ts - float(max(cooldown_seconds, 1))
        while (
            _ingestion_circuit.recent_failure_timestamps
            and _ingestion_circuit.recent_failure_timestamps[0] < cutoff
        ):
            _ingestion_circuit.recent_failure_timestamps.popleft()

        if _ingestion_circuit.consecutive_failures >= max(1, breaker_threshold):
            should_open = True
            _ingestion_circuit.opened_until = datetime.fromtimestamp(
                now_ts + max(1, cooldown_seconds), tz=timezone.utc
            )
            opened_until = _ingestion_circuit.opened_until

        return _ingestion_circuit.consecutive_failures, opened_until, should_open


def evict_old_jobs(
    max_age_seconds: int = _JOB_TTL_SECONDS,
    dead_letter_max_age_seconds: Optional[int] = None,
) -> None:
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_seconds
    dead_letter_cutoff = (
        None
        if dead_letter_max_age_seconds is None
        else datetime.now(timezone.utc).timestamp() - dead_letter_max_age_seconds
    )
    with _lock:
        stale = [
            jid for jid, entry in _jobs.items() if entry.created_at.timestamp() < cutoff
        ]
        for jid in stale:
            del _jobs[jid]

        if dead_letter_cutoff is not None:
            stale_dead_letters = [
                jid
                for jid, entry in _dead_letters.items()
                if entry.created_at.timestamp() < dead_letter_cutoff
            ]
            for jid in stale_dead_letters:
                del _dead_letters[jid]
