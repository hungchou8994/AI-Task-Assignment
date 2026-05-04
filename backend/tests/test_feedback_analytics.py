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
    FeedbackEvent,
    TaskCandidate,
)
from app.services import extraction_service as _extraction_svc
from app.routers import (
    ai,
    feedback_analytics,
    people,
    task_candidates,
    tasks,
    workspaces,
)

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
            if path == "/api/feedback-analytics":
                response = feedback_analytics.get_feedback_analytics(
                    db=self.db,
                    project_id=uuid.UUID(query["project_id"][0]),
                    period=query.get("period", ["week"])[0],
                    current_user=self.current_user,
                )
                return self._ok(response)
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
            raise AssertionError(f"Unhandled PATCH path: {path}")
        except HTTPException as exc:
            return self._error(exc)


@pytest.fixture
def client(tmp_path):
    db, current_user, cleanup = create_test_db(
        user_email="feedback-analytics@example.com",
        caller_globals=globals(),
    )
    try:
        yield DirectClient(db=db, current_user=current_user)
    finally:
        cleanup()


def mock_extraction_result(recommendation_ids=None, confidence=0.7):
    _ = recommendation_ids
    return ExtractionServiceResult(
        outcome=ExtractionOutcome(
            source_summary="Feedback analytics source summary.",
            tasks=(
                ExtractedTaskItem(
                    title=f"Candidate-{unique()}",
                    description="Candidate generated for feedback tracking.",
                    priority="medium",
                    due_date=date(2026, 4, 1),
                    confidence_score=confidence,
                ),
            ),
        ),
        source_excerpt="Seed candidate for feedback event test.",
    )


def create_candidate(
    client, monkeypatch, project_id, recommendation_ids=None, confidence=0.7
):
    result = mock_extraction_result(
        recommendation_ids=recommendation_ids, confidence=confidence
    )
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
            "content": "Seed candidate for feedback event test.",
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


def get_feedback_events_for_candidate(candidate_id):
    candidate_uuid = uuid.UUID(str(candidate_id))
    with SessionLocal() as db:
        return (
            db.query(FeedbackEvent)
            .filter(FeedbackEvent.candidate_id == candidate_uuid)
            .order_by(FeedbackEvent.created_at.asc())
            .all()
        )


def test_approve_emits_accept_event_with_timestamp(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])

    approve = client.post(f"/api/task-candidates/{candidate.id}/approve")
    assert approve.status_code == 200, approve.text

    events = get_feedback_events_for_candidate(candidate.id)
    assert len(events) == 1
    assert events[0].action.value == "accept"
    assert events[0].acted_at is not None


def test_reject_emits_reject_event_with_timestamp(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])

    reject = client.post(f"/api/task-candidates/{candidate.id}/reject")
    assert reject.status_code == 200, reject.text

    events = get_feedback_events_for_candidate(candidate.id)
    assert len(events) == 1
    assert events[0].action.value == "reject"
    assert events[0].acted_at is not None


def test_edit_emits_delta_entries_only_for_changed_fields(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])
    original_title = candidate.title

    edit = client.patch(
        f"/api/task-candidates/{candidate.id}",
        json={
            "title": "Updated title",
            "priority": "high",
            "description": candidate.description,
        },
    )
    assert edit.status_code == 200, edit.text

    events = get_feedback_events_for_candidate(candidate.id)
    assert len(events) == 1
    assert events[0].action.value == "edit"
    assert sorted(events[0].field_deltas.keys()) == ["priority", "title"]
    assert events[0].field_deltas["title"] == {
        "original": original_title,
        "final": "Updated title",
    }


def test_patch_noop_does_not_emit_edit_event(client, monkeypatch):
    project = make_project(client)
    candidate = create_candidate(client, monkeypatch, project["id"])

    edit = client.patch(
        f"/api/task-candidates/{candidate.id}",
        json={"title": candidate.title},
    )
    assert edit.status_code == 200, edit.text

    events = get_feedback_events_for_candidate(candidate.id)
    assert len(events) == 0


def test_approve_captures_selected_assignee_rank_bins(client, monkeypatch):
    project = make_project(client)
    person_1 = make_person(client)
    person_2 = make_person(client)
    person_3 = make_person(client)
    person_4 = make_person(client)

    recommendation_ids = [person_1["id"], person_2["id"], person_3["id"]]
    cases = [
        (person_1["id"], "top_1"),
        (person_2["id"], "top_2"),
        (person_3["id"], "top_3"),
        (person_4["id"], "not_recommended"),
    ]

    for selected_assignee_id, expected_rank in cases:
        candidate = create_candidate(
            client,
            monkeypatch,
            project["id"],
            recommendation_ids=recommendation_ids,
        )
        update = client.patch(
            f"/api/task-candidates/{candidate.id}",
            json={"selected_assignee_id": selected_assignee_id},
        )
        assert update.status_code == 200, update.text

        approve = client.post(f"/api/task-candidates/{candidate.id}/approve")
        assert approve.status_code == 200, approve.text

        accept_events = [
            event
            for event in get_feedback_events_for_candidate(candidate.id)
            if event.action.value == "accept"
        ]
        assert len(accept_events) == 1
        assert accept_events[0].selected_assignee_id is not None
        assert accept_events[0].selected_assignee_rank == expected_rank


