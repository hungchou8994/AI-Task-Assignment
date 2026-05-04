from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import MemoryAuditEvent
from app.services.memory_policy import MemoryScope

logger = logging.getLogger(__name__)


class MemoryAuditService:
    def log_memory_search(
        self,
        db: Session,
        *,
        scope: MemoryScope,
        actor_type: str,
        actor_id: str | None,
        query: str,
        result_count: int,
        latency_ms: int,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._log_event(
            db,
            scope=scope,
            action="search",
            actor_type=actor_type,
            actor_id=actor_id,
            query_hash=self._hash_query(query),
            result_count=result_count,
            latency_ms=latency_ms,
            status=status,
            metadata=metadata or {},
        )

    def log_memory_injection(
        self,
        db: Session,
        *,
        scope: MemoryScope,
        actor_type: str,
        actor_id: str | None,
        query: str,
        result_count: int,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._log_event(
            db,
            scope=scope,
            action="inject",
            actor_type=actor_type,
            actor_id=actor_id,
            query_hash=self._hash_query(query),
            result_count=result_count,
            latency_ms=None,
            status=status,
            metadata=metadata or {},
        )

    def log_memory_mine(
        self,
        db: Session,
        *,
        scope: MemoryScope,
        actor_type: str,
        actor_id: str | None,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._log_event(
            db,
            scope=scope,
            action="mine",
            actor_type=actor_type,
            actor_id=actor_id,
            query_hash=None,
            result_count=None,
            latency_ms=None,
            status=status,
            metadata=metadata or {},
        )

    def log_memory_error(
        self,
        db: Session,
        *,
        scope: MemoryScope | None,
        action: str,
        actor_type: str,
        actor_id: str | None,
        query: str | None,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if scope is None:
            return
        self._log_event(
            db,
            scope=scope,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            query_hash=self._hash_query(query) if query else None,
            result_count=None,
            latency_ms=None,
            status=status,
            metadata=metadata or {},
        )

    def _log_event(
        self,
        db: Session,
        *,
        scope: MemoryScope,
        action: str,
        actor_type: str,
        actor_id: str | None,
        query_hash: str | None,
        result_count: int | None,
        latency_ms: int | None,
        status: str,
        metadata: dict[str, Any],
    ) -> None:
        try:
            db.add(
                MemoryAuditEvent(
                    org_id=UUID(scope.org_id),
                    workspace_id=UUID(scope.workspace_id),
                    project_id=UUID(scope.project_id) if scope.project_id else None,
                    action=action,
                    actor_type=actor_type,
                    actor_id=UUID(actor_id) if actor_id else None,
                    query_hash=query_hash,
                    result_count=result_count,
                    latency_ms=latency_ms,
                    status=status,
                    event_metadata=dict(metadata or {}),
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to write memory audit event")

    @staticmethod
    def _hash_query(query: str) -> str:
        return hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest()
