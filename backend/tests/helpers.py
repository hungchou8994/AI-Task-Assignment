"""Shared test infrastructure for backend tests.

Extracts duplicated utilities from conftest.py, test_task_candidates.py,
test_feedback_analytics.py, and test_task_activity.py.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse
from uuid import UUID

if TYPE_CHECKING:
    from app.schemas import ExtractedTaskItem

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, SessionLocal
from app.models import (
    CandidateApprovalEvent,
    CandidateSourceSpan,
    FeedbackEvent,
    Label,
    MemoryAuditEvent,
    Organization,
    OrgMembership,
    Person,
    Project,
    Task,
    TaskActivityEvent,
    TaskCandidate,
    TaskCandidateRevision,
    TaskComment,
    TaskDependency,
    TaskEstimate,
    TaskLabel,
    TaskStatusHistory,
    User,
    Workspace,
    WorkspaceMembership,
    WebhookSubscription,
    WebhookDelivery,
    Source,
    TaskSource,
)

# ---------------------------------------------------------------------------
# All tables used in test DB setup
# ---------------------------------------------------------------------------
ALL_TEST_TABLES = [
    User.__table__,
    Organization.__table__,
    OrgMembership.__table__,
    Workspace.__table__,
    WorkspaceMembership.__table__,
    Project.__table__,
    Person.__table__,
    Task.__table__,
    Label.__table__,
    TaskLabel.__table__,
    TaskStatusHistory.__table__,
    TaskEstimate.__table__,
    TaskDependency.__table__,
    TaskCandidate.__table__,
    FeedbackEvent.__table__,
    TaskActivityEvent.__table__,
    TaskComment.__table__,
    WebhookSubscription.__table__,
    WebhookDelivery.__table__,
    Source.__table__,
    TaskSource.__table__,
    TaskCandidateRevision.__table__,
    CandidateSourceSpan.__table__,
    CandidateApprovalEvent.__table__,
    MemoryAuditEvent.__table__,
]


# ---------------------------------------------------------------------------
# SQLite column patching (JSONB/ARRAY -> JSON for unit tests)
# ---------------------------------------------------------------------------

_sqlite_columns_patched = False


def patch_sqlite_columns():
    """Patch PostgreSQL-specific column types to SQLite-compatible JSON.

    This mutates the shared SQLAlchemy table metadata objects, which is a
    process-level side effect.  The patch is idempotent: calling it multiple
    times is safe.  It is intentionally applied once per process before any
    SQLite test engine is created.
    """
    global _sqlite_columns_patched  # noqa: PLW0603
    if _sqlite_columns_patched:
        return
    Organization.__table__.c.settings.type = JSON()
    Organization.__table__.c.settings.server_default = None
    Person.__table__.c.skills.type = JSON()
    TaskCandidate.__table__.c.assignee_recommendations.type = JSON()
    TaskCandidate.__table__.c.assignee_recommendations.server_default = None
    FeedbackEvent.__table__.c.field_deltas.type = JSON()
    FeedbackEvent.__table__.c.field_deltas.nullable = True
    FeedbackEvent.__table__.c.field_deltas.server_default = None
    FeedbackEvent.__table__.c["metadata"].type = JSON()
    FeedbackEvent.__table__.c["metadata"].nullable = True
    FeedbackEvent.__table__.c["metadata"].server_default = None
    TaskActivityEvent.__table__.c.before_value.type = JSON()
    TaskActivityEvent.__table__.c.after_value.type = JSON()
    TaskActivityEvent.__table__.c.event_metadata.type = JSON()
    TaskActivityEvent.__table__.c.event_metadata.nullable = True
    TaskActivityEvent.__table__.c.event_metadata.server_default = None
    Source.__table__.c.payload.type = JSON()
    Source.__table__.c.payload.server_default = None
    TaskCandidateRevision.__table__.c.event_metadata.type = JSON()
    TaskCandidateRevision.__table__.c.event_metadata.server_default = None
    CandidateApprovalEvent.__table__.c.event_metadata.type = JSON()
    CandidateApprovalEvent.__table__.c.event_metadata.server_default = None
    MemoryAuditEvent.__table__.c["metadata"].type = JSON()
    MemoryAuditEvent.__table__.c["metadata"].server_default = None
    _sqlite_columns_patched = True


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------
def create_test_db(
    user_email: str = "test@example.com",
    caller_globals: dict | None = None,
):
    """Create an in-memory SQLite test database.

    Args:
        user_email: Email for the seed user.
        caller_globals: Pass ``globals()`` from the calling module so that
            its module-level ``SessionLocal`` name is rebound to the test
            session factory.  This is necessary because the test files use
            ``from app.database import SessionLocal`` which creates a
            module-local binding that must be patched individually.

    Returns:
        Tuple of (db_session, user_namespace, cleanup_fn).
    """
    patch_sqlite_columns()

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine, tables=ALL_TEST_TABLES)

    setup_db = testing_session_local()
    user = User(email=user_email, hashed_password="hashed")
    setup_db.add(user)
    setup_db.commit()
    setup_db.refresh(user)
    user_id = user.id
    setup_db.close()

    import app.database as _db_module

    original_session_local = _db_module.SessionLocal

    # Patch the canonical module so ``app.database.SessionLocal`` resolves
    # to the test session factory.
    _db_module.SessionLocal = testing_session_local
    # Patch our own module-level reference.
    globals()["SessionLocal"] = testing_session_local
    # Patch the caller's module-level reference (if provided).
    if caller_globals is not None:
        caller_globals["SessionLocal"] = testing_session_local

    db = testing_session_local()
    current_user = SimpleNamespace(id=user_id)

    def cleanup():
        db.close()
        _db_module.SessionLocal = original_session_local
        globals()["SessionLocal"] = original_session_local
        if caller_globals is not None:
            caller_globals["SessionLocal"] = original_session_local

    return db, current_user, cleanup


# ---------------------------------------------------------------------------
# DirectResponse
# ---------------------------------------------------------------------------
class DirectResponse:
    def __init__(self, status_code: int, data=None):
        self.status_code = status_code
        self._data = data
        self.text = "" if data is None else json.dumps(data)

    def json(self):
        return self._data


# ---------------------------------------------------------------------------
# Base DirectClient — shared across all test files
# ---------------------------------------------------------------------------
class BaseDirectClient:
    """Thin HTTP-like client that calls router functions directly.

    Subclasses override get/post/patch/put/delete to dispatch
    the routes they need.
    """

    def __init__(self, db, current_user):
        self.db = db
        self.current_user = current_user

    def _ok(self, value, status_code=200):
        return DirectResponse(status_code, jsonable_encoder(value))

    def _error(self, exc: HTTPException):
        return DirectResponse(exc.status_code, {"detail": exc.detail})

    @staticmethod
    def _parse(url: str):
        parsed = urlparse(url)
        return parsed.path, parse_qs(parsed.query)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def unique() -> str:
    return str(uuid.uuid4())


def make_workspace(client, name=None):
    payload = {"name": name or f"Workspace-{unique()}"}
    resp = client.post("/api/workspaces", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_project(client, workspace_id=None, name=None):
    if workspace_id is None:
        workspace_id = make_workspace(client)["id"]
    payload = {"name": name or f"Project-{unique()}"}
    resp = client.post(f"/api/workspaces/{workspace_id}/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_person(client, name=None, email=None):
    payload = {
        "name": name or f"Person-{unique()}",
        "email": email or f"{unique()}@example.com",
    }
    resp = client.post("/api/people", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def list_tasks(client, project_id):
    resp = client.get(f"/api/tasks?project_id={project_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Extraction persistence helper (replaces the deleted _save_extraction_outcome)
# ---------------------------------------------------------------------------


def persist_extraction_tasks(
    db,
    *,
    project_id: str,
    source_type: str,
    source_content: str,
    source_excerpt: str,
    source_summary: str,
    tasks: tuple,
    recommendations_by_task: list | None = None,
    source_uri: str | None = None,
    source_payload: dict | None = None,
    model_version: str | None = None,
    prompt_template_hash: str | None = None,
    model_latency_ms: int | None = None,
) -> list[UUID]:
    """Persist extracted tasks directly to DB, bypassing the agent loop.

    Used in fake use-cases inside tests that need candidates and tasks to exist
    without hitting Gemini.  Replicates what the create_tasks tool does.
    """
    from app.config import get_settings
    from app.models import Project, Source, TaskCandidate, TaskPriority, TaskSource
    from app.services.candidate_provenance_service import append_candidate_revision
    from app.services.candidate_service import create_task_from_candidate

    if recommendations_by_task is None:
        recommendations_by_task = [[] for _ in tasks]

    settings = get_settings()
    pid = UUID(project_id)

    resolved_source_uri = source_uri
    resolved_source_payload = dict(source_payload or {})
    if not resolved_source_payload and source_type == "text":
        resolved_source_payload = {"raw_text": source_content}
    if source_type == "url":
        if resolved_source_uri is None:
            resolved_source_uri = source_content
        if not resolved_source_payload:
            resolved_source_payload = {"fetched_text": source_excerpt}

    project = db.get(Project, pid)
    assert project, f"project {pid} not found"

    content_hash = hashlib.sha256(
        source_content.encode("utf-8", errors="replace")
    ).hexdigest()

    source = (
        db.query(Source)
        .filter(
            Source.workspace_id == project.workspace_id,
            Source.project_id == pid,
            Source.source_type == source_type,
            Source.content_hash == content_hash,
        )
        .first()
    )
    if not source:
        source = Source(
            workspace_id=project.workspace_id,
            project_id=pid,
            source_type=source_type,
            uri=resolved_source_uri,
            summary=source_summary,
            excerpt=source_excerpt[: settings.ai_source_excerpt_chars],
            content_hash=content_hash,
            payload=resolved_source_payload,
        )
        db.add(source)
        db.flush()

    created_task_ids: list[UUID] = []
    for idx, item in enumerate(tasks):
        recs_raw = list(
            recommendations_by_task[idx] if idx < len(recommendations_by_task) else []
        )
        # Apply payload builder so defaults (reason_code, workload_score, etc.) are filled in
        from app.ai.agent_extraction.tools import (
            _build_recommendation_payload,
            _resolve_selected_assignee_id,
        )

        recs = [_build_recommendation_payload(r) for r in recs_raw]
        selected_assignee_id = _resolve_selected_assignee_id(
            db, recs, task_confidence=float(item.confidence_score)
        )

        candidate = TaskCandidate(
            project_id=pid,
            title=item.title[: settings.ai_task_title_max_chars],
            description=item.description,
            priority=TaskPriority(item.priority),
            due_date=item.due_date,
            selected_assignee_id=selected_assignee_id,
            confidence_score=item.confidence_score,
            source_type=source_type,
            source_excerpt=source_excerpt[: settings.ai_source_excerpt_chars],
            source_summary=source_summary,
            assignee_recommendations=recs,
        )
        db.add(candidate)
        db.flush()

        task = create_task_from_candidate(
            db, candidate, actor_type="system", actor_label="auto_approve_after_extract"
        )
        candidate.approved_task_id = task.id

        db.add(
            TaskSource(
                task_id=task.id,
                source_id=source.id,
                link_type="derived_from",
                confidence_score=candidate.confidence_score,
            )
        )

        append_candidate_revision(
            db,
            candidate,
            revision_type="extracted",
            source_id=source.id,
            model_version=model_version,
            prompt_template_hash=prompt_template_hash,
            model_latency_ms=model_latency_ms,
            event_metadata={"flow": "extraction_pipeline"},
        )

        created_task_ids.append(task.id)

    db.commit()
    return created_task_ids
