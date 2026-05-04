import uuid
import pytest
from app.models import Source, TaskSource, TaskCandidate
from app.routers import ai, tasks
from types import SimpleNamespace
from tests.helpers import (
    make_person,
    make_project,
    persist_extraction_tasks,
)
from app.schemas import (
    ExtractedTaskItem,
    ExtractionOutcome,
    ExtractTasksResult,
)


def test_extraction_creates_source_and_links_tasks(client, monkeypatch):
    project = make_project(client)
    source_content = "Extract these: Task 1 and Task 2"

    outcome = ExtractionOutcome(
        source_summary="Test Summary",
        tasks=(
            ExtractedTaskItem(
                title="Task 1",
                description="Desc 1",
                priority="medium",
                confidence_score=0.9,
            ),
            ExtractedTaskItem(
                title="Task 2",
                description="Desc 2",
                priority="high",
                confidence_score=0.8,
            ),
        ),
    )

    class FakeUseCase:
        async def execute(self, command):
            task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="Test excerpt",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(task_ids),
            )

    monkeypatch.setattr(ai, "get_extract_tasks_use_case", lambda db: FakeUseCase())

    resp = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": source_content,
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]

    job_status = client.get(f"/api/ai/jobs/{job_id}")
    assert job_status.json()["status"] == "done"

    created_task_ids = job_status.json()["result"]["created_task_ids"]
    assert len(created_task_ids) == 2

    db = client.db
    sources = (
        db.query(Source).filter(Source.project_id == uuid.UUID(project["id"])).all()
    )
    assert len(sources) == 1
    assert sources[0].source_type == "text"
    assert sources[0].summary == "Test Summary"
    assert (sources[0].payload or {}).get("raw_text") == source_content

    for task_id in created_task_ids:
        links = (
            db.query(TaskSource)
            .filter(TaskSource.task_id == uuid.UUID(str(task_id)))
            .all()
        )
        assert len(links) == 1
        assert links[0].source_id == sources[0].id

        api_resp = client.get(f"/api/tasks/{task_id}/sources")
        assert api_resp.status_code == 200
        assert len(api_resp.json()) == 1
        assert api_resp.json()[0]["source_id"] == str(sources[0].id)
        assert api_resp.json()[0]["source"]["summary"] == "Test Summary"


def test_manual_approve_resolves_and_links_source(client, monkeypatch):
    project = make_project(client)
    project_id = uuid.UUID(project["id"])

    db = client.db
    candidate = TaskCandidate(
        project_id=project_id,
        title="Manual Candidate",
        description="Manual Desc",
        priority="medium",
        confidence_score=0.7,
        source_type="url",
        source_excerpt="http://example.com excerpt",
        source_summary="Example Summary",
        assignee_recommendations=[],
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    resp = client.post(f"/api/task-candidates/{str(candidate.id)}/approve")
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["task_id"]

    sources = db.query(Source).filter(Source.project_id == project_id).all()
    assert len(sources) == 1
    assert sources[0].source_type == "url"

    links = db.query(TaskSource).filter(TaskSource.task_id == uuid.UUID(task_id)).all()
    assert len(links) == 1
    assert links[0].source_id == sources[0].id

    # Deduplication: second candidate with same source attributes
    candidate2 = TaskCandidate(
        project_id=project_id,
        title="Manual Candidate 2",
        description="Manual Desc 2",
        priority="low",
        confidence_score=0.6,
        source_type="url",
        source_excerpt="http://example.com excerpt",
        source_summary="Example Summary",
        assignee_recommendations=[],
    )
    db.add(candidate2)
    db.commit()
    db.refresh(candidate2)

    resp2 = client.post(f"/api/task-candidates/{str(candidate2.id)}/approve")
    assert resp2.status_code == 200
    task_id2 = resp2.json()["task_id"]

    sources = db.query(Source).filter(Source.project_id == project_id).all()
    assert len(sources) == 1

    links = db.query(TaskSource).filter(TaskSource.source_id == sources[0].id).all()
    assert len(links) == 2


def test_extraction_deduplicates_sources(client, monkeypatch):
    project = make_project(client)
    content = "Same Content"

    outcome = ExtractionOutcome(
        source_summary="Duplicate Summary",
        tasks=(
            ExtractedTaskItem(
                title="Unique Task",
                description="Desc",
                priority="medium",
                confidence_score=0.9,
            ),
        ),
    )

    class FakeUseCase:
        async def execute(self, command):
            task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="Duplicate excerpt",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(task_ids),
            )

    monkeypatch.setattr(ai, "get_extract_tasks_use_case", lambda db: FakeUseCase())

    payload = {
        "source_type": "text",
        "content": content,
        "project_id": project["id"],
    }
    resp1 = client.post("/api/ai/extract-tasks", json=payload)
    assert resp1.status_code == 200

    resp2 = client.post("/api/ai/extract-tasks", json=payload)
    assert resp2.status_code == 200

    db = client.db
    sources = (
        db.query(Source).filter(Source.project_id == uuid.UUID(project["id"])).all()
    )
    # Only one Source row because content hash is identical
    assert len(sources) == 1


