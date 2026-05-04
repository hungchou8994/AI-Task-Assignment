from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.candidate_service import create_task_from_candidate
from app.services.telegram_notification_service import notify_candidate_approved
from app.services.task_webhook_service import enqueue_task_webhook
from app.services.webhook_service import trigger_webhooks
from app.auth import (
    ensure_candidate_access,
    ensure_project_access,
    get_current_user,
)
from app.dependencies import get_db
from app.models import (
    CandidateApprovalAction,
    CandidateStatus,
    FeedbackAction,
    FeedbackEvent,
    Person,
    Project,
    Source,
    Task,
    TaskCandidate,
    TaskSource,
    TaskStatus,
    User,
)
from app.serialization import to_json_value as _to_json_value
from app.jobs.memory_ingestion_job import ingest_candidate_event
from app.schemas import (
    ApproveCandidateResponse,
    BatchCandidateActionRequest,
    BatchCandidateActionResponse,
    BatchCandidateItemResult,
    CandidateProvenanceResponse,
    RejectCandidateResponse,
    TaskCandidatePatch,
    TaskCandidateResponse,
)
from app.services.candidate_provenance_service import (
    append_candidate_approval_event,
    append_candidate_revision,
    build_candidate_provenance_payload,
    ensure_baseline_revision,
)

router = APIRouter(prefix="/api/task-candidates", tags=["task-candidates"])
DbDep = Annotated[Session, Depends(get_db)]
UNDO_WINDOW_SECONDS = 5

TRACKED_EDIT_FIELDS = {
    "title",
    "description",
    "priority",
    "due_date",
    "selected_assignee_id",
}


class UndoRejectCandidateResponseModel(BaseModel):
    candidate: TaskCandidateResponse


def _ensure_pending(candidate: TaskCandidate) -> None:
    if candidate.status != CandidateStatus.pending:
        raise HTTPException(status_code=409, detail="Candidate is not pending")


def _derive_selected_rank(candidate: TaskCandidate) -> str | None:
    if candidate.selected_assignee_id is None:
        return "unassigned"

    selected_id = str(candidate.selected_assignee_id)
    for recommendation in candidate.assignee_recommendations or []:
        if str(recommendation.get("person_id")) == selected_id:
            rank = recommendation.get("rank")
            if rank in (1, 2, 3):
                return f"top_{rank}"
    return "not_recommended"


def _batch_access_result(
    candidate_id: UUID, exc: HTTPException
) -> BatchCandidateItemResult:
    return BatchCandidateItemResult(
        candidate_id=candidate_id,
        status="forbidden",
        message=exc.detail,
    )


