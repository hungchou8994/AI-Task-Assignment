from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CandidateApprovalAction,
    CandidateApprovalEvent,
    CandidateSourceSpan,
    TaskCandidate,
    TaskCandidateRevision,
)


def compute_prompt_template_hash(prompt_text: str | None) -> str | None:
    if not prompt_text:
        return None
    return sha256(prompt_text.encode("utf-8", errors="replace")).hexdigest()


def _next_revision_number(db: Session, candidate_id: UUID) -> int:
    current = db.scalar(
        select(func.max(TaskCandidateRevision.revision_number)).where(
            TaskCandidateRevision.candidate_id == candidate_id
        )
    )
    return int(current or 0) + 1


def append_candidate_revision(
    db: Session,
    candidate: TaskCandidate,
    *,
    revision_type: str,
    source_id: UUID | None,
    model_version: str | None = None,
    prompt_template_hash: str | None = None,
    model_latency_ms: int | None = None,
    event_metadata: dict[str, Any] | None = None,
) -> TaskCandidateRevision:
    revision = TaskCandidateRevision(
        candidate_id=candidate.id,
        revision_number=_next_revision_number(db, candidate.id),
        revision_type=revision_type,
        title=candidate.title,
        description=candidate.description,
        priority=candidate.priority,
        due_date=candidate.due_date,
        selected_assignee_id=candidate.selected_assignee_id,
        confidence_score=candidate.confidence_score,
        source_type=candidate.source_type,
        source_excerpt=candidate.source_excerpt,
        source_summary=candidate.source_summary,
        model_version=model_version,
        prompt_template_hash=prompt_template_hash,
        model_latency_ms=model_latency_ms,
        event_metadata=event_metadata or {},
    )
    db.add(revision)
    db.flush()

    if source_id is not None:
        db.add(
            CandidateSourceSpan(
                candidate_revision_id=revision.id,
                source_id=source_id,
                span_start=None,
                span_end=None,
                snippet=candidate.source_excerpt,
            )
        )
    return revision


def ensure_baseline_revision(
    db: Session,
    candidate: TaskCandidate,
    *,
    source_id: UUID | None,
) -> None:
    existing = db.scalar(
        select(TaskCandidateRevision.id)
        .where(TaskCandidateRevision.candidate_id == candidate.id)
        .limit(1)
    )
    if existing is not None:
        return
    append_candidate_revision(
        db,
        candidate,
        revision_type="snapshot",
        source_id=source_id,
        event_metadata={"reason": "backfill_baseline"},
    )


def append_candidate_approval_event(
    db: Session,
    *,
    candidate_id: UUID,
    action: CandidateApprovalAction,
    actor_type: str,
    actor_id: UUID | None,
    task_id: UUID | None,
    event_metadata: dict[str, Any] | None = None,
) -> CandidateApprovalEvent:
    event = CandidateApprovalEvent(
        candidate_id=candidate_id,
        task_id=task_id,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        event_metadata=event_metadata or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def _revision_to_dict(revision: TaskCandidateRevision, source_spans: list[dict]) -> dict:
    return {
        "id": revision.id,
        "candidate_id": revision.candidate_id,
        "revision_number": revision.revision_number,
        "revision_type": revision.revision_type,
        "title": revision.title,
        "description": revision.description,
        "priority": revision.priority,
        "due_date": revision.due_date,
        "selected_assignee_id": revision.selected_assignee_id,
        "confidence_score": revision.confidence_score,
        "source_type": revision.source_type,
        "source_excerpt": revision.source_excerpt,
        "source_summary": revision.source_summary,
        "model_version": revision.model_version,
        "prompt_template_hash": revision.prompt_template_hash,
        "model_latency_ms": revision.model_latency_ms,
        "event_metadata": revision.event_metadata or {},
        "created_at": revision.created_at,
        "source_spans": source_spans,
    }


def _approval_event_to_dict(event: CandidateApprovalEvent) -> dict:
    return {
        "id": event.id,
        "candidate_id": event.candidate_id,
        "task_id": event.task_id,
        "action": event.action,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "event_metadata": event.event_metadata or {},
        "created_at": event.created_at,
    }


def _span_to_dict(span: CandidateSourceSpan) -> dict:
    return {
        "id": span.id,
        "candidate_revision_id": span.candidate_revision_id,
        "source_id": span.source_id,
        "span_start": span.span_start,
        "span_end": span.span_end,
        "snippet": span.snippet,
        "created_at": span.created_at,
    }


def build_candidate_provenance_payload(
    db: Session, candidate: TaskCandidate
) -> dict[str, Any]:
    revisions = db.scalars(
        select(TaskCandidateRevision)
        .where(TaskCandidateRevision.candidate_id == candidate.id)
        .order_by(
            TaskCandidateRevision.revision_number.asc(),
            TaskCandidateRevision.created_at.asc(),
        )
    ).all()

    approval_events = db.scalars(
        select(CandidateApprovalEvent)
        .where(CandidateApprovalEvent.candidate_id == candidate.id)
        .order_by(
            CandidateApprovalEvent.created_at.asc(), CandidateApprovalEvent.id.asc()
        )
    ).all()

    # Build source spans grouped by revision
    revision_ids = {r.id for r in revisions}
    spans_by_revision: dict[Any, list[dict]] = {rid: [] for rid in revision_ids}
    if revision_ids:
        spans = db.scalars(
            select(CandidateSourceSpan)
            .where(CandidateSourceSpan.candidate_revision_id.in_(revision_ids))
            .order_by(
                CandidateSourceSpan.created_at.asc(), CandidateSourceSpan.id.asc()
            )
        ).all()
        for span in spans:
            spans_by_revision.setdefault(span.candidate_revision_id, []).append(
                _span_to_dict(span)
            )

    # Build timeline
    timeline: list[dict[str, Any]] = []
    for revision in revisions:
        timeline.append({
            "event_type": "candidate_revision",
            "event_id": str(revision.id),
            "candidate_id": str(candidate.id),
            "occurred_at": revision.created_at or datetime.now(timezone.utc),
            "data": {
                "revision_number": revision.revision_number,
                "revision_type": revision.revision_type,
                "model_version": revision.model_version,
                "prompt_template_hash": revision.prompt_template_hash,
                "model_latency_ms": revision.model_latency_ms,
                "event_metadata": revision.event_metadata or {},
                "source_spans": spans_by_revision.get(revision.id, []),
            },
        })
    for event in approval_events:
        timeline.append({
            "event_type": "candidate_approval_event",
            "event_id": str(event.id),
            "candidate_id": str(candidate.id),
            "occurred_at": event.created_at or datetime.now(timezone.utc),
            "data": {
                "action": event.action,
                "task_id": event.task_id,
                "actor_type": event.actor_type,
                "actor_id": event.actor_id,
                "event_metadata": event.event_metadata or {},
            },
        })

    timeline.sort(key=lambda item: (item["occurred_at"], item["event_id"]))

    return {
        "candidate_id": candidate.id,
        "approved_task_id": candidate.approved_task_id,
        "candidate_status": candidate.status,
        "revisions": [
            _revision_to_dict(item, spans_by_revision.get(item.id, []))
            for item in revisions
        ],
        "approval_events": [
            _approval_event_to_dict(item) for item in approval_events
        ],
        "timeline": timeline,
    }
