from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from app.services.memory_policy import MemoryScope
from app.services.memory_service import MemoryService, MemoryServiceError


def test_memory_service_search_builds_scoped_safe_command(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout='{"hits": []}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    service = MemoryService()
    result = service.search(
        query="query text",
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id="proj-1"),
        classes=["review_feedback", "project_glossary"],
        k=3,
    )

    assert result.status == "ok"
    assert result.hits == ()
    assert captured["command"] == [
        "mempalace",
        "--palace",
        "/app/.mempalace/org_org-1",
        "search",
        "query text",
        "--results",
        "3",
        "--wing",
        "ws-1",
        "--room",
        "review_feedback",
    ]


def test_memory_service_search_parses_json_hits(monkeypatch):
    payload = """
    {
      "hits": [
        {
          "class": "review_feedback",
          "fact": "Always ask for ticket links.",
          "confidence": 1.4,
          "project_id": "proj-1",
          "timestamp": "2026-01-01T00:00:00Z"
        }
      ]
    }
    """

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=payload, stderr=""
        ),
    )

    result = MemoryService().search(
        query="q",
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id="proj-1"),
        classes=["review_feedback"],
        k=5,
    )

    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.class_name == "review_feedback"
    assert hit.fact == "Always ask for ticket links."
    assert hit.confidence_score == 1.0
    assert hit.project_id == "proj-1"
    assert hit.timestamp == "2026-01-01T00:00:00Z"


def test_memory_service_search_falls_back_to_plain_text_lines(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="line one\nline two\n",
            stderr="",
        ),
    )

    result = MemoryService().search(
        query="q",
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id=None),
        classes=["extraction_patterns"],
        k=2,
    )

    assert [item.fact for item in result.hits] == ["line one", "line two"]
    assert [item.class_name for item in result.hits] == [
        "extraction_patterns",
        "extraction_patterns",
    ]


def test_memory_service_search_timeout_raises_structured_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="mempalace", timeout=20)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MemoryServiceError, match="timed out"):
        MemoryService().search(
            query="q",
            scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id=None),
            classes=["review_feedback"],
            k=1,
        )


def test_memory_service_mine_parses_mined_count(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"mined_count": 2}',
            stderr="",
        ),
    )

    result = MemoryService().mine(
        payload={"title": "x"},
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id="proj-1"),
        class_name="review_feedback",
    )

    assert result.status == "ok"
    assert result.mined_count == 1
