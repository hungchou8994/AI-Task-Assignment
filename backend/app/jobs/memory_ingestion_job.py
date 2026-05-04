from __future__ import annotations

import logging
import re
from uuid import UUID

from app.config import get_settings
from app.dependencies import get_db
from app.models import Project, TaskCandidate, Workspace
from app.services.memory_audit_service import MemoryAuditService
from app.services.memory_policy import MemoryScope
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|authorization)",
    flags=re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def ingest_candidate_event(
    candidate_id: str,
    *,
    event_type: str,
    actor_id: str | None,
    field_deltas: dict | None = None,
) -> None:
    settings = get_settings()
    if not settings.memory_enabled:
        return

    db = next(get_db())
    try:
        candidate = db.get(TaskCandidate, UUID(candidate_id))
        if candidate is None:
            logger.warning(
                "memory ingestion skipped; candidate not found: %s", candidate_id
            )
            return

        scope = _scope_from_project(db, str(candidate.project_id))
        payload = {
            "candidate_id": str(candidate.id),
            "project_id": str(candidate.project_id),
            "event_type": event_type,
            "title": candidate.title,
            "description": candidate.description,
            "priority": candidate.priority.value
            if hasattr(candidate.priority, "value")
            else str(candidate.priority),
            "selected_assignee_id": str(candidate.selected_assignee_id)
            if candidate.selected_assignee_id
            else None,
            "confidence_score": candidate.confidence_score,
            "field_deltas": field_deltas or {},
        }
        redacted_payload = _redact_payload(payload)
        class_name = _class_for_event(event_type)

        memory_service = MemoryService()
        audit_service = MemoryAuditService()
        try:
            mine_result = memory_service.mine(
                payload=redacted_payload,
                scope=scope,
                class_name=class_name,
            )
            audit_service.log_memory_mine(
                db,
                scope=scope,
                actor_type="user" if actor_id else "system",
                actor_id=actor_id,
                status=mine_result.status,
                metadata={
                    "event_type": event_type,
                    "class_name": class_name,
                    "mined_count": mine_result.mined_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory ingestion failed: %s", exc)
            audit_service.log_memory_error(
                db,
                scope=scope,
                action="mine",
                actor_type="user" if actor_id else "system",
                actor_id=actor_id,
                query=None,
                status="error",
                metadata={
                    "event_type": event_type,
                    "class_name": class_name,
                    "error": str(exc)[:500],
                },
            )

        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("memory ingestion job crashed")
    finally:
        db.close()


def _scope_from_project(db, project_id: str) -> MemoryScope:
    row = (
        db.query(Project.id, Workspace.id, Workspace.org_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .filter(Project.id == UUID(project_id))
        .one_or_none()
    )
    if row is None:
        raise ValueError(f"project not found for memory ingestion: {project_id}")
    return MemoryScope(
        org_id=str(row[2]), workspace_id=str(row[1]), project_id=str(row[0])
    )


def _class_for_event(event_type: str) -> str:
    if event_type in {"candidate.approved", "candidate.rejected"}:
        return "assignee_outcomes"
    if event_type == "candidate.edited":
        return "review_feedback"
    return "extraction_patterns"


def _redact_payload(value):
    if isinstance(value, dict):
        result = {}
        for key, raw in value.items():
            if _SENSITIVE_KEY_PATTERN.search(key):
                result[key] = "[REDACTED]"
            else:
                result[key] = _redact_payload(raw)
        return result
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, str):
        if _EMAIL_PATTERN.search(value):
            return _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
        return value
    return value
