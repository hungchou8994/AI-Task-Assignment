from __future__ import annotations

import html
import logging
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.models import Project, Task, TaskCandidate

logger = logging.getLogger(__name__)


async def notify_candidate_approved(task: Task, candidate: TaskCandidate | None) -> None:
    if not _is_enabled():
        return
    try:
        project_link = _build_project_tasks_url(task.project_id, task.id)
        lines = [
            "<b>Review queue approved</b>",
            f"<b>Task:</b> {html.escape(task.title)}",
            f"<b>Status:</b> {html.escape(task.status.value)}",
            f"<b>Priority:</b> {html.escape(task.priority.value)}",
        ]
        if candidate is not None:
            lines.append(f"<b>Candidate:</b> <code>{candidate.id}</code>")
            if candidate.selected_assignee_id:
                lines.append(
                    f"<b>Assignee:</b> <code>{candidate.selected_assignee_id}</code>"
                )
        await _send_message(
            text="\n".join(lines),
            button_text="Open approved task",
            button_url=project_link,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telegram candidate approval notification failed for task %s: %s",
            task.id,
            exc,
        )


async def notify_task_created(task: Task) -> None:
    if not _is_enabled():
        return
    try:
        await _send_message(
            text="\n".join(
                [
                    "<b>Task created</b>",
                    f"<b>Task:</b> {html.escape(task.title)}",
                    f"<b>Status:</b> {html.escape(task.status.value)}",
                    f"<b>Priority:</b> {html.escape(task.priority.value)}",
                ]
            ),
            button_text="Open task",
            button_url=_build_project_tasks_url(task.project_id, task.id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telegram task creation notification failed for task %s: %s",
            task.id,
            exc,
        )


async def notify_task_updated(task: Task) -> None:
    if not _is_enabled():
        return
    try:
        await _send_message(
            text="\n".join(
                [
                    "<b>Task updated</b>",
                    f"<b>Task:</b> {html.escape(task.title)}",
                    f"<b>Status:</b> {html.escape(task.status.value)}",
                    f"<b>Priority:</b> {html.escape(task.priority.value)}",
                ]
            ),
            button_text="Open task",
            button_url=_build_project_tasks_url(task.project_id, task.id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Telegram task update notification failed for task %s: %s",
            task.id,
            exc,
        )


def _build_project_tasks_url(project_id, task_id) -> str:
    settings = get_settings()
    base = settings.app_base_url.rstrip("/")
    workspace_id = _resolve_workspace_id(project_id)
    if workspace_id:
        return f"{base}/{workspace_id}/tasks?task={task_id}"
    return f"{base}/tasks?task={task_id}"


def _resolve_workspace_id(project_id) -> str | None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        return str(project.workspace_id) if project else None
    finally:
        db.close()


def _is_enabled() -> bool:
    settings = get_settings()
    if not settings.telegram_notifications_enabled:
        return False
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning(
            "Telegram notifications enabled but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing"
        )
        return False
    return True


async def _send_message(*, text: str, button_text: str, button_url: str) -> None:
    settings = get_settings()
    api_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if _is_public_button_url(button_url):
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {
                        "text": button_text,
                        "url": button_url,
                    }
                ]
            ]
        }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(api_url, json=payload)
        response.raise_for_status()


def _is_public_button_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return False
    if not host:
        return False
    return host not in {"localhost", "127.0.0.1", "0.0.0.0"}
