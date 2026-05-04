from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.config import get_settings
from app.schemas import ExtractTasksCommand
from app.services import memory_context_builder
from tests.helpers import make_project, make_workspace


def test_build_extraction_memory_context_prefers_ranked_project_hits(
    monkeypatch, client
):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(settings, "memory_default_results", 5)
    monkeypatch.setattr(settings, "memory_max_context_chars", 1000)

    workspace = make_workspace(client)
    project = make_project(client, workspace_id=workspace["id"])

    now = datetime.now(tz=timezone.utc)
    older = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    newer = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    def fake_search(self, query, scope, classes, k):  # noqa: ARG001
        assert scope.project_id == project["id"]
        return SimpleNamespace(
            hits=(
                memory_context_builder.MemoryHit(
                    class_name="review_feedback",
                    fact="Prefer measurable acceptance criteria.",
                    confidence_score=0.9,
                    project_id=project["id"],
                    timestamp=older,
                ),
                memory_context_builder.MemoryHit(
                    class_name="extraction_patterns",
                    fact="Split bundled asks into separate tasks.",
                    confidence_score=0.6,
                    project_id=project["id"],
                    timestamp=newer,
                ),
            )
        )

    monkeypatch.setattr(memory_context_builder.MemoryService, "search", fake_search)

    command = ExtractTasksCommand(
        source_type="text",
        content="Review new launch prep and split follow-ups.",
        project_id=project["id"],
        job_id=None,
    )
    context = memory_context_builder.build_extraction_memory_context(client.db, command)

    assert context.startswith("## MEMORY CONTEXT")
    first_line = context.splitlines()[1]
    assert "class=extraction_patterns" in first_line


def test_build_extraction_memory_context_widens_scope_once_when_project_recall_low(
    monkeypatch, client
):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(settings, "memory_default_results", 5)
    monkeypatch.setattr(settings, "memory_max_context_chars", 1000)
    monkeypatch.setattr(settings, "memory_allowed_scope_widening", True)

    workspace = make_workspace(client)
    project = make_project(client, workspace_id=workspace["id"])

    calls: list[str] = []

    def fake_search(self, query, scope, classes, k):  # noqa: ARG001
        if scope.project_id:
            calls.append("project")
            return SimpleNamespace(hits=())
        calls.append("workspace")
        return SimpleNamespace(
            hits=(
                memory_context_builder.MemoryHit(
                    class_name="review_feedback",
                    fact="Reviewer asked for explicit owner field.",
                    confidence_score=0.8,
                    project_id=None,
                    timestamp="2026-01-01T00:00:00Z",
                ),
            )
        )

    monkeypatch.setattr(memory_context_builder.MemoryService, "search", fake_search)

    command = ExtractTasksCommand(
        source_type="text",
        content="Owner missing in draft tasks",
        project_id=project["id"],
        job_id=None,
    )
    context = memory_context_builder.build_extraction_memory_context(client.db, command)

    assert calls == ["project", "workspace"]
    assert "explicit owner field" in context


def test_build_extraction_memory_context_applies_character_budget(monkeypatch, client):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(settings, "memory_default_results", 5)
    monkeypatch.setattr(settings, "memory_max_context_chars", 220)

    workspace = make_workspace(client)
    project = make_project(client, workspace_id=workspace["id"])

    def fake_search(self, query, scope, classes, k):  # noqa: ARG001
        return SimpleNamespace(
            hits=(
                memory_context_builder.MemoryHit(
                    class_name="review_feedback",
                    fact="Very long memory fact " * 20,
                    confidence_score=0.9,
                    project_id=project["id"],
                    timestamp="2026-01-01T00:00:00Z",
                ),
                memory_context_builder.MemoryHit(
                    class_name="project_glossary",
                    fact="Short fallback fact.",
                    confidence_score=0.5,
                    project_id=project["id"],
                    timestamp="2026-01-01T00:00:00Z",
                ),
            )
        )

    monkeypatch.setattr(memory_context_builder.MemoryService, "search", fake_search)

    command = ExtractTasksCommand(
        source_type="text",
        content="Need compact context",
        project_id=project["id"],
        job_id=None,
    )
    context = memory_context_builder.build_extraction_memory_context(client.db, command)

    assert len(context) <= 220
    assert "Short fallback fact." in context
    assert "Very long memory fact" not in context
