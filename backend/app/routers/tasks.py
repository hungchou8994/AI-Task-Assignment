from uuid import UUID
from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import ensure_project_access, ensure_task_access, get_current_user
from app.dependencies import get_db
from app.models import (
    Label,
    OrgMembership,
    Task,
    TaskCandidate,
    TaskDependency,
    TaskEstimate,
    TaskLabel,
    TaskStatusHistory,
    Person,
    Project,
    TaskActivityAction,
    TaskActivityEvent,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.schemas import (
    CandidateProvenanceResponse,
    TaskCreate,
    TaskUpdate,
    TaskPatch,
    TaskResponse,
    TaskAssigneeRecommendationsResponse,
    TaskStatusHistoryEntry,
    TaskDependencyCreate,
    TaskDependencyResponse,
    SourceResponse,
    TaskSourceLinkResponse,
    BulkDeleteTasksRequest,
    BulkDeleteTasksResponse,
)
from app.serialization import to_json_value as _to_json_value
from app.services.candidate_provenance_service import build_candidate_provenance_payload
from app.services.telegram_notification_service import (
    notify_task_created,
    notify_task_updated,
)
from app.services.task_webhook_service import enqueue_task_webhook

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
DbDep = Annotated[Session, Depends(get_db)]

TRACKED_ACTIVITY_FIELDS = {
    "title",
    "description",
    "priority",
    "due_date",
    "status",
    "assignee_id",
}


def _status_to_str(value) -> Optional[str]:
    if value is None:
        return None
    return value.value if isinstance(value, Enum) else str(value)


def record_task_status_history(
    db: Session,
    *,
    task_id: UUID,
    from_status,
    to_status,
    changed_at: datetime,
    actor_type: str,
    actor_id: Optional[UUID],
) -> None:
    db.add(
        TaskStatusHistory(
            task_id=task_id,
            from_status=_status_to_str(from_status),
            to_status=_status_to_str(to_status) or "",
            changed_at=changed_at,
            changed_by_actor_type=actor_type,
            changed_by_actor_id=actor_id,
        )
    )


def write_task_activity_event(
    *,
    db: Session,
    task: Task,
    action_type: TaskActivityAction,
    field_name: Optional[str] = None,
    before_value=None,
    after_value=None,
    actor_type: str = "user",
    actor_label: Optional[str] = "task_api",
    actor_id: Optional[UUID] = None,
    occurred_at: Optional[datetime] = None,
    event_metadata: Optional[dict] = None,
) -> TaskActivityEvent:
    event = TaskActivityEvent(
        task_id=task.id,
        project_id=task.project_id,
        action_type=action_type,
        field_name=field_name,
        before_value=_to_json_value(before_value),
        after_value=_to_json_value(after_value),
        event_metadata=event_metadata or {},
        actor_type=actor_type,
        actor_label=actor_label,
        actor_id=actor_id,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def build_task_response(db: Session, task: Task) -> TaskResponse:
    label_ids = list(
        db.scalars(select(TaskLabel.label_id).where(TaskLabel.task_id == task.id)).all()
    )
    latest = db.scalar(
        select(TaskEstimate)
        .where(TaskEstimate.task_id == task.id)
        .order_by(TaskEstimate.recorded_at.desc())
        .limit(1)
    )
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        assignee_id=task.assignee_id,
        project_id=task.project_id,
        needs_review=task.needs_review,
        created_at=task.created_at,
        updated_at=task.updated_at,
        archived_at=task.archived_at,
        label_ids=label_ids,
        estimated_hours=latest.estimated_hours if latest else None,
        actual_hours=latest.actual_hours if latest else None,
    )


def _task_workspace_id(db: Session, task: Task) -> UUID:
    project = db.get(Project, task.project_id)
    assert project is not None
    return project.workspace_id


def _record_field_changes(
    db: Session,
    task: Task,
    before: dict,
    update_data: dict,
    actor_id: UUID,
    now: datetime,
) -> None:
    """Emit activity events (and status history) for every changed tracked field."""
    for field in TRACKED_ACTIVITY_FIELDS:
        if field not in update_data:
            continue
        previous_value = before[field]
        next_value = getattr(task, field)
        if previous_value == next_value:
            continue

        if field == "status":
            action_type = TaskActivityAction.status_changed
        elif field == "assignee_id":
            action_type = TaskActivityAction.assignment_changed
        else:
            action_type = TaskActivityAction.field_changed

        write_task_activity_event(
            db=db,
            task=task,
            action_type=action_type,
            field_name=field,
            before_value=previous_value,
            after_value=next_value,
            actor_type="user",
            actor_label="task_api",
            occurred_at=now,
        )
        if field == "status":
            record_task_status_history(
                db,
                task_id=task.id,
                from_status=previous_value,
                to_status=next_value,
                changed_at=now,
                actor_type="user",
                actor_id=actor_id,
            )


def _trigger_task_webhooks(
    db: Session, task: Task, event_type: str, background_tasks: BackgroundTasks
) -> None:
    enqueue_task_webhook(db, task, event_type, background_tasks)


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(
    payload: TaskCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    ensure_project_access(payload.project_id, current_user, db, min_role="member")
    if payload.assignee_id is not None:
        person = db.get(Person, payload.assignee_id)
        if not person:
            raise HTTPException(status_code=404, detail="Assignee not found")
    task_data = payload.model_dump()
    if task_data.get("due_date") is None:
        task_data["due_date"] = date.today()
    task = Task(**task_data)
    db.add(task)
    db.flush()
    write_task_activity_event(
        db=db,
        task=task,
        action_type=TaskActivityAction.task_created,
        actor_type="user",
        actor_label="task_api",
    )
    db.commit()
    db.refresh(task)
    _trigger_task_webhooks(db, task, "task.created", background_tasks)
    background_tasks.add_task(notify_task_created, task)
    return build_task_response(db, task)


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: DbDep,
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    include_archived: bool = Query(
        False, description="Include archived (soft-deleted) tasks"
    ),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .outerjoin(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .outerjoin(
            OrgMembership,
            OrgMembership.org_id == Workspace.org_id,
        )
        .where(
            (Workspace.owner_id == current_user.id)
            | (WorkspaceMembership.user_id == current_user.id)
            | (
                (OrgMembership.user_id == current_user.id)
                & (OrgMembership.role.in_(["owner", "admin"]))
            )
        )
    )
    if not include_archived:
        stmt = stmt.where(Task.archived_at.is_(None))
    if project_id:
        ensure_project_access(project_id, current_user, db, min_role="viewer")
        stmt = stmt.where(Task.project_id == project_id)
    tasks = db.scalars(stmt).all()
    return [build_task_response(db, t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = ensure_task_access(task_id, current_user, db, min_role="viewer")
    return build_task_response(db, task)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    task = ensure_task_access(task_id, current_user, db, min_role="member")
    update_data = payload.model_dump(exclude_unset=True)
    if "assignee_id" in update_data and update_data["assignee_id"] is not None:
        person = db.get(Person, update_data["assignee_id"])
        if not person:
            raise HTTPException(status_code=404, detail="Assignee not found")

    before = {
        field: getattr(task, field)
        for field in TRACKED_ACTIVITY_FIELDS
        if field in update_data
    }

    old_status = task.status

    for field, value in update_data.items():
        setattr(task, field, value)

    _record_field_changes(
        db,
        task,
        before,
        update_data,
        actor_id=current_user.id,
        now=datetime.now(timezone.utc),
    )

    db.commit()
    db.refresh(task)

    if old_status != task.status:
        event_type = "task.completed" if task.status == "done" else "task.updated"
    else:
        event_type = "task.updated"
    _trigger_task_webhooks(db, task, event_type, background_tasks)
    if event_type == "task.updated":
        background_tasks.add_task(notify_task_updated, task)

    return build_task_response(db, task)


@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: UUID,
    payload: TaskPatch,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    task = ensure_task_access(task_id, current_user, db, min_role="member")
    data = payload.model_dump(exclude_unset=True)

    old_status = task.status

    if "assignee_id" in data:
        aid = data["assignee_id"]
        if aid is not None:
            person = db.get(Person, aid)
            if not person:
                raise HTTPException(status_code=404, detail="Person not found")
        previous_assignee = task.assignee_id
        task.assignee_id = aid
        if previous_assignee != task.assignee_id:
            write_task_activity_event(
                db=db,
                task=task,
                action_type=TaskActivityAction.assignment_changed,
                field_name="assignee_id",
                before_value=previous_assignee,
                after_value=task.assignee_id,
                actor_type="user",
                actor_label="task_api",
            )

    if "status" in data:
        task.status = data["status"]

    if "label_ids" in data:
        ws_id = _task_workspace_id(db, task)
        new_ids = data["label_ids"] or []
        for lid in new_ids:
            lb = db.get(Label, lid)
            if not lb or lb.workspace_id != ws_id:
                raise HTTPException(
                    status_code=400,
                    detail="Label not found in this task's workspace",
                )
        db.execute(delete(TaskLabel).where(TaskLabel.task_id == task.id))
        for lid in new_ids:
            db.add(TaskLabel(task_id=task.id, label_id=lid))

    if "estimated_hours" in data or "actual_hours" in data:
        db.add(
            TaskEstimate(
                task_id=task.id,
                estimated_hours=data.get("estimated_hours"),
                actual_hours=data.get("actual_hours"),
                estimated_by=current_user.id,
            )
        )

    db.commit()
    db.refresh(task)

    if old_status != task.status:
        event_type = "task.completed" if task.status == "done" else "task.updated"
    else:
        event_type = "task.updated"
    _trigger_task_webhooks(db, task, event_type, background_tasks)
    if event_type == "task.updated":
        background_tasks.add_task(notify_task_updated, task)

    return build_task_response(db, task)


@router.post("/{task_id}/archive", response_model=TaskResponse)
def archive_task(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = ensure_task_access(task_id, current_user, db, min_role="member")
    task.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return build_task_response(db, task)


@router.post("/{task_id}/unarchive", response_model=TaskResponse)
def unarchive_task(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = ensure_task_access(task_id, current_user, db, min_role="member")
    task.archived_at = None
    db.commit()
    db.refresh(task)
    return build_task_response(db, task)


@router.get(
    "/{task_id}/status-history",
    response_model=list[TaskStatusHistoryEntry],
)
def get_task_status_history(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="viewer")
    rows = db.scalars(
        select(TaskStatusHistory)
        .where(TaskStatusHistory.task_id == task_id)
        .order_by(TaskStatusHistory.changed_at.desc())
    ).all()
    return rows


@router.post(
    "/{task_id}/dependencies",
    response_model=TaskDependencyResponse,
    status_code=201,
)
def add_task_dependency(
    task_id: UUID,
    payload: TaskDependencyCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    dependent = ensure_task_access(task_id, current_user, db, min_role="member")
    ensure_task_access(payload.blocks_task_id, current_user, db, min_role="viewer")
    if dependent.id == payload.blocks_task_id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")
    ws_d = _task_workspace_id(db, dependent)
    blocker = db.get(Task, payload.blocks_task_id)
    assert blocker is not None
    ws_b = _task_workspace_id(db, blocker)
    if ws_d != ws_b:
        raise HTTPException(
            status_code=400,
            detail="Dependent and blocking tasks must be in the same workspace",
        )
    row = TaskDependency(
        dependent_task_id=dependent.id,
        blocks_task_id=payload.blocks_task_id,
        dependency_type=payload.dependency_type,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="This dependency already exists"
        ) from None
    db.refresh(row)
    return row


@router.get(
    "/{task_id}/assignee-recommendations",
    response_model=TaskAssigneeRecommendationsResponse,
)
def get_task_assignee_recommendations(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = ensure_task_access(task_id, current_user, db, min_role="viewer")

    candidate = (
        db.query(TaskCandidate)
        .filter(TaskCandidate.approved_task_id == task_id)
        .first()
    )

    recommendations = candidate.assignee_recommendations if candidate else []

    return TaskAssigneeRecommendationsResponse(recommendations=recommendations)


@router.get("/{task_id}/sources", response_model=list[TaskSourceLinkResponse])
def get_task_sources(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="viewer")

    from app.models import Source, TaskSource

    stmt = (
        select(TaskSource, Source)
        .join(Source, TaskSource.source_id == Source.id)
        .where(TaskSource.task_id == task_id)
    )
    results = db.execute(stmt).all()

    return [
        TaskSourceLinkResponse(
            task_id=ts.task_id,
            source_id=ts.source_id,
            link_type=ts.link_type,
            confidence_score=ts.confidence_score,
            created_at=ts.created_at,
            source=SourceResponse.model_validate(s),
        )
        for ts, s in results
    ]


@router.get("/{task_id}/provenance", response_model=CandidateProvenanceResponse)
def get_task_provenance(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="viewer")

    candidate = (
        db.query(TaskCandidate)
        .filter(TaskCandidate.approved_task_id == task_id)
        .order_by(TaskCandidate.updated_at.desc(), TaskCandidate.id.desc())
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="No provenance found for task")

    payload = build_candidate_provenance_payload(db, candidate)
    return CandidateProvenanceResponse.model_validate(payload)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = ensure_task_access(task_id, current_user, db, min_role="manager")
    db.delete(task)
    db.commit()


@router.post("/bulk-delete", response_model=BulkDeleteTasksResponse)
def bulk_delete_tasks(
    payload: BulkDeleteTasksRequest,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    deleted_count = 0
    for task_id in payload.task_ids:
        task = ensure_task_access(task_id, current_user, db, min_role="manager")
        db.delete(task)
        deleted_count += 1
    db.commit()
    return BulkDeleteTasksResponse(deleted_count=deleted_count)
