import uuid
import pytest
from fastapi.testclient import TestClient


def unique() -> str:
    return str(uuid.uuid4())


def make_workspace(client, name=None, description=None):
    """Helper: create a workspace, assert 201, return response dict."""
    payload = {"name": name or f"Workspace-{unique()}"}
    if description:
        payload["description"] = description
    resp = client.post("/api/workspaces", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_project(client, workspace_id=None, name=None, description=None):
    """Helper: create a project in a workspace, assert 201, return response dict."""
    if workspace_id is None:
        workspace = make_workspace(client)
        workspace_id = workspace["id"]
    payload = {"name": name or f"Project-{unique()}"}
    if description:
        payload["description"] = description
    resp = client.post(f"/api/workspaces/{workspace_id}/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_person(client, name=None, email=None):
    payload = {"name": name or f"Person-{unique()}"}
    if email is not None:
        payload["email"] = email
    resp = client.post("/api/people", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_task(client, title=None, project_id=None, assignee_id=None):
    if project_id is None:
        project = make_project(client)
        project_id = project["id"]
    payload = {"title": title or f"Task-{unique()}", "project_id": project_id}
    if assignee_id:
        payload["assignee_id"] = assignee_id
    resp = client.post("/api/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- PEOP-01: create person ---


def test_create_person_name_only(client):
    """POST /api/people with name only → 201, email null."""
    name = f"Alice-{unique()}"
    resp = client.post("/api/people", json={"name": name})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert data["email"] is None
    assert "id" in data
    assert "created_at" in data


def test_create_person_with_email(client):
    """POST /api/people with email → 201, email stored."""
    email = f"alice-{unique()}@example.com"
    resp = client.post("/api/people", json={"name": "Alice", "email": email})
    assert resp.status_code == 201
    assert resp.json()["email"] == email


def test_duplicate_email_returns_409(client):
    """POST /api/people with duplicate email → 409 Conflict."""
    email = f"dup-{unique()}@example.com"
    make_person(client, email=email)
    resp = client.post("/api/people", json={"name": "AnotherAlice", "email": email})
    assert resp.status_code == 409


# --- PEOP-02: list people ---


def test_list_people_returns_list(client):
    """GET /api/people → 200 and JSON array."""
    make_person(client)
    resp = client.get("/api/people")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


# --- PEOP-03: delete person, tasks become unassigned ---


def test_delete_person(client):
    """DELETE /api/people/{id} → 204."""
    person = make_person(client)
    resp = client.delete(f"/api/people/{person['id']}")
    assert resp.status_code == 204


def test_delete_person_not_found(client):
    """DELETE /api/people/{random-uuid} → 404."""
    resp = client.delete(f"/api/people/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_delete_person_nulls_task_assignments(client):
    """Delete person → their task's assignee_id becomes null (ON DELETE SET NULL)."""
    person = make_person(client)
    task = make_task(client, assignee_id=person["id"])

    # Confirm assignment
    assigned = client.get("/api/tasks").json()
    matched = next((t for t in assigned if t["id"] == task["id"]), None)
    assert matched is not None
    assert matched["assignee_id"] == person["id"]

    # Delete person
    del_resp = client.delete(f"/api/people/{person['id']}")
    assert del_resp.status_code == 204

    # Task still exists, assignee_id is now null
    all_tasks = client.get("/api/tasks").json()
    task_after = next((t for t in all_tasks if t["id"] == task["id"]), None)
    assert task_after is not None, "Task should still exist after person deletion"
    assert task_after["assignee_id"] is None, (
        "assignee_id must be null after person deleted"
    )
