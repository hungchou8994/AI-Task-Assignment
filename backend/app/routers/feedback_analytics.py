from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import ensure_project_access, get_current_user
from app.dependencies import get_db
from app.models import FeedbackAction, FeedbackEvent, User
from app.schemas import (
    AssigneeAccuracyMetric,
    FeedbackAnalyticsResponse,
    FieldAccuracyMetric,
    RatePoint,
)

router = APIRouter(prefix="/api/feedback-analytics", tags=["feedback-analytics"])
DbDep = Annotated[Session, Depends(get_db)]
Period = Literal["day", "week", "month"]
TRACKED_FIELDS = [
    "title",
    "description",
    "priority",
    "due_date",
    "selected_assignee_id",
]


def _bucket_start(dt: datetime, period: Period) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    if period == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        week_start = dt - timedelta(days=dt.weekday())
        return week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _safe_rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


# ---------------------------------------------------------------------------
# Computation helpers
# ---------------------------------------------------------------------------


def _aggregate_events(
    events: list[FeedbackEvent], period: Period
) -> tuple[
    dict[datetime, dict[str, int]],
    list[FeedbackEvent],
    dict[UUID, list[dict]],
    dict[str, int],
]:
    """Single pass over events: bucket counts, accept list, edit deltas, touch counts.

    Returns:
        bucket_counts: {bucket_start: {action_value: count}}
        accept_events: list of accept FeedbackEvents
        edits_by_candidate: {candidate_id: [field_deltas, ...]}
        edit_touch_counts: {field_name: number_of_edits_touching_this_field}
    """
    bucket_counts: dict[datetime, dict[str, int]] = defaultdict(
        lambda: {"accept": 0, "reject": 0, "edit": 0}
    )
    accept_events: list[FeedbackEvent] = []
    edits_by_candidate: dict[UUID, list[dict]] = defaultdict(list)
    edit_touch_counts: dict[str, int] = {field: 0 for field in TRACKED_FIELDS}

    for event in events:
        bucket = _bucket_start(event.acted_at, period)
        bucket_counts[bucket][event.action.value] += 1

        if event.action == FeedbackAction.accept:
            accept_events.append(event)
        elif event.action == FeedbackAction.edit and event.field_deltas:
            edits_by_candidate[event.candidate_id].append(event.field_deltas)
            for field in TRACKED_FIELDS:
                if field in event.field_deltas:
                    edit_touch_counts[field] += 1

    return bucket_counts, accept_events, edits_by_candidate, edit_touch_counts


def _build_rate_series(
    bucket_counts: dict[datetime, dict[str, int]],
) -> list[RatePoint]:
    """Convert bucketed action counts into a time-ordered rate series."""
    rate_series: list[RatePoint] = []
    for bucket in sorted(bucket_counts.keys()):
        counts = bucket_counts[bucket]
        total = counts["accept"] + counts["reject"] + counts["edit"]
        rate_series.append(
            RatePoint(
                bucket_start=bucket,
                total_actions=total,
                accept_rate=_safe_rate(counts["accept"], total),
                reject_rate=_safe_rate(counts["reject"], total),
                edit_rate=_safe_rate(counts["edit"], total),
            )
        )
    return rate_series


def _build_field_accuracy(
    accept_events: list[FeedbackEvent],
    edits_by_candidate: dict[UUID, list[dict]],
    edit_touch_counts: dict[str, int],
) -> list[FieldAccuracyMetric]:
    """Compute per-field accuracy: fraction of accepted candidates not edited on that field."""
    total_accepts = len(accept_events)

    # Precompute which accepted candidates were edited on each field
    edited_candidates_by_field: dict[str, set[UUID]] = {
        field: set() for field in TRACKED_FIELDS
    }
    for event in accept_events:
        for field in TRACKED_FIELDS:
            if any(field in delta for delta in edits_by_candidate.get(event.candidate_id, [])):
                edited_candidates_by_field[field].add(event.candidate_id)

    return [
        FieldAccuracyMetric(
            field=field,
            total_considered=total_accepts + edit_touch_counts[field],
            accurate_count=total_accepts - len(edited_candidates_by_field[field]),
            accuracy_rate=_safe_rate(
                total_accepts - len(edited_candidates_by_field[field]),
                total_accepts + edit_touch_counts[field],
            ),
        )
        for field in TRACKED_FIELDS
    ]


def _build_assignee_accuracy(
    accept_events: list[FeedbackEvent],
) -> AssigneeAccuracyMetric:
    """Summarise how often the AI's ranked assignee suggestions were accepted."""
    total_accepts = len(accept_events)

    def _count(rank: str) -> int:
        return sum(1 for e in accept_events if e.selected_assignee_rank == rank)

    top_1_count = _count("top_1")
    top_2_count = _count("top_2")
    top_3_count = _count("top_3")
    not_recommended_count = _count("not_recommended")
    unassigned_count = sum(
        1
        for e in accept_events
        if e.selected_assignee_rank == "unassigned" or e.selected_assignee_id is None
    )

    return AssigneeAccuracyMetric(
        total_accepts=total_accepts,
        top_1_count=top_1_count,
        top_1_rate=_safe_rate(top_1_count, total_accepts),
        top_2_count=top_2_count,
        top_2_rate=_safe_rate(top_2_count, total_accepts),
        top_3_count=top_3_count,
        top_3_rate=_safe_rate(top_3_count, total_accepts),
        not_recommended_count=not_recommended_count,
        not_recommended_rate=_safe_rate(not_recommended_count, total_accepts),
        unassigned_count=unassigned_count,
        unassigned_rate=_safe_rate(unassigned_count, total_accepts),
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("", response_model=FeedbackAnalyticsResponse)
def get_feedback_analytics(
    db: DbDep,
    project_id: UUID = Query(...),
    period: Period = Query("week"),
    current_user: User = Depends(get_current_user),
):
    ensure_project_access(project_id, current_user, db, min_role="viewer")
    events = (
        db.query(FeedbackEvent)
        .filter(FeedbackEvent.project_id == project_id)
        .order_by(FeedbackEvent.acted_at.asc())
        .all()
    )

    bucket_counts, accept_events, edits_by_candidate, edit_touch_counts = (
        _aggregate_events(events, period)
    )

    return FeedbackAnalyticsResponse(
        project_id=project_id,
        period=period,
        rate_series=_build_rate_series(bucket_counts),
        field_accuracy=_build_field_accuracy(
            accept_events, edits_by_candidate, edit_touch_counts
        ),
        assignee_accuracy=_build_assignee_accuracy(accept_events),
    )
