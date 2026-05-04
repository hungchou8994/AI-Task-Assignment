import os
import asyncio
import uuid
from datetime import date

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
from app.models import (
    Task,
    TaskActivityAction,
    TaskActivityEvent,
    TaskCandidate,
)
from app.services import extraction_service as _extraction_svc
from app.routers import ai, people, task_activity, task_candidates, tasks, workspaces

from tests.helpers import (
    BaseDirectClient,
    create_test_db,
    make_person,
    make_project,
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
            if path.endswith("/activity") and path.startswith("/api/tasks/"):
                task_id = uuid.UUID(path.split("/")[3])
                response = task_activity.list_task_activity(
                    task_id=task_id,
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response)
            raise AssertionError(f"Unhandled GET path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def post(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
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
            if path == "/api/tasks/bulk-delete":
                response = tasks.bulk_delete_tasks(
                    payload=tasks.BulkDeleteTasksRequest(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response)
            if path == "/api/tasks":
                response = tasks.create_task(
                    payload=tasks.TaskCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                    background_tasks=BackgroundTasks(),
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
                    background_tasks=BackgroundTasks(),
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
                    background_tasks=BackgroundTasks(),
                )
                return self._ok(response)
            raise AssertionError(f"Unhandled PUT path: {path}")
        except HTTPException as exc:
            return self._error(exc)


@pytest.fixture
def client(tmp_path):
    db, current_user, cleanup = create_test_db(
        user_email="task-activity@example.com",
        caller_globals=globals(),
    )
    try:
        yield DirectClient(db=db, current_user=current_user)
    finally:
        cleanup()


def make_task(client, project_id, **overrides):
    payload = {
        "title": f"Task-{unique()}",
        "project_id": project_id,
        "description": "Initial description",
        "priority": "medium",
        "status": "todo",
        **overrides,
    }
    resp = client.post("/api/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_bulk_delete_tasks_removes_selected_tasks(client):
    project = make_project(client)
    first = make_task(client, project["id"])
    second = make_task(client, project["id"])
    remaining = make_task(client, project["id"])

    response = client.post(
        "/api/tasks/bulk-delete",
        json={"task_ids": [first["id"], second["id"]]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["deleted_count"] == 2
    assert client.db.get(Task, uuid.UUID(first["id"])) is None
    assert client.db.get(Task, uuid.UUID(second["id"])) is None
    assert client.db.get(Task, uuid.UUID(remaining["id"])) is not None


def mock_extraction_result() -> ExtractionServiceResult:
    return ExtractionServiceResult(
        outcome=ExtractionOutcome(
            source_summary="Task activity source",
            tasks=(
                ExtractedTaskItem(
                    title=f"Candidate-{unique()}",
                    description="Candidate description",
                    priority="high",
                    due_date=date(2026, 4, 10),
                    confidence_score=0.7,
                ),
            ),
        ),
        source_excerpt="Create candidate for activity test",
    )


def create_candidate(client, monkeypatch, project_id):
    result = mock_extraction_result()
    title = result.outcome.tasks[0].title

    class FakeExtractTasksUseCase:
        def __init__(self, outcome_result, db):
            self._result = outcome_result
            self._db = db

        async def execute(self, command):
            created_ids = persist_extraction_tasks(
                self._db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt=self._result.source_excerpt,
                source_summary=self._result.outcome.source_summary,
                tasks=self._result.outcome.tasks,
                recommendations_by_task=[[] for _ in self._result.outcome.tasks],
            )
            return ExtractTasksResult(
                outcome=self._result.outcome,
                created_task_ids=tuple(created_ids),
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
            "content": "Create candidate for activity test",
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
    return candidate


def get_task_activity(task_id):
    task_uuid = uuid.UUID(str(task_id))
    with SessionLocal() as db:
        return (
            db.query(TaskActivityEvent)
            .filter(TaskActivityEvent.task_id == task_uuid)
            .order_by(TaskActivityEvent.occurred_at.asc(), TaskActivityEvent.id.asc())
            .all()
        )


def test_create_task_emits_task_created_event(client):
    project = make_project(client)
    task = make_task(client, project["id"])

    events = get_task_activity(task["id"])
    assert len(events) == 1
    assert events[0].action_type == TaskActivityAction.task_created
    assert events[0].actor_type == "user"
    assert events[0].actor_label == "task_api"
    assert events[0].occurred_at is not None


def test_update_task_logs_only_changed_tracked_fields(client):
    project = make_project(client)
    task = make_task(
        client, project["id"], description="Stable description", priority="low"
    )

    resp = client.put(
        f"/api/tasks/{task['id']}",
        json={
            "title": "Updated title",
            "description": "Stable description",
            "status": "in_progress",
            "priority": "high",
        },
    )
    assert resp.status_code == 200, resp.text

    events = get_task_activity(task["id"])
    changed_events = [
        e for e in events if e.action_type != TaskActivityAction.task_created
    ]
    assert len(changed_events) == 3

    by_field = {event.field_name: event for event in changed_events}
    assert set(by_field.keys()) == {"title", "status", "priority"}
    assert by_field["title"].action_type == TaskActivityAction.field_changed
    assert by_field["status"].action_type == TaskActivityAction.status_changed
    assert by_field["priority"].action_type == TaskActivityAction.field_changed
    assert by_field["status"].before_value == "todo"
    assert by_field["status"].after_value == "in_progress"


def test_patch_assignment_and_unassignment_emits_assignment_events(client):
    project = make_project(client)
    person = make_person(client)
    task = make_task(client, project["id"])

    assign = client.patch(
        f"/api/tasks/{task['id']}", json={"assignee_id": person["id"]}
    )
    assert assign.status_code == 200, assign.text
    unassign = client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": None})
    assert unassign.status_code == 200, unassign.text

    events = get_task_activity(task["id"])
    assignment_events = [
        event
        for event in events
        if event.action_type == TaskActivityAction.assignment_changed
    ]
    assert len(assignment_events) == 2
    assert assignment_events[0].before_value is None
    assert assignment_events[0].after_value == person["id"]
    assert assignment_events[1].before_value == person["id"]
    assert assignment_events[1].after_value is None


def test_candidate_approve_and_batch_approve_emit_task_created_events(
    client, monkeypatch
):
    project = make_project(client)

    candidate_a = create_candidate(client, monkeypatch, project["id"])
    approve = client.post(f"/api/task-candidates/{candidate_a.id}/approve")
    assert approve.status_code == 200, approve.text
    approved_task_id = approve.json()["task_id"]

    candidate_b = create_candidate(client, monkeypatch, project["id"])
    candidate_c = create_candidate(client, monkeypatch, project["id"])
    batch = client.post(
        "/api/task-candidates/batch-approve",
        json={"candidate_ids": [str(candidate_b.id), str(candidate_c.id)]},
    )
    assert batch.status_code == 200, batch.text
    task_ids = [
        item["task_id"]
        for item in batch.json()["results"]
        if item["status"] == "approved"
    ]

    for task_id in [approved_task_id, *task_ids]:
        events = get_task_activity(task_id)
        assert len(events) >= 1
        assert any(
            event.action_type == TaskActivityAction.task_created for event in events
        )


def test_all_existing_tasks_have_task_created_event_backfill_or_write(client):
    with SessionLocal() as db:
        task_ids = [str(item[0]) for item in db.query(Task.id).all()]
        event_task_ids = {
            str(item[0])
            for item in db.query(TaskActivityEvent.task_id)
            .filter(TaskActivityEvent.action_type == TaskActivityAction.task_created)
            .all()
        }

    missing = [task_id for task_id in task_ids if task_id not in event_task_ids]
    assert missing == []


def test_get_task_activity_returns_newest_first(client):
    project = make_project(client)
    task = make_task(client, project["id"])

    update = client.put(
        f"/api/tasks/{task['id']}",
        json={"status": "in_progress", "title": "Newest title"},
    )
    assert update.status_code == 200, update.text

    resp = client.get(f"/api/tasks/{task['id']}/activity")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert len(data) >= 2
    assert data[0]["occurred_at"] >= data[1]["occurred_at"]


def test_get_task_activity_tie_breaks_by_id_desc(client):
    project = make_project(client)
    task = make_task(client, project["id"])
    update = client.put(f"/api/tasks/{task['id']}", json={"title": "Second event"})
    assert update.status_code == 200, update.text

    with SessionLocal() as db:
        events = (
            db.query(TaskActivityEvent)
            .filter(TaskActivityEvent.task_id == uuid.UUID(task["id"]))
            .all()
        )
        for event in events:
            event.occurred_at = events[0].occurred_at
        db.commit()

    resp = client.get(f"/api/tasks/{task['id']}/activity")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    ids = [uuid.UUID(item["id"]) for item in data]
    assert ids == sorted(ids, reverse=True)


def test_get_task_activity_returns_404_for_missing_task(client):
    resp = client.get(f"/api/tasks/{uuid.uuid4()}/activity")
    assert resp.status_code == 404
