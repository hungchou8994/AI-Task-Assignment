import asyncio
import json
import uuid
from unittest.mock import MagicMock, patch
from uuid import UUID

from fastapi import BackgroundTasks

from app.models import CandidateStatus, Task
from app.routers import task_candidates
from app.ai.agent_extraction.extraction_agent import AgentRunResult
from app.ai.gemini_client import ExtractionResult
from app.config import get_settings
from app.models import (
    MemoryAuditEvent,
    Person,
    Project,
    TaskCandidate,
    WebhookDelivery,
    WebhookSubscription,
    Workspace,
)
from app.schemas import ExtractTasksCommand
from app.services import extraction_service
from app.services.memory_context_builder import MemoryContextBuildResult
from app.services.memory_policy import MemoryScope


def test_extract_tasks_passes_full_text_payload_to_agent(monkeypatch, client):
    captured: dict = {}

    async def fake_run(user_prompt, system_prompt, **kwargs):
        captured.update(kwargs)
        return AgentRunResult(
            finalized=ExtractionResult(source_summary="summary", tasks=[]),
            created_task_ids=[],
        )

    monkeypatch.setattr(extraction_service, "run_autonomous_extraction_async", fake_run)

    command = ExtractTasksCommand(
        source_type="text",
        content="Full source text should persist",
        project_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
    )

    asyncio.run(extraction_service.extract_tasks(client.db, command))

    assert captured["source_uri"] is None
    assert captured["source_payload"] == {"raw_text": "Full source text should persist"}


def test_extract_tasks_passes_url_and_fetched_text_payload_to_agent(
    monkeypatch, client
):
    captured: dict = {}

    async def fake_run(user_prompt, system_prompt, **kwargs):
        captured.update(kwargs)
        return AgentRunResult(
            finalized=ExtractionResult(source_summary="summary", tasks=[]),
            created_task_ids=[],
        )

    monkeypatch.setattr(extraction_service, "run_autonomous_extraction_async", fake_run)
    monkeypatch.setattr(
        extraction_service, "preprocess", lambda _t, _c: "Fetched URL body"
    )

    source_url = "https://example.com/docs"
    command = ExtractTasksCommand(
        source_type="url",
        content=source_url,
        project_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
    )

    asyncio.run(extraction_service.extract_tasks(client.db, command))

    assert captured["source_uri"] == source_url
    assert captured["source_payload"] == {"fetched_text": "Fetched URL body"}


