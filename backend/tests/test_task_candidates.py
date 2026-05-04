import os
import asyncio
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.database import SessionLocal  # noqa: F811 — rebound by create_test_db
from app.schemas import (
    ExtractedTaskItem,
    ExtractionOutcome,
    ExtractionServiceResult,
    ExtractTasksResult,
)
from app.services import extraction_service as _extraction_svc
from app.models import (
    CandidateApprovalEvent,
    CandidateSourceSpan,
    FeedbackEvent,
    Organization,
    OrgMembership,
    Person,
    Project,
    Task,
    TaskCandidate,
    TaskCandidateRevision,
    TaskPriority,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.routers import ai, people, task_candidates, tasks, workspaces
from app.models import CandidateStatus

from tests.helpers import (
    BaseDirectClient,
    DirectResponse,
    create_test_db,
    list_tasks,
    make_person,
    make_project,
    make_workspace,
    persist_extraction_tasks,
    unique,
)


class DirectClient(BaseDirectClient):
    def get(self, url: str, **kwargs):
        path, query = self._parse(url)
        try:
            if path == "/api/tasks":
                project_id = query.get("project_id", [None])[0]
                project_uuid = uuid.UUID(project_id) if project_id else None
                inc = (query.get("include_archived", ["false"])[0] or "").lower()
                include_archived = inc in ("1", "true", "yes")
                response = tasks.list_tasks(
                    db=self.db,
                    project_id=project_uuid,
                    include_archived=include_archived,
                    current_user=self.current_user,
                )
                return self._ok(response)
            if path == "/api/task-candidates":
                project_id = uuid.UUID(query["project_id"][0])
                status = CandidateStatus(query.get("status", ["pending"])[0])
                response = task_candidates.list_candidates(
                    db=self.db,
                    project_id=project_id,
                    status=status,
                    current_user=self.current_user,
                )
                return self._ok(response)
            if path.startswith("/api/tasks/") and path.endswith("/provenance"):
                task_id = uuid.UUID(path.split("/")[3])
                response = tasks.get_task_provenance(
                    task_id=task_id,
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response)
            raise AssertionError(f"Unhandled GET path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def post(self, url: str, json=None, **kwargs):
        path, query = self._parse(url)
        try:
            if path == "/api/ai/extract-tasks":
                payload = ai.ExtractTasksRequest(**json)
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
                response = workspaces.create_workspace(
                    payload=workspaces.WorkspaceCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response, 201)
            if path.startswith("/api/workspaces/") and path.endswith("/projects"):
                workspace_id = uuid.UUID(path.split("/")[3])
                response = workspaces.create_project(
                    workspace_id=workspace_id,
                    payload=workspaces.ProjectCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response, 201)
            if path == "/api/people":
                response = people.create_person(
                    payload=people.PersonCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response, 201)
            if path == "/api/tasks":
                response = tasks.create_task(
                    payload=tasks.TaskCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response, 201)
            if path == "/api/task-candidates/batch-approve":
                response = task_candidates.batch_approve(
                    payload=task_candidates.BatchCandidateActionRequest(**json),
                    db=self.db,
                    current_user=self.current_user,
                    background_tasks=BackgroundTasks(),
                )
                return self._ok(response)
            if path == "/api/task-candidates/batch-reject":
                response = task_candidates.batch_reject(
                    payload=task_candidates.BatchCandidateActionRequest(**json),
                    db=self.db,
                    current_user=self.current_user,
                    background_tasks=BackgroundTasks(),
                )
                return self._ok(response)
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
            if path.startswith("/api/task-candidates/") and path.endswith(
                "/undo-reject"
            ):
                candidate_id = uuid.UUID(path.split("/")[3])
                response = task_candidates.undo_reject(
                    candidate_id=candidate_id,
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response)
            raise AssertionError(f"Unhandled POST path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def patch(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        try:
            if path.startswith("/api/task-candidates/"):
                candidate_id = uuid.UUID(path.split("/")[3])
                response = task_candidates.patch_candidate(
                    candidate_id=candidate_id,
                    payload=task_candidates.TaskCandidatePatch(**json),
                    db=self.db,
                    background_tasks=BackgroundTasks(),
                    current_user=self.current_user,
                )
                return self._ok(response)
            if path.startswith("/api/tasks/"):
                parts = path.split("/")
                if len(parts) != 4:
                    raise AssertionError(f"Unhandled PATCH path: {path}")
                task_id = uuid.UUID(parts[3])
                response = tasks.patch_task(
                    task_id=task_id,
                    payload=tasks.TaskPatch(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response)
            raise AssertionError(f"Unhandled PATCH path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def put(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        try:
            if path.startswith("/api/tasks/"):
                task_id = uuid.UUID(path.split("/")[3])
                response = tasks.update_task(
                    task_id=task_id,
                    payload=tasks.TaskUpdate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response)
            raise AssertionError(f"Unhandled PUT path: {path}")
        except HTTPException as exc:
            return self._error(exc)


@pytest.fixture
def client(tmp_path):
    db, current_user, cleanup = create_test_db(
        user_email="task-candidates@example.com",
        caller_globals=globals(),
    )
    try:
        yield DirectClient(db=db, current_user=current_user)
    finally:
        cleanup()


def mock_extraction_result(person_id=None):
    _ = person_id
    return ExtractionServiceResult(
        outcome=ExtractionOutcome(
            source_summary="Release work planning notes.",
            tasks=(
                ExtractedTaskItem(
                    title=f"Candidate-{unique()}",
                    description="Prepare release notes and changelog.",
                    priority="high",
                    due_date=date(2026, 4, 1),
                    confidence_score=0.91,
                ),
            ),
        ),
        source_excerpt="Seed candidate for task candidate tests.",
    )


def create_candidate(client, monkeypatch, project_id, recommendation_ids=None):
    result = mock_extraction_result(
        person_id=recommendation_ids[0] if recommendation_ids else None
    )
    title = result.outcome.tasks[0].title

    class FakeExtractTasksUseCase:
        def __init__(self, outcome_result, db):
            self._result = outcome_result
            self._db = db

        async def execute(self, command):
            created_task_ids = persist_extraction_tasks(
                self._db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt=self._result.source_excerpt,
                source_summary=self._result.outcome.source_summary,
                tasks=self._result.outcome.tasks,
                recommendations_by_task=[[] for _ in self._result.outcome.tasks],
                model_version="test-model-v1",
                prompt_template_hash="a" * 64,
                model_latency_ms=42,
            )
            return ExtractTasksResult(
                outcome=self._result.outcome,
                created_task_ids=tuple(created_task_ids),
            )

    monkeypatch.setattr(
        ai,
        "get_extract_tasks_use_case",
        lambda db: FakeExtractTasksUseCase(result, db),
    )

    response = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": "Seed candidate for task candidate tests.",
            "project_id": project_id,
        },
    )
    assert response.status_code == 200, response.text

    candidate = (
        client.db.query(TaskCandidate)
        .filter(
            TaskCandidate.project_id == uuid.UUID(str(project_id)),
            TaskCandidate.title == title,
        )
        .order_by(TaskCandidate.created_at.desc(), TaskCandidate.id.desc())
        .one()
    )

    if recommendation_ids is not None:
        candidate.assignee_recommendations = [
            {
                "rank": idx,
                "person_id": person_id,
                "name": f"Recommended-{idx}",
                "confidence_score": 0.95 - (idx * 0.1),
                "reasoning": f"Recommendation {idx}",
            }
            for idx, person_id in enumerate(recommendation_ids, start=1)
        ]
        candidate.selected_assignee_id = uuid.UUID(str(recommendation_ids[0]))
        client.db.commit()
        client.db.refresh(candidate)

    return candidate


def create_foreign_candidate(title=None):
    with SessionLocal() as db:
        other_user = User(
            email=f"foreign-{uuid.uuid4()}@example.com",
            hashed_password="hashed",
        )
        db.add(other_user)
        db.flush()

        org = Organization(
            name="Foreign Org",
            slug=f"foreign-{str(other_user.id)[:8]}",
            settings={},
        )
        db.add(org)
        db.flush()
        db.add(OrgMembership(org_id=org.id, user_id=other_user.id, role="owner"))

        workspace = Workspace(
            name="Foreign Workspace",
            owner_id=other_user.id,
            org_id=org.id,
        )
        db.add(workspace)
        db.flush()
        db.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=other_user.id,
                role="owner",
            )
        )

        project = Project(name="Foreign Project", workspace_id=workspace.id)
        db.add(project)
        db.flush()

        candidate = TaskCandidate(
            project_id=project.id,
            title=title or f"Foreign-{uuid.uuid4()}",
            description="Foreign candidate",
            priority=TaskPriority.medium,
            confidence_score=0.5,
            source_type="text",
            source_excerpt="foreign excerpt",
            source_summary="foreign summary",
            assignee_recommendations=[],
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate


def get_feedback_events_for_candidate(candidate_id):
    candidate_uuid = uuid.UUID(str(candidate_id))
    with SessionLocal() as db:
        return (
            db.query(FeedbackEvent)
            .filter(FeedbackEvent.candidate_id == candidate_uuid)
            .order_by(FeedbackEvent.created_at.asc())
            .all()
        )


def test_analyze_creates_candidates_and_auto_creates_tasks(client, monkeypatch):
    project = make_project(client)
    before_count = len(list_tasks(client, project["id"]))
    candidate = create_candidate(client, monkeypatch, project["id"])
    assert candidate.source_summary == "Release work planning notes."

    with SessionLocal() as db:
        candidate_count = (
            db.query(TaskCandidate)
            .filter(TaskCandidate.project_id == uuid.UUID(project["id"]))
            .count()
        )
    assert candidate_count == 1

    after_count = len(list_tasks(client, project["id"]))
    assert after_count == before_count + 1

    with SessionLocal() as db:
        refreshed = db.get(TaskCandidate, candidate.id)
        assert refreshed is not None
        assert refreshed.status == CandidateStatus.pending
        assert refreshed.approved_task_id is not None


def test_approve_creates_one_task_and_sets_approved_task_id(client, monkeypatch):
    project = make_project(client)
    person = make_person(client)

    candidate = create_candidate(client, monkeypatch, project["id"], [person["id"]])
    candidate_id = str(candidate.id)

    before_count = len(list_tasks(client, project["id"]))
    prelinked_task_id = str(candidate.approved_task_id)
    approve = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve.status_code == 200, approve.text
    body = approve.json()
    assert body["task_id"]
    assert body["candidate"]["approved_task_id"] == body["task_id"]
    assert body["candidate"]["status"] == "approved"
    assert body["task_id"] == prelinked_task_id

    after_count = len(list_tasks(client, project["id"]))
    assert after_count == before_count


def test_reject_hides_from_pending_and_can_undo_within_window(client, monkeypatch):
    project = make_project(client)

    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    reject = client.post(f"/api/task-candidates/{candidate_id}/reject")
    assert reject.status_code == 200, reject.text
    reject_data = reject.json()
    assert reject_data["candidate"]["status"] == "rejected"
    assert reject_data["undo_expires_at"] is not None

    pending = client.get(
        f"/api/task-candidates?project_id={project['id']}&status=pending"
    )
    assert pending.status_code == 200, pending.text
    assert all(item["id"] != candidate_id for item in pending.json())

    undo = client.post(f"/api/task-candidates/{candidate_id}/undo-reject")
    assert undo.status_code == 200, undo.text
    assert undo.json()["candidate"]["status"] == "pending"


def test_undo_after_window_returns_conflict(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    reject = client.post(f"/api/task-candidates/{candidate_id}/reject")
    assert reject.status_code == 200, reject.text

    with SessionLocal() as db:
        candidate = db.get(TaskCandidate, uuid.UUID(candidate_id))
        candidate.undo_expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()

    undo = client.post(f"/api/task-candidates/{candidate_id}/undo-reject")
    assert undo.status_code == 409


def test_batch_approve_reject_reports_per_item_outcomes(client, monkeypatch):
    project = make_project(client)

    ids = []
    for _ in range(3):
        candidate = create_candidate(client, monkeypatch, project["id"])
        ids.append(str(candidate.id))

    approve_resp = client.post(
        "/api/task-candidates/batch-approve",
        json={"candidate_ids": ids[:2]},
    )
    assert approve_resp.status_code == 200, approve_resp.text
    approve_results = approve_resp.json()["results"]
    assert len(approve_results) == 2
    assert all(item["status"] == "approved" for item in approve_results)

    reject_resp = client.post(
        "/api/task-candidates/batch-reject",
        json={"candidate_ids": ids[1:]},
    )
    assert reject_resp.status_code == 200, reject_resp.text
    reject_results = reject_resp.json()["results"]
    assert len(reject_results) == 2
    statuses = {item["candidate_id"]: item["status"] for item in reject_results}
    assert statuses[ids[1]] == "conflict"
    assert statuses[ids[2]] == "rejected"


def test_batch_approve_emits_accept_event_per_successful_item(client, monkeypatch):
    project = make_project(client)

    ids = []
    for _ in range(2):
        candidate = create_candidate(client, monkeypatch, project["id"])
        ids.append(str(candidate.id))

    approve_resp = client.post(
        "/api/task-candidates/batch-approve",
        json={"candidate_ids": ids},
    )
    assert approve_resp.status_code == 200, approve_resp.text

    for candidate_id in ids:
        events = get_feedback_events_for_candidate(candidate_id)
        actions = [event.action.value for event in events]
        assert actions == ["accept"]


def test_batch_reject_emits_reject_event_per_successful_item(client, monkeypatch):
    project = make_project(client)

    ids = []
    for _ in range(2):
        candidate = create_candidate(client, monkeypatch, project["id"])
        ids.append(str(candidate.id))

    reject_resp = client.post(
        "/api/task-candidates/batch-reject",
        json={"candidate_ids": ids},
    )
    assert reject_resp.status_code == 200, reject_resp.text

    for candidate_id in ids:
        events = get_feedback_events_for_candidate(candidate_id)
        actions = [event.action.value for event in events]
        assert actions == ["reject"]


def test_batch_conflicts_do_not_emit_feedback_events(client, monkeypatch):
    project = make_project(client)

    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    approve_resp = client.post(
        "/api/task-candidates/batch-approve",
        json={"candidate_ids": [candidate_id]},
    )
    assert approve_resp.status_code == 200, approve_resp.text

    reject_resp = client.post(
        "/api/task-candidates/batch-reject",
        json={"candidate_ids": [candidate_id]},
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["results"][0]["status"] == "conflict"

    events = get_feedback_events_for_candidate(candidate_id)
    actions = [event.action.value for event in events]
    assert actions == ["accept"]


def test_batch_endpoints_return_item_level_forbidden_on_project_access_failure(
    client, monkeypatch
):
    project = make_project(client)
    accessible_approve = create_candidate(client, monkeypatch, project["id"])
    foreign_approve = create_foreign_candidate()

    approve_resp = client.post(
        "/api/task-candidates/batch-approve",
        json={
            "candidate_ids": [
                str(accessible_approve.id),
                str(foreign_approve.id),
            ]
        },
    )
    assert approve_resp.status_code == 200, approve_resp.text
    approve_results = {
        item["candidate_id"]: item for item in approve_resp.json()["results"]
    }
    assert approve_results[str(accessible_approve.id)]["status"] == "approved"
    assert approve_results[str(foreign_approve.id)]["status"] == "forbidden"
    assert (
        approve_results[str(foreign_approve.id)]["message"]
        == "Forbidden: Not a workspace member"
    )
    accessible_reject = create_candidate(client, monkeypatch, project["id"])
    foreign_reject = create_foreign_candidate()

    reject_resp = client.post(
        "/api/task-candidates/batch-reject",
        json={
            "candidate_ids": [
                str(accessible_reject.id),
                str(foreign_reject.id),
            ]
        },
    )
    assert reject_resp.status_code == 200, reject_resp.text
    reject_results = {
        item["candidate_id"]: item for item in reject_resp.json()["results"]
    }
    assert reject_results[str(accessible_reject.id)]["status"] == "rejected"
    assert reject_results[str(foreign_reject.id)]["status"] == "forbidden"
    assert (
        reject_results[str(foreign_reject.id)]["message"]
        == "Forbidden: Not a workspace member"
    )


def test_list_candidates_orders_by_created_at_desc_then_id_desc(client, monkeypatch):
    project = make_project(client)

    candidate_ids = []
    for _ in range(3):
        candidate = create_candidate(client, monkeypatch, project["id"])
        candidate_ids.append(str(candidate.id))

    shared_created_at = datetime(2026, 3, 25, 0, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        for candidate_id in candidate_ids:
            candidate = db.get(TaskCandidate, uuid.UUID(candidate_id))
            candidate.created_at = shared_created_at
        db.commit()

    listed = client.get(
        f"/api/task-candidates?project_id={project['id']}&status=pending"
    )
    assert listed.status_code == 200, listed.text

    returned_ids = [item["id"] for item in listed.json()]
    with SessionLocal() as db:
        expected_order = [
            str(candidate.id)
            for candidate in (
                db.query(TaskCandidate)
                .filter(TaskCandidate.project_id == uuid.UUID(project["id"]))
                .order_by(TaskCandidate.created_at.desc(), TaskCandidate.id.desc())
                .all()
            )
        ]
    assert returned_ids[:3] == expected_order


def test_patch_updates_pending_only(client, monkeypatch):
    project = make_project(client)

    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    edit = client.patch(
        f"/api/task-candidates/{candidate_id}",
        json={"title": "Updated title", "priority": "low"},
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["title"] == "Updated title"
    assert edit.json()["priority"] == "low"

    approve = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve.status_code == 200, approve.text

    edit_again = client.patch(
        f"/api/task-candidates/{candidate_id}",
        json={"title": "Should fail"},
    )
    assert edit_again.status_code == 409


def test_patch_due_date_serializes_feedback_event_deltas(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)
    new_due_date = "2026-04-22"

    edit = client.patch(
        f"/api/task-candidates/{candidate_id}",
        json={"due_date": new_due_date},
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["due_date"] == new_due_date

    events = get_feedback_events_for_candidate(candidate_id)
    assert len(events) == 1
    assert events[0].action.value == "edit"
    assert events[0].field_deltas["due_date"] == {
        "original": "2026-04-01",
        "final": new_due_date,
    }


def test_candidate_provenance_endpoint_returns_revision_and_approval_timeline(
    client, monkeypatch
):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    edit = client.patch(
        f"/api/task-candidates/{candidate_id}",
        json={"title": "Edited for provenance"},
    )
    assert edit.status_code == 200, edit.text

    approve = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve.status_code == 200, approve.text

    with SessionLocal() as db:
        payload = task_candidates.get_candidate_provenance(
            candidate_id=uuid.UUID(candidate_id),
            db=db,
            current_user=client.current_user,
        )

    timeline_event_types = [item.event_type for item in payload.timeline]
    assert timeline_event_types.count("candidate_revision") >= 2
    assert "candidate_approval_event" in timeline_event_types
    assert any(item.revision_type == "edited" for item in payload.revisions)
    assert any(item.action.value == "approve" for item in payload.approval_events)


def test_task_provenance_endpoint_returns_approved_candidate_chain(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    approve = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve.status_code == 200, approve.text
    task_id = approve.json()["task_id"]

    provenance_resp = client.get(f"/api/tasks/{task_id}/provenance")
    assert provenance_resp.status_code == 200, provenance_resp.text
    payload = provenance_resp.json()
    assert payload["approved_task_id"] == task_id
    assert payload["candidate_id"] == candidate_id
    assert len(payload["revisions"]) >= 1


def test_candidate_actions_are_append_only_for_approval_events(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    reject = client.post(f"/api/task-candidates/{candidate_id}/reject")
    assert reject.status_code == 200, reject.text
    undo = client.post(f"/api/task-candidates/{candidate_id}/undo-reject")
    assert undo.status_code == 200, undo.text
    approve = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve.status_code == 200, approve.text

    with SessionLocal() as db:
        events = (
            db.query(CandidateApprovalEvent)
            .filter(CandidateApprovalEvent.candidate_id == uuid.UUID(candidate_id))
            .order_by(
                CandidateApprovalEvent.created_at.asc(), CandidateApprovalEvent.id.asc()
            )
            .all()
        )
    assert [event.action.value for event in events] == [
        "reject",
        "undo_reject",
        "approve",
    ]


def test_extraction_persists_model_metadata_on_candidate_revisions(client, monkeypatch):
    project = make_project(client)
    create_candidate(client, monkeypatch, project["id"])

    with SessionLocal() as db:
        revision = (
            db.query(TaskCandidateRevision)
            .order_by(
                TaskCandidateRevision.created_at.desc(), TaskCandidateRevision.id.desc()
            )
            .first()
        )

    assert revision is not None
    assert revision.model_version is not None
    assert revision.prompt_template_hash is not None
    assert len(revision.prompt_template_hash) == 64
    assert revision.model_latency_ms is not None


def test_candidate_revision_records_source_span_link(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    candidate_id = str(candidate.id)

    approve = client.post(f"/api/task-candidates/{candidate_id}/approve")
    assert approve.status_code == 200, approve.text

    with SessionLocal() as db:
        revision = (
            db.query(TaskCandidateRevision)
            .filter(TaskCandidateRevision.candidate_id == uuid.UUID(candidate_id))
            .order_by(TaskCandidateRevision.revision_number.desc())
            .first()
        )
        assert revision is not None
        spans = (
            db.query(CandidateSourceSpan)
            .filter(CandidateSourceSpan.candidate_revision_id == revision.id)
            .all()
        )
    assert len(spans) >= 1