def _resolve_source_for_candidate(db: Session, candidate: TaskCandidate) -> Source:
    """Find or create a Source record for the given candidate."""
    project = db.get(Project, candidate.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source = (
        db.query(Source)
        .filter(
            Source.workspace_id == project.workspace_id,
            Source.project_id == candidate.project_id,
            Source.source_type == candidate.source_type,
            Source.summary == candidate.source_summary,
            Source.excerpt == candidate.source_excerpt,
        )
        .first()
    )

    if not source:
        source = Source(
            workspace_id=project.workspace_id,
            project_id=candidate.project_id,
            source_type=candidate.source_type,
            summary=candidate.source_summary,
            excerpt=candidate.source_excerpt,
            payload={},
        )
        db.add(source)
        db.flush()

    return source


def _link_task_to_source(
    db: Session, task: Task, source: Source, confidence: float
) -> None:
    """Link a Task to a Source if not already linked."""
    existing = (
        db.query(TaskSource)
        .filter(TaskSource.task_id == task.id, TaskSource.source_id == source.id)
        .first()
    )
    if not existing:
        db.add(
            TaskSource(
                task_id=task.id,
                source_id=source.id,
                link_type="derived_from",
                confidence_score=confidence,
            )
        )


def _trigger_candidate_webhooks(
    db: Session,
    candidate: TaskCandidate,
    event_type: str,
    background_tasks: BackgroundTasks,
) -> None:
    project = db.get(Project, candidate.project_id)
    if not project:
        return

    payload = {
        "event_type": event_type,
        "candidate": {
            "id": str(candidate.id),
            "title": candidate.title,
            "status": candidate.status.value
            if isinstance(candidate.status, Enum)
            else str(candidate.status),
            "project_id": str(candidate.project_id),
            "selected_assignee_id": str(candidate.selected_assignee_id)
            if candidate.selected_assignee_id
            else None,
        },
    }
    background_tasks.add_task(
        trigger_webhooks, db, project.workspace_id, event_type, candidate.id, payload
    )


def _approve_candidate(
    db: Session,
    candidate: TaskCandidate,
    actor_id: UUID,
    *,
    mode: str = "single",
) -> Task:
    """Shared approve logic for single and batch operations."""
    task = None
    created_task = False
    if candidate.approved_task_id is not None:
        task = db.get(Task, candidate.approved_task_id)
    if task is None:
        task = create_task_from_candidate(
            db, candidate, actor_type="user", actor_label="candidate_approve"
        )
        created_task = True

    source = _resolve_source_for_candidate(db, candidate)
    _link_task_to_source(db, task, source, candidate.confidence_score)
    ensure_baseline_revision(db, candidate, source_id=source.id)

    candidate.status = CandidateStatus.approved
    candidate.approved_task_id = task.id
    candidate.approved_at = datetime.now(timezone.utc)
    candidate.rejected_at = None
    candidate.undo_expires_at = None

    append_candidate_revision(
        db,
        candidate,
        revision_type="approved",
        source_id=source.id,
        event_metadata={"task_id": str(task.id), "mode": mode},
    )
    append_candidate_approval_event(
        db,
        candidate_id=candidate.id,
        action=CandidateApprovalAction.approve,
        actor_type="user",
        actor_id=actor_id,
        task_id=task.id,
        event_metadata={
            "selected_assignee_rank": _derive_selected_rank(candidate),
            "mode": mode,
        },
    )

    db.add(
        FeedbackEvent(
            project_id=candidate.project_id,
            candidate_id=candidate.id,
            action=FeedbackAction.accept,
            acted_at=datetime.now(timezone.utc),
            selected_assignee_id=candidate.selected_assignee_id,
            selected_assignee_rank=_derive_selected_rank(candidate),
        )
    )
    task._created_from_candidate_approval = created_task
    return task


def _reject_candidate(
    db: Session,
    candidate: TaskCandidate,
    actor_id: UUID,
    *,
    mode: str = "single",
) -> datetime:
    """Shared reject logic for single and batch operations."""
    if candidate.approved_task_id is not None:
        linked_task = db.get(Task, candidate.approved_task_id)
        if linked_task is not None:
            linked_task.status = TaskStatus.cancelled
        candidate.approved_task_id = None
        candidate.approved_at = None

    now = datetime.now(timezone.utc)
    candidate.status = CandidateStatus.rejected
    candidate.rejected_at = now
    candidate.undo_expires_at = now + timedelta(seconds=UNDO_WINDOW_SECONDS)

    source = _resolve_source_for_candidate(db, candidate)
    ensure_baseline_revision(db, candidate, source_id=source.id)
    append_candidate_revision(
        db,
        candidate,
        revision_type="rejected",
        source_id=source.id,
        event_metadata={"undo_window_seconds": UNDO_WINDOW_SECONDS, "mode": mode},
    )
    append_candidate_approval_event(
        db,
        candidate_id=candidate.id,
        action=CandidateApprovalAction.reject,
        actor_type="user",
        actor_id=actor_id,
        task_id=None,
        event_metadata={
            "undo_expires_at": candidate.undo_expires_at.isoformat(),
            "mode": mode,
        },
    )

    db.add(
        FeedbackEvent(
            project_id=candidate.project_id,
            candidate_id=candidate.id,
            action=FeedbackAction.reject,
            acted_at=now,
        )
    )
    return candidate.undo_expires_at


@router.get("", response_model=list[TaskCandidateResponse])
def list_candidates(
    db: DbDep,
    project_id: UUID = Query(...),
    status: CandidateStatus = Query(CandidateStatus.pending),
    current_user: User = Depends(get_current_user),
):
    ensure_project_access(project_id, current_user, db, min_role="viewer")
    return (
        db.query(TaskCandidate)
        .filter(TaskCandidate.project_id == project_id, TaskCandidate.status == status)
        .order_by(TaskCandidate.created_at.desc(), TaskCandidate.id.desc())
        .all()
    )


@router.patch("/{candidate_id}", response_model=TaskCandidateResponse)
def patch_candidate(
    candidate_id: UUID,
    payload: TaskCandidatePatch,
    db: DbDep,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
):
    candidate = ensure_candidate_access(
        candidate_id, current_user, db, min_role="member"
    )
    _ensure_pending(candidate)

    patch_data = payload.model_dump(exclude_unset=True)
    if (
        "selected_assignee_id" in patch_data
        and patch_data["selected_assignee_id"] is not None
    ):
        person = db.get(Person, patch_data["selected_assignee_id"])
        if not person:
            raise HTTPException(status_code=404, detail="Assignee not found")

    changed_fields: dict[str, dict[str, object]] = {}
    for field, final_value in patch_data.items():
        if field not in TRACKED_EDIT_FIELDS:
            continue
        original_value = getattr(candidate, field)
        if original_value != final_value:
            changed_fields[field] = {
                "original": _to_json_value(original_value),
                "final": _to_json_value(final_value),
            }

    if not changed_fields:
        return candidate

    for field, value in patch_data.items():
        setattr(candidate, field, value)

    source = _resolve_source_for_candidate(db, candidate)
    ensure_baseline_revision(db, candidate, source_id=source.id)
    append_candidate_revision(
        db,
        candidate,
        revision_type="edited",
        source_id=source.id,
        event_metadata={"changed_fields": changed_fields},
    )

    db.add(
        FeedbackEvent(
            project_id=candidate.project_id,
            candidate_id=candidate.id,
            action=FeedbackAction.edit,
            acted_at=datetime.now(timezone.utc),
            field_deltas=changed_fields,
        )
    )

    db.commit()
    db.refresh(candidate)
    background_tasks.add_task(
        ingest_candidate_event,
        str(candidate.id),
        event_type="candidate.edited",
        actor_id=str(current_user.id),
        field_deltas=changed_fields,
    )
    return candidate


@router.post("/{candidate_id}/approve", response_model=ApproveCandidateResponse)
def approve_candidate(
    candidate_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    candidate = ensure_candidate_access(
        candidate_id, current_user, db, min_role="member"
    )
    _ensure_pending(candidate)

    task = _approve_candidate(db, candidate, current_user.id)
    db.commit()
    db.refresh(candidate)

    _trigger_candidate_webhooks(db, candidate, "candidate.approved", background_tasks)
    if getattr(task, "_created_from_candidate_approval", False):
        _trigger_task_created_webhook(db, task, background_tasks)
        background_tasks.add_task(notify_candidate_approved, task, candidate)
    background_tasks.add_task(
        ingest_candidate_event,
        str(candidate.id),
        event_type="candidate.approved",
        actor_id=str(current_user.id),
        field_deltas={},
    )
    return ApproveCandidateResponse(candidate=candidate, task_id=task.id)


@router.post("/{candidate_id}/reject", response_model=RejectCandidateResponse)
def reject_candidate(
    candidate_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    candidate = ensure_candidate_access(
        candidate_id, current_user, db, min_role="member"
    )
    _ensure_pending(candidate)

    undo_expires_at = _reject_candidate(db, candidate, current_user.id)
    db.commit()
    db.refresh(candidate)

    _trigger_candidate_webhooks(db, candidate, "candidate.rejected", background_tasks)
    background_tasks.add_task(
        ingest_candidate_event,
        str(candidate.id),
        event_type="candidate.rejected",
        actor_id=str(current_user.id),
        field_deltas={},
    )
    return RejectCandidateResponse(
        candidate=candidate,
        undo_expires_at=undo_expires_at,
    )


@router.post(
    "/{candidate_id}/undo-reject", response_model=UndoRejectCandidateResponseModel
)
def undo_reject(
    candidate_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    candidate = ensure_candidate_access(
        candidate_id, current_user, db, min_role="member"
    )
    db.refresh(candidate)
    if candidate.status != CandidateStatus.rejected:
        raise HTTPException(status_code=409, detail="Candidate is not rejected")

    now = datetime.now(timezone.utc)
    undo_expires_at = candidate.undo_expires_at
    if undo_expires_at is not None and undo_expires_at.tzinfo is None:
        undo_expires_at = undo_expires_at.replace(tzinfo=timezone.utc)
    if not undo_expires_at or now > undo_expires_at:
        raise HTTPException(status_code=409, detail="Undo window expired")

    candidate.status = CandidateStatus.pending
    candidate.rejected_at = None
    candidate.undo_expires_at = None

    source = _resolve_source_for_candidate(db, candidate)
    ensure_baseline_revision(db, candidate, source_id=source.id)
    append_candidate_revision(
        db,
        candidate,
        revision_type="undo_reject",
        source_id=source.id,
        event_metadata={},
    )
    append_candidate_approval_event(
        db,
        candidate_id=candidate.id,
        action=CandidateApprovalAction.undo_reject,
        actor_type="user",
        actor_id=current_user.id,
        task_id=candidate.approved_task_id,
        event_metadata={},
    )

    db.commit()
    db.refresh(candidate)
    return UndoRejectCandidateResponseModel(candidate=candidate)


def _apply_approve(
    db: Session, candidate: TaskCandidate, candidate_id: UUID, actor_id: UUID
) -> BatchCandidateItemResult:
    task = _approve_candidate(db, candidate, actor_id, mode="batch")
    return BatchCandidateItemResult(
        candidate_id=candidate_id,
        status="approved",
        task_id=task.id,
    )


def _trigger_task_created_webhook(
    db: Session, task: Task, background_tasks: BackgroundTasks
) -> None:
    enqueue_task_webhook(db, task, "task.created", background_tasks)


def _apply_reject(
    db: Session, candidate: TaskCandidate, candidate_id: UUID, actor_id: UUID
) -> BatchCandidateItemResult:
    _reject_candidate(db, candidate, actor_id, mode="batch")
    return BatchCandidateItemResult(candidate_id=candidate_id, status="rejected")


def _run_batch_action(
    payload: BatchCandidateActionRequest,
    db: Session,
    current_user: User,
    background_tasks: BackgroundTasks,
    *,
    apply_fn,
    event_type: str,
) -> BatchCandidateActionResponse:
    """Shared skeleton for batch approve/reject: guard → access → apply → commit."""
    results: list[BatchCandidateItemResult] = []

    for candidate_id in payload.candidate_ids:
        candidate = db.get(TaskCandidate, candidate_id)
        if not candidate or candidate.status != CandidateStatus.pending:
            results.append(
                BatchCandidateItemResult(
                    candidate_id=candidate_id,
                    status="conflict",
                    message="Candidate missing or not pending",
                )
            )
            continue

        try:
            ensure_project_access(
                candidate.project_id, current_user, db, min_role="member"
            )
        except HTTPException as exc:
            results.append(_batch_access_result(candidate_id, exc))
            continue

        result = apply_fn(db, candidate, candidate_id, current_user.id)
        results.append(result)
        _trigger_candidate_webhooks(db, candidate, event_type, background_tasks)
        if event_type == "candidate.approved" and result.task_id:
            task = db.get(Task, result.task_id)
            if task is not None:
                _trigger_task_created_webhook(db, task, background_tasks)
                background_tasks.add_task(notify_candidate_approved, task, candidate)
        background_tasks.add_task(
            ingest_candidate_event,
            str(candidate.id),
            event_type=event_type,
            actor_id=str(current_user.id),
            field_deltas={},
        )

    db.commit()
    return BatchCandidateActionResponse(results=results)


@router.post("/batch-approve", response_model=BatchCandidateActionResponse)
def batch_approve(
    payload: BatchCandidateActionRequest,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    return _run_batch_action(
        payload,
        db,
        current_user,
        background_tasks,
        apply_fn=_apply_approve,
        event_type="candidate.approved",
    )


@router.post("/batch-reject", response_model=BatchCandidateActionResponse)
def batch_reject(
    payload: BatchCandidateActionRequest,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    return _run_batch_action(
        payload,
        db,
        current_user,
        background_tasks,
        apply_fn=_apply_reject,
        event_type="candidate.rejected",
    )


@router.get("/{candidate_id}/provenance", response_model=CandidateProvenanceResponse)
def get_candidate_provenance(
    candidate_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    candidate = ensure_candidate_access(
        candidate_id, current_user, db, min_role="viewer"
    )
    payload = build_candidate_provenance_payload(db, candidate)
    return CandidateProvenanceResponse.model_validate(payload)
