"""Service for creating Tasks from TaskCandidates.

Both the auto-creation path (extraction pipeline) and the manual-approval path
(task_candidates router) produce identical Task rows from a TaskCandidate.
This module centralises that logic so a change to the creation logic only needs
to happen in one place.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Task,
    TaskActivityAction,
    TaskActivityEvent,
    TaskCandidate,
    TaskStatus,
)


def create_task_from_candidate(
    db: Session,
    candidate: TaskCandidate,
    *,
    actor_type: str,
    actor_label: str,
) -> Task:
    """Persist a new Task built from *candidate* and write its creation event.

    Args:
        db: Active SQLAlchemy session.
        candidate: The source candidate; must already be flushed (has an ``id``).
        actor_type: ``"system"`` for auto-creation, ``"user"`` for manual approval.
        actor_label: Free-form label recorded in the activity event for auditing.

    Returns:
        The newly created and flushed ``Task`` instance.  The caller is
        responsible for committing the session.
    """
    task = Task(
        title=candidate.title,
        description=candidate.description,
        status=TaskStatus.todo,
        priority=candidate.priority,
        due_date=candidate.due_date,
        assignee_id=candidate.selected_assignee_id,
        project_id=candidate.project_id,
        needs_review=False,
    )
    db.add(task)
    db.flush()

    db.add(
        TaskActivityEvent(
            task_id=task.id,
            project_id=task.project_id,
            action_type=TaskActivityAction.task_created,
            actor_type=actor_type,
            actor_label=actor_label,
            occurred_at=datetime.now(timezone.utc),
        )
    )
    return task
