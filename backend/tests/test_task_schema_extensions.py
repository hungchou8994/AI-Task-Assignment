"""Integration tests for task schema extensions (archive, labels, estimates, deps)."""

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import (
    FeedbackEvent,
    Label,
    Organization,
    OrgMembership,
    Person,
    Project,
    Task,
    TaskActivityEvent,
    TaskCandidate,
    TaskDependency,
    TaskEstimate,
    TaskLabel,
    TaskStatusHistory,
    User,
    Workspace,
    WorkspaceMembership,
    WebhookSubscription,
    WebhookDelivery,
)


def _patch_sqlite_json_columns():
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


@pytest.fixture
def api_client():
    _patch_sqlite_json_columns()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
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
            WebhookSubscription.__table__,
            WebhookDelivery.__table__,
        ],
    )
    setup = TestingSessionLocal()
    user = User(email="schema-ext@example.com", hashed_password="x")
    setup.add(user)
    setup.commit()
    setup.refresh(user)
    setup.close()

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def _workspace_and_project(client: TestClient):
    w = client.post("/api/workspaces", json={"name": f"W-{uuid.uuid4()}"})
    assert w.status_code == 201
    wid = w.json()["id"]
    p = client.post(f"/api/workspaces/{wid}/projects", json={"name": "P1"})
    assert p.status_code == 201
    return wid, p.json()["id"]


def test_archive_hides_from_list_include_archived(api_client: TestClient):
    _, pid = _workspace_and_project(api_client)
    t = api_client.post(
        "/api/tasks", json={"title": "Archivable", "project_id": pid}
    )
    assert t.status_code == 201
    tid = t.json()["id"]
    ar = api_client.post(f"/api/tasks/{tid}/archive")
    assert ar.status_code == 200
    assert ar.json()["archived_at"] is not None
    listed = api_client.get("/api/tasks")
    assert tid not in {x["id"] for x in listed.json()}
    inc = api_client.get("/api/tasks?include_archived=true")
    assert tid in {x["id"] for x in inc.json()}
    un = api_client.post(f"/api/tasks/{tid}/unarchive")
    assert un.status_code == 200
    assert un.json()["archived_at"] is None


def test_status_history_on_put_status(api_client: TestClient):
    _, pid = _workspace_and_project(api_client)
    t = api_client.post("/api/tasks", json={"title": "S", "project_id": pid})
    tid = t.json()["id"]
    api_client.put(f"/api/tasks/{tid}", json={"status": "in_progress"})
    h = api_client.get(f"/api/tasks/{tid}/status-history")
    assert h.status_code == 200
    rows = h.json()
    assert len(rows) >= 1
    assert rows[0]["to_status"] == "in_progress"
    assert rows[0]["from_status"] == "todo"


def test_patch_labels_and_estimates(api_client: TestClient):
    wid, pid = _workspace_and_project(api_client)
    lb = api_client.post(
        f"/api/workspaces/{wid}/labels", json={"name": "bug", "color": "#f00"}
    )
    assert lb.status_code == 201
    lid = lb.json()["id"]
    t = api_client.post("/api/tasks", json={"title": "L", "project_id": pid})
    tid = t.json()["id"]
    p = api_client.patch(
        f"/api/tasks/{tid}",
        json={"label_ids": [lid], "estimated_hours": 3.5},
    )
    assert p.status_code == 200
    body = p.json()
    assert body["label_ids"] == [lid]
    assert body["estimated_hours"] == 3.5


def test_task_dependency_create_and_duplicate(api_client: TestClient):
    _, pid = _workspace_and_project(api_client)
    a = api_client.post("/api/tasks", json={"title": "Blocker", "project_id": pid})
    b = api_client.post("/api/tasks", json={"title": "Blocked", "project_id": pid})
    aid, bid = a.json()["id"], b.json()["id"]
    r1 = api_client.post(
        f"/api/tasks/{bid}/dependencies",
        json={"blocks_task_id": aid, "dependency_type": "blocks"},
    )
    assert r1.status_code == 201
    assert r1.json()["dependent_task_id"] == bid
    assert r1.json()["blocks_task_id"] == aid
    r2 = api_client.post(
        f"/api/tasks/{bid}/dependencies",
        json={"blocks_task_id": aid, "dependency_type": "blocks"},
    )
    assert r2.status_code == 409
