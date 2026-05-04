from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import ensure_task_access, get_current_user
from app.dependencies import get_db
from app.models import TaskActivityEvent, User
from app.schemas import TaskActivityEventResponse

router = APIRouter(prefix="/api/tasks", tags=["task-activity"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/{task_id}/activity", response_model=list[TaskActivityEventResponse])
def list_task_activity(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="viewer")

    return (
        db.query(TaskActivityEvent)
        .filter(TaskActivityEvent.task_id == task_id)
        .order_by(TaskActivityEvent.occurred_at.desc(), TaskActivityEvent.id.desc())
        .all()
    )
