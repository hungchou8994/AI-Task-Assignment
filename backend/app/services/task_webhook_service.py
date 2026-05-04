from __future__ import annotations

import asyncio
from enum import Enum
import logging
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models import Project, Task
from app.services.webhook_service import trigger_webhooks

logger = logging.getLogger(__name__)


def build_task_webhook_payload(task: Task, event_type: str) -> dict:
    return {
        "event_type": event_type,
        "task": {
            "id": str(task.id),
            "title": task.title,
            "status": task.status.value
            if isinstance(task.status, Enum)
            else str(task.status),
            "project_id": str(task.project_id),
            "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        },
    }


async def trigger_task_webhook(
    db: Session,
    task: Task,
    event_type: str = "task.created",
) -> None:
    project = db.get(Project, task.project_id)
    if not project:
        return

    await trigger_webhooks(
        db,
        project.workspace_id,
        event_type,
        task.id,
        build_task_webhook_payload(task, event_type),
    )


async def trigger_task_webhook_by_id(
    db: Session,
    task_id: UUID,
    event_type: str = "task.created",
) -> None:
    task = db.get(Task, task_id)
    if task is None:
        return
    await trigger_task_webhook(db, task, event_type)


def trigger_task_webhook_by_id_sync(
    db: Session,
    task_id: UUID,
    event_type: str = "task.created",
) -> None:
    try:
        asyncio.run(trigger_task_webhook_by_id(db, task_id, event_type))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Task webhook dispatch failed for task %s: %s",
            task_id,
            exc,
        )


def enqueue_task_webhook(
    db: Session,
    task: Task,
    event_type: str,
    background_tasks: BackgroundTasks,
) -> None:
    background_tasks.add_task(trigger_task_webhook_by_id, db, task.id, event_type)
