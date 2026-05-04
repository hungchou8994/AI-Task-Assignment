import os
import uuid
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi import BackgroundTasks

from app.models import (
    CandidateStatus,
    Source,
    Task,
    TaskCandidate,
    TaskSource,
    TaskStatus,
)
from app.routers import ai, task_candidates
from app.services import extraction_service as _extraction_svc
from app.schemas import (
    ExtractedTaskItem,
    ExtractionOutcome,
    ExtractTasksResult,
)

from tests.helpers import (
    BaseDirectClient,
    create_test_db,
    make_project,
    persist_extraction_tasks,
    unique,
)


# ---------------------------------------------------------------------------
# DirectClient
# ---------------------------------------------------------------------------


class DirectClient(BaseDirectClient):
    def post(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        if path == "/api/ai/extract-tasks":
            payload = ai.ExtractTasksRequest(**json)
            import asyncio

            response = asyncio.run(
                ai.extract_tasks(
                    payload=payload,
                    background_tasks=BackgroundTasks(),
                    db=self.db,
                    current_user=self.current_user,
                    use_case=ai.get_extract_tasks_use_case(self.db),
                )
            )
            return self._ok(response)
        if path == "/api/workspaces":
            from app.routers import workspaces

            response = workspaces.create_workspace(
                payload=workspaces.WorkspaceCreate(**json),
                db=self.db,
                current_user=self.current_user,
            )
            return self._ok(response, 201)
        if path.startswith("/api/workspaces/") and path.endswith("/projects"):
            from app.routers import workspaces

            workspace_id = uuid.UUID(path.split("/")[3])
            response = workspaces.create_project(
                workspace_id=workspace_id,
                payload=workspaces.ProjectCreate(**json),
                db=self.db,
                current_user=self.current_user,
            )
            return self._ok(response, 201)
        if path == "/api/people":
            from app.routers import people

            response = people.create_person(
                payload=people.PersonCreate(**json),
                db=self.db,
                current_user=self.current_user,
            )
            return self._ok(response, 201)
        if path.startswith("/api/task-candidates/") and path.endswith("/approve"):
            candidate_id = uuid.UUID(path.split("/")[3])
            response = task_candidates.approve_candidate(
                candidate_id=candidate_id,
                db=self.db,
                current_user=self.current_user,
                background_tasks=BackgroundTasks(),
            )
            return self._ok(response)
        if path.startswith("/api/task-candidates/") and path.endswith("/reject"):
            candidate_id = uuid.UUID(path.split("/")[3])
            response = task_candidates.reject_candidate(
                candidate_id=candidate_id,
                db=self.db,
                current_user=self.current_user,
                background_tasks=BackgroundTasks(),
            )
            return self._ok(response)
        if path.startswith("/api/task-candidates/") and path.endswith("/undo-reject"):
            candidate_id = uuid.UUID(path.split("/")[3])
            response = task_candidates.undo_reject(
                candidate_id=candidate_id,
                db=self.db,
                current_user=self.current_user,
            )
            return self._ok(response)
        raise AssertionError(f"Unhandled POST path: {path}")


@pytest.fixture
def client():
    db, current_user, cleanup = create_test_db(
        user_email="qa-ait-40@example.com",
        caller_globals=globals(),
    )
    try:
        yield DirectClient(db=db, current_user=current_user)
    finally:
        cleanup()


def test_traceability_full_chain(client, monkeypatch):
    """
    Verify the chain: Source Text -> TaskCandidate -> Approved Task.
    Requirement: Test matrix for source text -> candidate -> approved task traceability
    """
    project = make_project(client)
    source_content = "Please fix the login bug by Friday. - John"

    outcome = ExtractionOutcome(
        source_summary="Email about login bug.",
        tasks=(
            ExtractedTaskItem(
                title="Fix login bug",
                description="User reported login failure on production.",
                priority="high",
                due_date=date(2026, 4, 12),
                confidence_score=0.95,
            ),
        ),
    )

    class FakeExtractTasksUseCase:
        async def execute(self, command):
            created_task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt=source_content[:50],
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
                recommendations_by_task=[[] for _ in outcome.tasks],
                model_version="test-model-v1",
                prompt_template_hash="a" * 64,
                model_latency_ms=123,
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(created_task_ids),
            )

    monkeypatch.setattr(
        ai,
        "get_extract_tasks_use_case",
        lambda db: FakeExtractTasksUseCase(),
    )

    # 1. Extraction
    response = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": source_content,
            "project_id": project["id"],
        },
    )
    assert response.status_code == 200

    # 2. Verify Candidate
    candidate = (
        client.db.query(TaskCandidate)
        .filter(TaskCandidate.title == "Fix login bug")
        .one()
    )
    assert candidate.source_summary == "Email about login bug."
    assert candidate.source_excerpt == source_content[:50]
    assert candidate.status == CandidateStatus.pending
    assert candidate.approved_task_id is not None

    # 3. Verify Task and Source Link
    task = client.db.get(Task, candidate.approved_task_id)
    assert task.title == "Fix login bug"
    assert task.status == TaskStatus.todo

    task_source = (
        client.db.query(TaskSource).filter(TaskSource.task_id == task.id).one()
    )
    source = client.db.get(Source, task_source.source_id)
    assert source.summary == "Email about login bug."
    assert source.excerpt == source_content[:50]
    assert task_source.link_type == "derived_from"

    # 4. Approval
    approve_resp = client.post(f"/api/task-candidates/{candidate.id}/approve")
    assert approve_resp.status_code == 200

    client.db.refresh(candidate)
    assert candidate.status == CandidateStatus.approved

    # 5. Provenance (Traceability verification)
    from app.routers.task_candidates import get_candidate_provenance

    provenance = get_candidate_provenance(candidate.id, client.db, client.current_user)
    assert provenance.candidate_id == candidate.id
    assert provenance.approved_task_id == task.id
    revision_types = [r.revision_type for r in provenance.revisions]
    assert "extracted" in revision_types
    assert "approved" in revision_types


