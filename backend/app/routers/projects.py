from uuid import UUID
from typing import Annotated, Literal, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from app.auth import ensure_project_access, get_current_user
from app.dependencies import get_db
from app.models import Source, Task, TaskStatus, User
from app.schemas import ProjectForecastResponse, SourceResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/{project_id}/sources", response_model=list[SourceResponse])
def list_project_sources(
    project_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_project_access(project_id, current_user, db, min_role="viewer")
    rows = db.scalars(
        select(Source)
        .where(Source.project_id == project_id)
        .order_by(Source.created_at.desc())
    ).all()
    return [
        SourceResponse.model_validate(row).model_copy(update={"payload": {}})
        for row in rows
    ]


@router.get("/{project_id}/forecast", response_model=ProjectForecastResponse)
def get_project_forecast(
    project_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Expose a project-level forecast API endpoint for the forecasting UI.
    """
    ensure_project_access(project_id, current_user, db, min_role="viewer")

    # 1. Compute velocity
    # Velocity = tasks completed in last 4 weeks / 4
    four_weeks_ago = datetime.now() - timedelta(weeks=4)
    completed_stmt = select(func.count(Task.id)).where(
        and_(
            Task.project_id == project_id,
            Task.status == TaskStatus.done,
            Task.updated_at >= four_weeks_ago,
        )
    )
    recent_completions = db.execute(completed_stmt).scalar() or 0
    velocity = recent_completions / 4.0

    # 2. Remaining tasks
    remaining_stmt = select(func.count(Task.id)).where(
        and_(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.todo, TaskStatus.in_progress]),
        )
    )
    remaining_tasks = db.execute(remaining_stmt).scalar() or 0

    # 3. Estimated completion date
    est_date = None
    if velocity > 0:
        weeks_to_complete = remaining_tasks / velocity
        est_date = date.today() + timedelta(weeks=weeks_to_complete)

    # 4. Confidence
    # Total historical completions
    total_completed_stmt = select(func.count(Task.id)).where(
        and_(Task.project_id == project_id, Task.status == TaskStatus.done)
    )
    total_completed = db.execute(total_completed_stmt).scalar() or 0

    confidence: Literal["low", "medium", "high"] = "low"
    if total_completed >= 10:
        confidence = "high"
    elif total_completed >= 5:
        confidence = "medium"

    return ProjectForecastResponse(
        velocity_per_week=velocity,
        remaining_tasks=remaining_tasks,
        estimated_completion_date=est_date,
        confidence=confidence,
    )
