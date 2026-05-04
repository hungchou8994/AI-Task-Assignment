import pytest

from app.config import get_settings
from app.services.memory_policy import MemoryClass, MemoryScope, resolve_policy


def test_resolve_policy_for_extraction_uses_expected_classes(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_allowed_scope_widening", True)

    decision = resolve_policy(
        action="extraction",
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id="proj-1"),
        role="system",
    )

    assert decision.initial_scope == "project"
    assert decision.allow_scope_widening is True
    assert decision.allowed_classes == (
        MemoryClass.extraction_patterns,
        MemoryClass.review_feedback,
        MemoryClass.project_glossary,
    )


def test_resolve_policy_workspace_scope_without_project(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_allowed_scope_widening", True)

    decision = resolve_policy(
        action="review",
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id=None),
        role="member",
    )

    assert decision.initial_scope == "workspace"
    assert decision.allow_scope_widening is False
    assert decision.allowed_classes == (
        MemoryClass.review_feedback,
        MemoryClass.project_glossary,
    )


def test_resolve_policy_disables_widening_when_setting_off(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "memory_allowed_scope_widening", False)

    decision = resolve_policy(
        action="recommendation",
        scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id="proj-1"),
        role="admin",
    )

    assert decision.allow_scope_widening is False


def test_resolve_policy_rejects_unknown_action():
    with pytest.raises(ValueError):
        resolve_policy(
            action="unknown",
            scope=MemoryScope(org_id="org-1", workspace_id="ws-1", project_id="proj-1"),
            role="system",
        )