def test_ai_malformed_output(client, monkeypatch):
    """
    Verify system handles malformed AI output from the agent runner.
    Requirement: Negative tests for AI malformed output
    """
    project = make_project(client)

    from app.ai.agent_extraction import extraction_agent

    async def mock_runner_fail(*args, **kwargs):
        raise ValueError("Agent loop failed to produce valid output")

    monkeypatch.setattr(extraction_agent.Runner, "run", mock_runner_fail)

    import asyncio
    from app.schemas import ExtractTasksCommand

    command = ExtractTasksCommand(
        source_type="text",
        content="bad content",
        project_id=project["id"],
        job_id=str(uuid.uuid4()),
    )

    with pytest.raises(ValueError, match="Agent loop failed to produce valid output"):
        asyncio.run(_extraction_svc.extract_tasks(client.db, command))


def test_agent_no_finalization(client, monkeypatch):
    """
    Verify system raises RuntimeError when agent loop ends without calling finalize_extraction.
    Requirement: Agent loop must finalize to produce a result
    """
    project = make_project(client)

    from app.ai.agent_extraction import extraction_agent

    async def mock_no_finalize(*args, **kwargs):
        # Simulate agent loop ending without calling finalize_extraction
        return SimpleNamespace(iterations=5, messages=[])

    monkeypatch.setattr(extraction_agent.Runner, "run", mock_no_finalize)

    import asyncio
    from app.schemas import ExtractTasksCommand

    command = ExtractTasksCommand(
        source_type="text",
        content="content without tasks",
        project_id=project["id"],
        job_id=str(uuid.uuid4()),
    )

    with pytest.raises(RuntimeError, match="without calling finalize_extraction"):
        asyncio.run(_extraction_svc.extract_tasks(client.db, command))


def test_confidence_fallback(client, monkeypatch):
    """
    Verify that assignee is NOT auto-applied if task confidence is below threshold.
    Requirement: Negative tests for confidence fallback
    """
    project = make_project(client)
    from app import config

    mock_settings = SimpleNamespace(
        gemini_api_key="dummy-key",
        gemini_model="gemini-1.5-pro",
        gemini_temperature=0.0,
        ai_task_title_max_chars=500,
        ai_source_excerpt_chars=500,
        ai_url_fetch_cap=5,
        ai_url_strip_chars=20000,
        ai_max_attachment_bytes=10 * 1024 * 1024,
        ai_assignee_auto_apply_confidence_threshold=0.8,
    )
    monkeypatch.setattr(config, "get_settings", lambda: mock_settings)

    from tests.helpers import make_person

    person = make_person(client)

    outcome = ExtractionOutcome(
        source_summary="Low confidence task.",
        tasks=(
            ExtractedTaskItem(
                title="Low confidence bug",
                description="Might be a bug.",
                priority="medium",
                due_date=date(2026, 4, 15),
                confidence_score=0.5,  # Below 0.8 threshold
            ),
        ),
    )

    class FakeExtractTasksUseCase:
        async def execute(self, command):
            recs = [
                {
                    "rank": 1,
                    "person_id": person["id"],
                    "name": person["name"],
                    "confidence_score": 0.9,
                    "reasoning": "He is the only one here.",
                    "auto_apply_eligible": True,
                }
            ]
            created_task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="Maybe fix something?",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
                recommendations_by_task=[recs],
                model_version="test-model-v1",
                prompt_template_hash="b" * 64,
                model_latency_ms=100,
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(created_task_ids),
            )

    monkeypatch.setattr(
        ai,
        "get_extract_tasks_use_case",
        lambda db: FakeExtractTasksUseCase(),
    )

    response = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": "Maybe fix something?",
            "project_id": project["id"],
        },
    )
    assert response.status_code == 200

    candidate = (
        client.db.query(TaskCandidate)
        .filter(TaskCandidate.title == "Low confidence bug")
        .one()
    )

    # Verify assignee was NOT selected despite high recommendation confidence
    assert candidate.selected_assignee_id is None
    assert len(candidate.assignee_recommendations) == 1

    task = client.db.get(Task, candidate.approved_task_id)
    assert task.assignee_id is None


def test_review_queue_workflow_hitl(client, monkeypatch):
    """
    Verify Approve -> Reject -> Undo Reject -> Approve flow.
    Requirement: Cross-browser validation for review queue workflows (API side)
    """
    project = make_project(client)

    from tests.test_task_candidates import create_candidate

    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = candidate.id
    task_id = candidate.approved_task_id

    task = client.db.get(Task, task_id)
    assert task.status == TaskStatus.todo
    assert candidate.status == CandidateStatus.pending

    # 1. Reject
    reject_resp = client.post(f"/api/task-candidates/{candidate_id}/reject")
    assert reject_resp.status_code == 200
    client.db.refresh(candidate)
    client.db.refresh(task)
    assert candidate.status == CandidateStatus.rejected
    assert task.status == TaskStatus.cancelled
    assert candidate.approved_task_id is None

    # 2. Undo Reject
    undo_resp = client.post(f"/api/task-candidates/{candidate_id}/undo-reject")
    assert undo_resp.status_code == 200
    client.db.refresh(candidate)
    assert candidate.status == CandidateStatus.pending

    # 3. Approve
    approve_resp = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve_resp.status_code == 200
    client.db.refresh(candidate)
    assert candidate.status == CandidateStatus.approved
    assert candidate.approved_task_id is not None

    new_task = client.db.get(Task, candidate.approved_task_id)
    assert new_task.status == TaskStatus.todo
