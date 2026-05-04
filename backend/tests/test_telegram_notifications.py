import asyncio
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import BackgroundTasks

from app.config import get_settings
from app.models import (
    CandidateStatus,
    Organization,
    Project,
    Task,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
    Workspace,
)
from app.routers import task_candidates, tasks
from app.services.telegram_notification_service import (
    _build_project_tasks_url,
    notify_candidate_approved,
    notify_task_created,
    notify_task_updated,
)
from tests.helpers import create_test_db


def test_build_project_tasks_url_includes_workspace_and_task(monkeypatch):
    db, current_user, cleanup = create_test_db()
    try:
        org = Organization(name="Test Org", slug="test-org-telegram-link", settings={})
        db.add(org)
        db.commit()

        workspace = Workspace(name="Test Workspace", org_id=org.id, owner_id=current_user.id)
        db.add(workspace)
        db.commit()

        project = Project(name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.commit()

        settings = get_settings()
        monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

        url = _build_project_tasks_url(project.id, "task-123")
        assert url == f"http://localhost:3000/{workspace.id}/tasks?task=task-123"
    finally:
        cleanup()


def test_candidate_approved_triggers_telegram_notification(monkeypatch):
    db, current_user, cleanup = create_test_db()
    try:
        org = Organization(name="Test Org", slug="test-org-telegram-approve", settings={})
        db.add(org)
        db.commit()

        workspace = Workspace(name="Test Workspace", org_id=org.id, owner_id=current_user.id)
        db.add(workspace)
        db.commit()

        project = Project(name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.commit()

        candidate = TaskCandidate(
            project_id=project.id,
            title="Review queue task",
            description="Needs approval",
            priority=TaskPriority.high,
            confidence_score=0.9,
            source_type="text",
            source_summary="Summary",
            assignee_recommendations=[],
            status=CandidateStatus.pending,
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        settings = get_settings()
        monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
        monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
        monkeypatch.setattr(settings, "telegram_chat_id", "123456")
        monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

        background_tasks = BackgroundTasks()
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            task_candidates.approve_candidate(
                candidate_id=candidate.id,
                db=db,
                current_user=current_user,
                background_tasks=background_tasks,
            )

            for queued in background_tasks.tasks:
                result = queued()
                if asyncio.iscoroutine(result):
                    asyncio.run(result)

        telegram_calls = [
            call for call in mock_post.call_args_list if call[0] and "api.telegram.org" in call[0][0]
        ]
        assert len(telegram_calls) == 1
        _, kwargs = telegram_calls[0]
        assert kwargs["json"]["chat_id"] == "123456"
        assert "Review queue approved" in kwargs["json"]["text"]
        assert "reply_markup" not in kwargs["json"]
    finally:
        cleanup()


def test_task_updated_triggers_telegram_notification(monkeypatch):
    db, current_user, cleanup = create_test_db()
    try:
        org = Organization(name="Test Org", slug="test-org-telegram-update", settings={})
        db.add(org)
        db.commit()

        workspace = Workspace(name="Test Workspace", org_id=org.id, owner_id=current_user.id)
        db.add(workspace)
        db.commit()

        project = Project(name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.commit()

        task = Task(
            title="Telegram update task",
            status=TaskStatus.todo,
            priority=TaskPriority.medium,
            project_id=project.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        settings = get_settings()
        monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
        monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
        monkeypatch.setattr(settings, "telegram_chat_id", "123456")
        monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

        background_tasks = BackgroundTasks()
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            tasks.update_task(
                task_id=task.id,
                payload=tasks.TaskUpdate(status=TaskStatus.in_progress),
                db=db,
                current_user=current_user,
                background_tasks=background_tasks,
            )

            for queued in background_tasks.tasks:
                result = queued()
                if asyncio.iscoroutine(result):
                    asyncio.run(result)

        telegram_calls = [
            call for call in mock_post.call_args_list if call[0] and "api.telegram.org" in call[0][0]
        ]
        assert len(telegram_calls) == 1
        _, kwargs = telegram_calls[0]
        assert "Task updated" in kwargs["json"]["text"]
        assert "reply_markup" not in kwargs["json"]
    finally:
        cleanup()


def test_task_created_triggers_telegram_notification(monkeypatch):
    db, current_user, cleanup = create_test_db()
    try:
        org = Organization(name="Test Org", slug="test-org-telegram-create", settings={})
        db.add(org)
        db.commit()

        workspace = Workspace(name="Test Workspace", org_id=org.id, owner_id=current_user.id)
        db.add(workspace)
        db.commit()

        project = Project(name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.commit()

        settings = get_settings()
        monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
        monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
        monkeypatch.setattr(settings, "telegram_chat_id", "123456")
        monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

        background_tasks = BackgroundTasks()
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            created = tasks.create_task(
                payload=tasks.TaskCreate(
                    title="Telegram created task",
                    project_id=project.id,
                    priority=TaskPriority.medium,
                ),
                db=db,
                current_user=current_user,
                background_tasks=background_tasks,
            )

            for queued in background_tasks.tasks:
                result = queued()
                if asyncio.iscoroutine(result):
                    asyncio.run(result)

        telegram_calls = [
            call for call in mock_post.call_args_list if call[0] and "api.telegram.org" in call[0][0]
        ]
        assert len(telegram_calls) == 1
        _, kwargs = telegram_calls[0]
        assert "Task created" in kwargs["json"]["text"]
        assert "reply_markup" not in kwargs["json"]
    finally:
        cleanup()


def test_notify_candidate_approved_can_send_directly(monkeypatch):
    task = Task(
        title="Review queue task",
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    candidate = TaskCandidate(
        title="Candidate title",
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
        priority=TaskPriority.high,
        confidence_score=0.9,
        source_type="text",
        source_summary="Summary",
        assignee_recommendations=[],
        status=CandidateStatus.pending,
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

    with patch("httpx.AsyncClient.post") as mock_post, patch(
        "app.services.telegram_notification_service._resolve_workspace_id",
        return_value="workspace-1",
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        asyncio.run(notify_candidate_approved(task, candidate))

    assert mock_post.call_count == 1


def test_notify_task_updated_can_send_directly(monkeypatch):
    task = Task(
        title="Task updated title",
        status=TaskStatus.in_progress,
        priority=TaskPriority.medium,
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

    with patch("httpx.AsyncClient.post") as mock_post, patch(
        "app.services.telegram_notification_service._resolve_workspace_id",
        return_value="workspace-1",
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        asyncio.run(notify_task_updated(task))

    assert mock_post.call_count == 1


def test_notify_task_created_can_send_directly(monkeypatch):
    task = Task(
        title="Task created title",
        status=TaskStatus.todo,
        priority=TaskPriority.medium,
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    monkeypatch.setattr(settings, "app_base_url", "http://localhost:3000")

    with patch("httpx.AsyncClient.post") as mock_post, patch(
        "app.services.telegram_notification_service._resolve_workspace_id",
        return_value="workspace-1",
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        asyncio.run(notify_task_created(task))

    assert mock_post.call_count == 1


def test_notify_task_created_includes_button_for_public_base_url(monkeypatch):
    task = Task(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        title="Task created title",
        status=TaskStatus.todo,
        priority=TaskPriority.medium,
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_notifications_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    monkeypatch.setattr(settings, "app_base_url", "https://demo.example.com")

    with patch("httpx.AsyncClient.post") as mock_post, patch(
        "app.services.telegram_notification_service._resolve_workspace_id",
        return_value="workspace-1",
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        asyncio.run(notify_task_created(task))

    assert mock_post.call_count == 1
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["reply_markup"]["inline_keyboard"][0][0]["url"] == (
        "https://demo.example.com/workspace-1/tasks?task="
        "00000000-0000-0000-0000-000000000000"
    )
