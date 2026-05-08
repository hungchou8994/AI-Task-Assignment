"""
Task Comments router.

Endpoints:
  GET    /api/tasks/{task_id}/comments                — list comments (viewer+)
  POST   /api/tasks/{task_id}/comments                — create comment (member+)
  PUT    /api/tasks/{task_id}/comments/{comment_id}   — edit own comment (author only)
  DELETE /api/tasks/{task_id}/comments/{comment_id}   — delete own or any (author / admin / owner)
"""
from datetime import datetime, timezone
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth import ensure_task_access, get_current_user, WORKSPACE_ROLE_PRIORITY
from app.dependencies import get_db
from app.models import TaskComment, User, WorkspaceMembership, Project, Workspace
from app.schemas import TaskCommentCreate, TaskCommentUpdate, TaskCommentResponse
from app.errors import NotFound, Forbidden

router = APIRouter(prefix="/api/tasks", tags=["task-comments"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/{task_id}/comments", response_model=list[TaskCommentResponse])
def list_task_comments(
    task_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="viewer")

    comments = (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
        .all()
    )

    # Resolve author emails — batch load users for comments that have an author_id
    author_ids = {c.author_id for c in comments if c.author_id is not None}
    users_by_id = {}
    if author_ids:
        rows = db.execute(select(User).where(User.id.in_(author_ids))).scalars().all()
        users_by_id = {u.id: u.email for u in rows}

    result = []
    for c in comments:
        email = users_by_id.get(c.author_id, "[deleted user]") if c.author_id else "[deleted user]"
        result.append(
            TaskCommentResponse(
                id=c.id,
                task_id=c.task_id,
                author_id=c.author_id,
                author_email=email,
                body=c.body,
                is_edited=c.edited_at is not None,
                created_at=c.created_at,
                edited_at=c.edited_at,
            )
        )
    return result


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
def create_task_comment(
    task_id: UUID,
    payload: TaskCommentCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="member")

    comment = TaskComment(
        task_id=task_id,
        author_id=current_user.id,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return TaskCommentResponse(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        author_email=db.get(User, current_user.id).email,
        body=comment.body,
        is_edited=False,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
    )


@router.put("/{task_id}/comments/{comment_id}", response_model=TaskCommentResponse)
def update_task_comment(
    task_id: UUID,
    comment_id: UUID,
    payload: TaskCommentUpdate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_task_access(task_id, current_user, db, min_role="member")

    comment = db.get(TaskComment, comment_id)
    if comment is None or comment.task_id != task_id:
        raise NotFound("Comment")

    if comment.author_id != current_user.id:
        raise Forbidden("insufficient permissions")

    comment.body = payload.body
    comment.edited_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)

    return TaskCommentResponse(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        author_email=db.get(User, current_user.id).email,
        body=comment.body,
        is_edited=True,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
    )


@router.delete("/{task_id}/comments/{comment_id}", status_code=204)
def delete_task_comment(
    task_id: UUID,
    comment_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    task = ensure_task_access(task_id, current_user, db, min_role="member")

    comment = db.get(TaskComment, comment_id)
    if comment is None or comment.task_id != task_id:
        raise NotFound("Comment")

    # Author can always delete their own comment
    if comment.author_id == current_user.id:
        db.delete(comment)
        db.commit()
        return Response(status_code=204)

    # Non-author: check if workspace admin or owner (D-09)
    project = db.get(Project, task.project_id)
    workspace = db.get(Workspace, project.workspace_id)

    # Workspace owner passthrough (mirrors ensure_workspace_access logic)
    if workspace.owner_id == current_user.id:
        db.delete(comment)
        db.commit()
        return Response(status_code=204)

    # Check workspace membership role
    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == current_user.id,
        )
    )
    if membership and WORKSPACE_ROLE_PRIORITY.get(membership.role, 0) >= WORKSPACE_ROLE_PRIORITY["admin"]:
        db.delete(comment)
        db.commit()
        return Response(status_code=204)

    raise Forbidden("insufficient permissions")
