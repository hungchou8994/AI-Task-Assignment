from __future__ import annotations

import asyncio
import logging
import time

from app.config import get_settings
from app.dependencies import get_db
from app.jobs.store import (
    enqueue_dead_letter,
    evict_old_jobs,
    is_ingestion_circuit_open,
    record_ingestion_failure,
    record_ingestion_success,
    set_job_attempts,
    update_job,
)
from app.schemas import ExtractTasksCommand
from app.services.extraction_service import extract_tasks

logger = logging.getLogger(__name__)


async def run_extraction_job(job_id: str, command: ExtractTasksCommand) -> None:
    """Background worker: runs the full AI extraction pipeline for *job_id*.

    Creates its own DB session because the request-scoped session will already
    be closed by the time BackgroundTasks executes.
    """
    update_job(job_id, "running")
    settings = get_settings()

    is_open, opened_until, failure_count = is_ingestion_circuit_open()
    if is_open:
        message = "Extraction circuit breaker is open; queued for manual retry"
        if opened_until is not None:
            message = (
                f"Extraction circuit breaker is open until {opened_until.isoformat()} "
                "(manual retry after cooldown)"
            )
        enqueue_dead_letter(
            job_id=job_id,
            project_id=command.project_id,
            command={
                "source_type": command.source_type,
                "content": command.content,
                "project_id": command.project_id,
            },
            reason="circuit_open",
            last_error=message,
            attempts=0,
        )
        update_job(job_id, "failed", error=message)
        logger.warning(
            "Extraction job %s skipped due to open circuit (failures=%d)",
            job_id,
            failure_count,
        )
        evict_old_jobs(
            dead_letter_max_age_seconds=settings.ai_extraction_dead_letter_ttl_seconds
        )
        return

    db = next(get_db())
    try:
        last_exc: Exception | None = None
        max_attempts = max(1, settings.ai_extraction_job_max_attempts)
        base_backoff = max(0.0, settings.ai_extraction_job_retry_backoff_seconds)
        timeout_s = max(1.0, settings.ai_extraction_job_timeout_seconds)

        for attempt in range(1, max_attempts + 1):
            set_job_attempts(job_id, attempt)
            try:
                result = await asyncio.wait_for(
                    extract_tasks(db, command),
                    timeout=timeout_s,
                )
                update_job(job_id, "done", result=result)
                record_ingestion_success()
                logger.info(
                    "Extraction job %s completed on attempt %d: %d candidates",
                    job_id,
                    attempt,
                    len(getattr(result, "tasks", result.created_task_ids)),
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass  # session might be totally dead; ignore

                # Build a useful error string even for exceptions without messages.
                exc_detail = str(exc) or repr(exc) or type(exc).__name__
                logger.warning(
                    "Extraction job %s attempt %d/%d failed: %s",
                    job_id,
                    attempt,
                    max_attempts,
                    exc_detail,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(base_backoff * (2 ** (attempt - 1)))
        else:
            assert last_exc is not None
            now_ts = time.time()
            fail_count, opened_until, opened = record_ingestion_failure(
                now_ts=now_ts,
                breaker_threshold=settings.ai_extraction_circuit_breaker_failure_threshold,
                cooldown_seconds=settings.ai_extraction_circuit_breaker_cooldown_seconds,
            )

            # Always produce a non-empty error string for dead-letter / logs.
            last_error = str(last_exc) or repr(last_exc) or type(last_exc).__name__
            reason = "max_retries_exceeded"
            if isinstance(last_exc, TimeoutError):
                reason = "timeout"
            enqueue_dead_letter(
                job_id=job_id,
                project_id=command.project_id,
                command={
                    "source_type": command.source_type,
                    "content": command.content,
                    "project_id": command.project_id,
                },
                reason=reason,
                last_error=last_error,
                attempts=max_attempts,
            )
            if opened and opened_until is not None:
                last_error = (
                    f"{last_error} (circuit open until {opened_until.isoformat()}; "
                    f"consecutive_failures={fail_count})"
                )
            logger.error(
                "Extraction job %s failed permanently: %s",
                job_id,
                last_error,
                exc_info=(type(last_exc), last_exc, last_exc.__traceback__),
            )
            update_job(job_id, "failed", error=last_error)
    except Exception as exc:  # noqa: BLE001
        exc_detail = str(exc) or repr(exc) or type(exc).__name__
        logger.exception("Extraction job %s failed: %s", job_id, exc_detail)
        enqueue_dead_letter(
            job_id=job_id,
            project_id=command.project_id,
            command={
                "source_type": command.source_type,
                "content": command.content,
                "project_id": command.project_id,
            },
            reason="job_orchestration_error",
            last_error=exc_detail,
            attempts=0,
        )
        update_job(job_id, "failed", error=exc_detail)
    finally:
        db.close()
        evict_old_jobs(
            dead_letter_max_age_seconds=settings.ai_extraction_dead_letter_ttl_seconds
        )
