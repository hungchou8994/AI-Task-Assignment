from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.agent_extraction.event_store import get_events, subscribe
from app.auth import ensure_project_access, get_current_user
from app.dependencies import get_db
from app.jobs.extraction_job import run_extraction_job
from app.jobs.store import create_job, get_dead_letter, get_job, update_job
from app.models import User
from app.schemas import (
    AgentEventsResponse,
    DeadLetterJobResponse,
    ExtractedTaskResponse,
    ExtractJobQueued,
    ExtractJobStatusResponse,
    ExtractTasksCommand,
    ExtractTasksRequest,
    ExtractTasksResponse,
    ExtractTasksResult,
    RetryDeadLetterRequest,
)
from app.services import extraction_service as _extraction_svc

router = APIRouter(prefix="/api/ai", tags=["ai"])
DbDep = Annotated[Session, Depends(get_db)]
_SSE_HEARTBEAT_SECONDS = 15


class AnalyzeResponse(BaseModel):
    """Response model for email analysis (Plan 02 / Wave 0 TDD)."""

    candidates: list[object] = Field(default_factory=list)
    source_summary: str
    skipped_attachments: list[str] = Field(default_factory=list)
    failed_urls: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Extraction endpoint (merged from adapters/inbound/routes_ai.py)
# ---------------------------------------------------------------------------


def get_extract_tasks_use_case(db: Session):
    """Build the default extraction use case.

    Returns a simple wrapper so tests can monkeypatch this function to inject
    a fake implementation.
    """

    class _ServiceBasedUseCase:
        async def execute(self, command: ExtractTasksCommand) -> ExtractTasksResult:
            return await _extraction_svc.extract_tasks(db, command)

    return _ServiceBasedUseCase()


@router.post(
    "/extract-tasks",
    response_model=ExtractJobQueued,
    summary="Extract tasks from content",
)
async def extract_tasks(
    payload: ExtractTasksRequest,
    background_tasks: BackgroundTasks,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    *,
    use_case=None,
) -> ExtractJobQueued:
    ensure_project_access(payload.project_id, current_user, db, min_role="member")
    job_id = str(uuid4())
    create_job(job_id, str(payload.project_id))

    command = ExtractTasksCommand(
        source_type=payload.source_type,
        content=payload.content,
        project_id=str(payload.project_id),
        job_id=job_id,
    )

    if use_case is not None:
        # Direct execution path (used by tests that call the function directly).
        result = await use_case.execute(command)
        update_job(job_id, "done", result=result)
    else:
        background_tasks.add_task(run_extraction_job, job_id, command)

    return ExtractJobQueued(job_id=UUID(job_id), status="queued")


# ---------------------------------------------------------------------------
# Job status / events endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}", response_model=ExtractJobStatusResponse)
def get_extraction_job_status(
    job_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ExtractJobStatusResponse:
    entry = get_job(str(job_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Job not found")

    ensure_project_access(UUID(entry.project_id), current_user, db, min_role="viewer")

    # Convert ExtractTasksResult to ExtractTasksResponse if present
    result = None
    if entry.result and isinstance(entry.result, ExtractTasksResult):
        result = ExtractTasksResponse(
            source_summary=entry.result.source_summary,
            tasks=[
                ExtractedTaskResponse(
                    title=task.title,
                    description=task.description,
                    priority=task.priority,
                    due_date=task.due_date,
                    confidence_score=task.confidence_score,
                )
                for task in entry.result.tasks
            ],
            created_task_ids=list(entry.result.created_task_ids),
        )

    return ExtractJobStatusResponse(
        job_id=job_id,
        status=entry.status,
        attempts=entry.attempts,
        result=result,
        error=entry.error,
    )


@router.get("/jobs/{job_id}/dead-letter", response_model=DeadLetterJobResponse)
def get_dead_letter_job(
    job_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> DeadLetterJobResponse:
    item = get_dead_letter(str(job_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Dead-letter entry not found")

    ensure_project_access(UUID(item.project_id), current_user, db, min_role="viewer")

    return DeadLetterJobResponse(
        job_id=UUID(item.job_id),
        project_id=UUID(item.project_id),
        reason=item.reason,
        last_error=item.last_error,
        attempts=item.attempts,
        created_at=item.created_at,
    )


@router.post("/jobs/{job_id}/dead-letter/retry", response_model=ExtractJobQueued)
async def retry_dead_letter_job(
    job_id: UUID,
    payload: RetryDeadLetterRequest,
    background_tasks: BackgroundTasks,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ExtractJobQueued:
    dead = get_dead_letter(str(job_id))
    if dead is None:
        raise HTTPException(status_code=404, detail="Dead-letter entry not found")

    if str(payload.project_id) != dead.project_id:
        raise HTTPException(
            status_code=400,
            detail="project_id does not match dead-letter entry",
        )

    ensure_project_access(payload.project_id, current_user, db, min_role="member")

    new_job_id = str(uuid4())
    create_job(new_job_id, str(payload.project_id))
    command = ExtractTasksCommand(
        source_type=str(dead.command.get("source_type") or "text"),
        content=str(dead.command.get("content") or ""),
        project_id=str(payload.project_id),
        job_id=new_job_id,
    )
    background_tasks.add_task(run_extraction_job, new_job_id, command)
    return ExtractJobQueued(job_id=UUID(new_job_id), status="queued")


@router.get("/jobs/{job_id}/events", response_model=AgentEventsResponse)
def get_agent_loop_events(
    job_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentEventsResponse:
    entry = get_job(str(job_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Job not found")

    ensure_project_access(UUID(entry.project_id), current_user, db, min_role="viewer")
    return AgentEventsResponse(events=get_events(str(job_id)))


def _sse_data(payload: dict[str, object]) -> bytes:
    return f"data: {json.dumps(payload, default=str)}\n\n".encode("utf-8")


@router.get("/jobs/{job_id}/events/stream")
async def stream_agent_loop_events(
    job_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    entry = get_job(str(job_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Job not found")

    ensure_project_access(UUID(entry.project_id), current_user, db, min_role="viewer")

    async def event_generator():
        queue, unsubscribe = subscribe(str(job_id))
        sent_event_ids: set[str] = set()

        def _should_yield(event: dict[str, object]) -> bool:
            event_id = event.get("id")
            if not isinstance(event_id, str):
                return True
            if event_id in sent_event_ids:
                return False
            sent_event_ids.add(event_id)
            return True

        try:
            for event in get_events(str(job_id)):
                if _should_yield(event):
                    yield _sse_data(event)

            while True:
                if not queue.empty():
                    event = queue.get_nowait()
                    if _should_yield(event):
                        yield _sse_data(event)
                    continue

                current = get_job(str(job_id))
                if current and current.status in {"done", "failed"}:
                    yield _sse_data(
                        {
                            "event_type": "job_terminal",
                            "job_id": str(job_id),
                            "status": current.status,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_SSE_HEARTBEAT_SECONDS
                    )
                    if _should_yield(event):
                        yield _sse_data(event)
                except TimeoutError:
                    yield _sse_data(
                        {
                            "event_type": "heartbeat",
                            "job_id": str(job_id),
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
        finally:
            unsubscribe()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