def _field_metric(metrics, field_name):
    return next(item for item in metrics if item["field"] == field_name)


def test_feedback_analytics_endpoint_returns_rate_and_accuracy_metrics(
    client, monkeypatch
):
    project = make_project(client)
    person_1 = make_person(client)
    person_2 = make_person(client)
    person_3 = make_person(client)
    person_4 = make_person(client)
    recommendation_ids = [person_1["id"], person_2["id"], person_3["id"]]

    candidate_a = create_candidate(
        client,
        monkeypatch,
        project["id"],
        recommendation_ids=recommendation_ids,
    )
    approve_a = client.post(f"/api/task-candidates/{candidate_a.id}/approve")
    assert approve_a.status_code == 200, approve_a.text

    candidate_b = create_candidate(
        client,
        monkeypatch,
        project["id"],
        recommendation_ids=recommendation_ids,
    )
    edit_b = client.patch(
        f"/api/task-candidates/{candidate_b.id}",
        json={
            "title": "Edited title",
            "description": "Edited description",
            "selected_assignee_id": person_4["id"],
        },
    )
    assert edit_b.status_code == 200, edit_b.text
    approve_b = client.post(f"/api/task-candidates/{candidate_b.id}/approve")
    assert approve_b.status_code == 200, approve_b.text

    candidate_c = create_candidate(
        client,
        monkeypatch,
        project["id"],
        recommendation_ids=recommendation_ids,
    )
    reject_c = client.post(f"/api/task-candidates/{candidate_c.id}/reject")
    assert reject_c.status_code == 200, reject_c.text

    metrics_resp = client.get(
        f"/api/feedback-analytics?project_id={project['id']}&period=day"
    )
    assert metrics_resp.status_code == 200, metrics_resp.text

    payload = metrics_resp.json()
    assert payload["project_id"] == project["id"]
    assert payload["period"] == "day"
    assert len(payload["rate_series"]) == 1

    bucket = payload["rate_series"][0]
    assert bucket["total_actions"] == 4
    assert bucket["accept_rate"] == 0.5
    assert bucket["reject_rate"] == 0.25
    assert bucket["edit_rate"] == 0.25

    title_metric = _field_metric(payload["field_accuracy"], "title")
    assert title_metric["total_considered"] == 3
    assert title_metric["accurate_count"] == 1
    assert title_metric["accuracy_rate"] == 0.3333

    priority_metric = _field_metric(payload["field_accuracy"], "priority")
    assert priority_metric["total_considered"] == 2
    assert priority_metric["accurate_count"] == 2
    assert priority_metric["accuracy_rate"] == 1.0

    assignee = payload["assignee_accuracy"]
    assert assignee["total_accepts"] == 2
    assert assignee["top_1_count"] == 1
    assert assignee["not_recommended_count"] == 1
    assert assignee["top_1_rate"] == 0.5
    assert assignee["not_recommended_rate"] == 0.5


def test_feedback_analytics_endpoint_handles_empty_project_state(client):
    project = make_project(client)

    metrics_resp = client.get(
        f"/api/feedback-analytics?project_id={project['id']}&period=week"
    )
    assert metrics_resp.status_code == 200, metrics_resp.text

    payload = metrics_resp.json()
    assert payload["rate_series"] == []
    assert payload["assignee_accuracy"]["total_accepts"] == 0
    assert all(item["accuracy_rate"] == 0 for item in payload["field_accuracy"])


def test_feedback_analytics_includes_batch_accept_and_reject_events(
    client, monkeypatch
):
    project = make_project(client)

    first = create_candidate(client, monkeypatch, project["id"])
    second = create_candidate(client, monkeypatch, project["id"])

    approve = client.post(
        "/api/task-candidates/batch-approve",
        json={"candidate_ids": [str(first.id)]},
    )
    assert approve.status_code == 200, approve.text
    reject = client.post(
        "/api/task-candidates/batch-reject",
        json={"candidate_ids": [str(second.id)]},
    )
    assert reject.status_code == 200, reject.text

    metrics_resp = client.get(
        f"/api/feedback-analytics?project_id={project['id']}&period=day"
    )
    assert metrics_resp.status_code == 200, metrics_resp.text

    payload = metrics_resp.json()
    assert len(payload["rate_series"]) == 1
    bucket = payload["rate_series"][0]
    assert bucket["total_actions"] == 2
    assert bucket["accept_rate"] == 0.5
    assert bucket["reject_rate"] == 0.5