def test_url_source_persists_uri(client, monkeypatch):
    project = make_project(client)
    source_url = "https://example.com/path"

    outcome = ExtractionOutcome(
        source_summary="URL summary",
        tasks=(
            ExtractedTaskItem(
                title="Task from url",
                description="Desc",
                priority="medium",
                confidence_score=0.9,
            ),
        ),
    )

    class FakeUseCase:
        async def execute(self, command):
            task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="Fetched page text",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(task_ids),
            )

    monkeypatch.setattr(ai, "get_extract_tasks_use_case", lambda db: FakeUseCase())

    resp = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "url",
            "content": source_url,
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 200, resp.text

    db = client.db
    source = (
        db.query(Source).filter(Source.project_id == uuid.UUID(project["id"])).one()
    )
    assert source.uri == source_url


def test_project_sources_endpoint_returns_project_sources(client, monkeypatch):
    project = make_project(client)

    outcome = ExtractionOutcome(
        source_summary="Project Sources Summary",
        tasks=(
            ExtractedTaskItem(
                title="Task from project source",
                description="Desc",
                priority="medium",
                confidence_score=0.9,
            ),
        ),
    )

    class FakeUseCase:
        async def execute(self, command):
            task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="Project sources excerpt",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(task_ids),
            )

    monkeypatch.setattr(ai, "get_extract_tasks_use_case", lambda db: FakeUseCase())

    resp = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": "source content for project endpoint",
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 200, resp.text

    sources_resp = client.get(f"/api/projects/{project['id']}/sources")
    assert sources_resp.status_code == 200, sources_resp.text
    items = sources_resp.json()
    assert len(items) >= 1
    assert all(item["project_id"] == project["id"] for item in items)
    assert all(item["payload"] == {} for item in items)


def test_low_confidence_recommendations_stay_manual_only(client, monkeypatch):
    person = make_person(client)
    project = make_project(client)

    outcome = ExtractionOutcome(
        source_summary="Low confidence summary",
        tasks=(
            ExtractedTaskItem(
                title="Low confidence candidate",
                description="Needs manual assignment",
                priority="medium",
                confidence_score=0.6,
            ),
        ),
    )

    class FakeUseCase:
        async def execute(self, command):
            recs = [
                {
                    "rank": 1,
                    "person_id": person["id"],
                    "name": person["name"],
                    "confidence_score": 0.92,
                    "reasoning": "Top candidate",
                    "auto_apply_eligible": True,
                }
            ]
            task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="low confidence excerpt",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
                recommendations_by_task=[recs],
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(task_ids),
            )

    monkeypatch.setattr(ai, "get_extract_tasks_use_case", lambda db: FakeUseCase())

    resp = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": "low confidence source",
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 200, resp.text

    candidate = (
        client.db.query(TaskCandidate)
        .filter(
            TaskCandidate.project_id == uuid.UUID(project["id"]),
            TaskCandidate.title == "Low confidence candidate",
        )
        .order_by(TaskCandidate.created_at.desc(), TaskCandidate.id.desc())
        .first()
    )
    assert candidate is not None
    assert candidate.selected_assignee_id is None
    assert len(candidate.assignee_recommendations) == 1
    rec = candidate.assignee_recommendations[0]
    assert rec["reason_code"] == "best_fit"
    assert rec["auto_apply_eligible"] is True
    assert 0 <= rec["workload_score"] <= 1
    assert 0 <= rec["skills_score"] <= 1
    assert 0 <= rec["historical_fit_score"] <= 1


def test_high_confidence_recommendations_auto_apply_and_expose_explanations(
    client, monkeypatch
):
    person = make_person(client)
    project = make_project(client)

    outcome = ExtractionOutcome(
        source_summary="High confidence summary",
        tasks=(
            ExtractedTaskItem(
                title="High confidence candidate",
                description="Can auto-assign",
                priority="high",
                confidence_score=0.95,
            ),
        ),
    )

    class FakeUseCase:
        async def execute(self, command):
            recs = [
                {
                    "rank": 1,
                    "person_id": person["id"],
                    "name": person["name"],
                    "confidence_score": 0.93,
                    "reasoning": "Best candidate",
                    "auto_apply_eligible": True,
                }
            ]
            task_ids = persist_extraction_tasks(
                client.db,
                project_id=command.project_id,
                source_type=command.source_type,
                source_content=command.content,
                source_excerpt="high confidence excerpt",
                source_summary=outcome.source_summary,
                tasks=outcome.tasks,
                recommendations_by_task=[recs],
            )
            return ExtractTasksResult(
                outcome=outcome,
                created_task_ids=tuple(task_ids),
            )

    monkeypatch.setattr(ai, "get_extract_tasks_use_case", lambda db: FakeUseCase())

    resp = client.post(
        "/api/ai/extract-tasks",
        json={
            "source_type": "text",
            "content": "high confidence source",
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 200, resp.text

    candidate = (
        client.db.query(TaskCandidate)
        .filter(
            TaskCandidate.project_id == uuid.UUID(project["id"]),
            TaskCandidate.title == "High confidence candidate",
        )
        .order_by(TaskCandidate.created_at.desc(), TaskCandidate.id.desc())
        .first()
    )
    assert candidate is not None
    assert str(candidate.selected_assignee_id) == person["id"]
    assert candidate.approved_task_id is not None

    recs_response = tasks.get_task_assignee_recommendations(
        task_id=candidate.approved_task_id,
        db=client.db,
        current_user=client.current_user,
    )
    assert len(recs_response.recommendations) == 1
    rec = recs_response.recommendations[0]
    assert rec.reason_code == "best_fit"
    assert rec.auto_apply_eligible is True
    assert rec.workload_score is not None
    assert rec.skills_score is not None
    assert rec.historical_fit_score is not None
