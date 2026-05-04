from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.config import get_settings


class MemoryClass(str, Enum):
    extraction_patterns = "extraction_patterns"
    review_feedback = "review_feedback"
    assignee_outcomes = "assignee_outcomes"
    project_glossary = "project_glossary"
    operational_incidents = "operational_incidents"


@dataclass(frozen=True)
class MemoryScope:
    org_id: str
    workspace_id: str
    project_id: str | None = None


@dataclass(frozen=True)
class MemoryPolicyDecision:
    allowed_classes: tuple[MemoryClass, ...]
    allow_scope_widening: bool
    initial_scope: str


_ACTION_CLASS_ALLOWLIST: dict[str, tuple[MemoryClass, ...]] = {
    "extraction": (
        MemoryClass.extraction_patterns,
        MemoryClass.review_feedback,
        MemoryClass.project_glossary,
    ),
    "recommendation": (
        MemoryClass.assignee_outcomes,
        MemoryClass.review_feedback,
    ),
    "review": (
        MemoryClass.review_feedback,
        MemoryClass.project_glossary,
    ),
}

_WIDENING_ROLES = {"owner", "admin", "system"}


def resolve_policy(action: str, scope: MemoryScope, role: str) -> MemoryPolicyDecision:
    if not scope.org_id or not scope.workspace_id:
        raise ValueError("MemoryScope requires org_id and workspace_id")

    normalized_action = action.strip().lower()
    if normalized_action not in _ACTION_CLASS_ALLOWLIST:
        raise ValueError(f"Unsupported memory action: {action}")

    settings = get_settings()
    normalized_role = role.strip().lower() or "member"
    allow_scope_widening = (
        settings.memory_allowed_scope_widening and normalized_role in _WIDENING_ROLES
    )

    return MemoryPolicyDecision(
        allowed_classes=_ACTION_CLASS_ALLOWLIST[normalized_action],
        allow_scope_widening=allow_scope_widening,
        initial_scope="project" if scope.project_id else "workspace",
    )
