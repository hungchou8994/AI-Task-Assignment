from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from app.config import get_settings
from app.jobs import memory_ingestion_job
from app.models import MemoryAuditEvent, TaskCandidate, TaskPriority
from tests.helpers import make_project, make_workspace


def test_ingest_candidate_event_mines_redacted_payload(monkeypatch, client):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)

    workspace = make_workspace(client)
    project = make_project(client, workspace_id=workspace["id"])

    candidate = TaskCandidate(
        project_id=UUID(project["id"]),
        title="Reach customer",
        description="Contact jane@example.com for update",
        priority=TaskPriority.high,
        due_date=None,
        selected_assignee_id=None,
        confidence_score=0.88,
        source_type="text",
        source_excerpt="excerpt",
        source_summary="summary",
        assignee_recommendations=[],
    )
    client.db.add(candidate)
    client.db.commit()
    client.db.refresh(candidate)

    captured: dict = {}

    def fake_mine(self, payload, scope, class_name):
        captured["payload"] = payload
        captured["scope"] = scope
        captured["class_name"] = class_name
        return SimpleNamespace(status="ok", mined_count=1)

    class _DbProxy:
        def __init__(self, inner):
            self._inner = inner

        def close(self):
            return None

        def __getattr__(self, item):
            return getattr(self._inner, item)

    monkeypatch.setattr(memory_ingestion_job.MemoryService, "mine", fake_mine)
    monkeypatch.setattr(
        memory_ingestion_job, "get_db", lambda: iter([_DbProxy(client.db)])
    )

    memory_ingestion_job.ingest_candidate_event(
        str(candidate.id),
        event_type="candidate.edited",
        actor_id=str(client.current_user.id),
        field_deltas={"description": {"original": "x", "final": "jane@example.com"}},
    )

    assert captured["class_name"] == "review_feedback"
    assert "[REDACTED_EMAIL]" in captured["payload"]["description"]
    assert (
        captured["payload"]["field_deltas"]["description"]["final"]
        == "[REDACTED_EMAIL]"
    )

    events = (
        client.db.query(MemoryAuditEvent)
        .filter(MemoryAuditEvent.action == "mine")
        .all()
    )
    assert len(events) == 1
    assert events[0].status == "ok"


def test_ingest_candidate_event_noop_when_memory_disabled(monkeypatch, client):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", False)

    called = {"value": False}

    def fake_mine(self, payload, scope, class_name):
        called["value"] = True
        return SimpleNamespace(status="ok", mined_count=1)

    class _DbProxy:
        def __init__(self, inner):
            self._inner = inner

        def close(self):
            return None

        def __getattr__(self, item):
            return getattr(self._inner, item)

    monkeypatch.setattr(memory_ingestion_job.MemoryService, "mine", fake_mine)
    monkeypatch.setattr(
        memory_ingestion_job, "get_db", lambda: iter([_DbProxy(client.db)])
    )

    memory_ingestion_job.ingest_candidate_event(
        "00000000-0000-0000-0000-000000000001",
        event_type="candidate.approved",
        actor_id=str(client.current_user.id),
        field_deltas={},
    )

    assert called["value"] is False