def test_extract_tasks_appends_memory_context_when_enabled(monkeypatch, client):
    captured: dict = {}

    async def fake_run(user_prompt, system_prompt, **kwargs):  # noqa: ARG001
        captured["user_prompt"] = user_prompt
        return AgentRunResult(
            finalized=ExtractionResult(source_summary="summary", tasks=[]),
            created_task_ids=[],
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(
        extraction_service,
        "build_extraction_memory_bundle",
        lambda _db, _cmd: MemoryContextBuildResult(
            context="## MEMORY CONTEXT\n- [class=review_feedback] tip",
            scope=None,
            query="input text",
            result_count=1,
            latency_ms=5,
        ),
    )
    monkeypatch.setattr(extraction_service, "run_autonomous_extraction_async", fake_run)

    command = ExtractTasksCommand(
        source_type="text",
        content="Input text",
        project_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
    )

    asyncio.run(extraction_service.extract_tasks(client.db, command))
    assert "## MEMORY CONTEXT" in captured["user_prompt"]


def test_extract_tasks_memory_failure_is_fail_open(monkeypatch, client):
    captured: dict = {}

    async def fake_run(user_prompt, system_prompt, **kwargs):  # noqa: ARG001
        captured["called"] = True
        captured["user_prompt"] = user_prompt
        return AgentRunResult(
            finalized=ExtractionResult(source_summary="summary", tasks=[]),
            created_task_ids=[],
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)

    def _raise_memory_error(_db, _cmd):
        raise RuntimeError("memory unavailable")

    monkeypatch.setattr(
        extraction_service,
        "build_extraction_memory_bundle",
        _raise_memory_error,
    )
    monkeypatch.setattr(extraction_service, "run_autonomous_extraction_async", fake_run)

    command = ExtractTasksCommand(
        source_type="text",
        content="Input text",
        project_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
    )

    asyncio.run(extraction_service.extract_tasks(client.db, command))

    assert captured["called"] is True
    assert "## MEMORY CONTEXT" not in captured["user_prompt"]


def test_extract_tasks_logs_memory_search_and_injection(monkeypatch, client):
    captured: dict = {}

    workspace = client.post("/api/workspaces", json={"name": "W-memory-audit"}).json()
    project = client.post(
        f"/api/workspaces/{workspace['id']}/projects",
        json={"name": "P-memory-audit"},
    ).json()
    scope_row = (
        client.db.query(Project.id, Workspace.id, Workspace.org_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .filter(Project.id == UUID(project["id"]))
        .one()
    )
    scope = MemoryScope(
        org_id=str(scope_row[2]),
        workspace_id=str(scope_row[1]),
        project_id=str(scope_row[0]),
    )

    async def fake_run(user_prompt, system_prompt, **kwargs):  # noqa: ARG001
        captured["user_prompt"] = user_prompt
        return AgentRunResult(
            finalized=ExtractionResult(source_summary="summary", tasks=[]),
            created_task_ids=[],
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(
        extraction_service,
        "build_extraction_memory_bundle",
        lambda _db, _cmd: MemoryContextBuildResult(
            context="## MEMORY CONTEXT\n- [class=review_feedback] tip",
            scope=scope,
            query="ship launch",
            result_count=1,
            latency_ms=8,
        ),
    )
    monkeypatch.setattr(extraction_service, "run_autonomous_extraction_async", fake_run)

    command = ExtractTasksCommand(
        source_type="text",
        content="Input text",
        project_id=project["id"],
        job_id=str(uuid.uuid4()),
    )

    asyncio.run(extraction_service.extract_tasks(client.db, command))
    client.db.commit()

    events = (
        client.db.query(MemoryAuditEvent)
        .order_by(MemoryAuditEvent.created_at.asc(), MemoryAuditEvent.id.asc())
        .all()
    )
    by_action = {event.action: event for event in events}
    assert set(by_action) == {"search", "inject"}
    assert by_action["search"].result_count == 1
    assert by_action["search"].latency_ms == 8
    assert "## MEMORY CONTEXT" in captured["user_prompt"]


def test_create_tasks_creates_review_candidate_then_approval_triggers_webhook(client):
    from app.ai.agent import RunContext
    from app.ai.agent_extraction.tools import ExtractionDeps, create_tasks

    workspace = client.post("/api/workspaces", json={"name": "W-webhook-ai"}).json()
    project = client.post(
        f"/api/workspaces/{workspace['id']}/projects",
        json={"name": "P-webhook-ai"},
    ).json()

    subscription = WebhookSubscription(
        workspace_id=UUID(workspace["id"]),
        event_type="task.created",
        target_url="https://example.com/webhook",
        secret="secret",
        is_active=True,
    )
    client.db.add(subscription)
    client.db.commit()

    deps = ExtractionDeps(
        raw_text=f"Create a follow-up task {uuid.uuid4()}",
        db=client.db,
        project_id=project["id"],
        source_type="text",
        source_excerpt="Create a follow-up task",
    )
    ctx = RunContext(deps=deps, agent_name="test")

    with patch("httpx.AsyncClient.post") as mock_post:
        result = asyncio.run(
            create_tasks.execute(
                ctx,
                {
                    "source_summary": "AI extracted one task",
                    "tasks": [
                        {
                            "title": "Follow up on AI extraction",
                            "description": "Created by the AI extraction pipeline",
                            "priority": "medium",
                            "confidence_score": 0.8,
                        }
                    ],
                },
            )
        )

    parsed = json.loads(result)
    assert parsed["ok"] is True
    assert parsed["created"][0]["task_id"] is None
    candidate_id = UUID(parsed["created"][0]["task_candidate_id"])
    candidate = client.db.get(TaskCandidate, candidate_id)
    assert candidate.status == CandidateStatus.pending
    assert candidate.approved_task_id is None
    assert client.db.query(Task).filter(Task.title == "Follow up on AI extraction").count() == 0
    mock_post.assert_not_called()

    background_tasks = BackgroundTasks()
    approved = task_candidates.approve_candidate(
        candidate_id=candidate_id,
        db=client.db,
        current_user=client.current_user,
        background_tasks=background_tasks,
    )
    task_id = approved.task_id

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        for task in background_tasks.tasks:
            if getattr(task.func, "__name__", "") == "trigger_task_webhook_by_id":
                asyncio.run(task())

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["X-Webhook-Event-Id"] == str(task_id)
    assert '"event_type": "task.created"' in kwargs["content"]
    assert str(task_id) in kwargs["content"]

    delivery = (
        client.db.query(WebhookDelivery)
        .filter(WebhookDelivery.subscription_id == subscription.id)
        .first()
    )
    assert delivery is not None
    assert delivery.status == "success"
    assert delivery.event_id == task_id


def test_recommend_assignees_normalizes_name_person_id(client):
    from app.ai.agent import RunContext
    from app.ai.agent_extraction.tools import ExtractionDeps, create_tasks, recommend_assignees

    workspace = client.post("/api/workspaces", json={"name": "W-recs"}).json()
    project = client.post(
        f"/api/workspaces/{workspace['id']}/projects",
        json={"name": "P-recs"},
    ).json()
    person = Person(name="Ethan Brooks", email="ethan.recs@example.com")
    client.db.add(person)
    client.db.commit()
    client.db.refresh(person)

    deps = ExtractionDeps(
        raw_text=f"Create a backend task {uuid.uuid4()}",
        db=client.db,
        project_id=project["id"],
        source_type="text",
        source_excerpt="Create a backend task",
    )
    ctx = RunContext(deps=deps, agent_name="test")
    created = json.loads(
        asyncio.run(
            create_tasks.execute(
                ctx,
                {
                    "source_summary": "AI extracted one task",
                    "tasks": [
                        {
                            "title": "Backend task",
                            "priority": "high",
                            "confidence_score": 0.9,
                        }
                    ],
                },
            )
        )
    )
    candidate_id = UUID(created["created"][0]["task_candidate_id"])

    result = json.loads(
        asyncio.run(
            recommend_assignees.execute(
                ctx,
                {
                    "assignments": [
                        {
                            "task_candidate_id": str(candidate_id),
                            "recommendations": [
                                {
                                    "rank": 1,
                                    "person_id": "ethan brooks",
                                    "name": "Ethan Brooks",
                                    "confidence_score": 0.9,
                                    "reasoning": "Best backend fit",
                                }
                            ],
                        }
                    ]
                },
            )
        )
    )

    assert result["ok"] is True
    candidate = client.db.get(TaskCandidate, candidate_id)
    assert candidate.assignee_recommendations[0]["person_id"] == str(person.id)
    assert candidate.selected_assignee_id == person.id
