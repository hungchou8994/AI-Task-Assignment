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


def make_task(client, title=None, project_id=None, **kwargs):
    """Helper: create a task, assert 201, return response dict."""
    if project_id is None:
        project = make_project(client)
        project_id = project["id"]
    payload = {"title": title or f"Task-{unique()}", "project_id": project_id, **kwargs}
    resp = client.post("/api/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_person(client, name=None, email=None):
    """Helper: create a person, assert 201, return response dict."""
    payload = {"name": name or f"Person-{unique()}"}
    if email:
        payload["email"] = email
    resp = client.post("/api/people", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- TASK-01: create task ---


def test_create_task_defaults(client):
    """POST /api/tasks with title only — defaults status=todo, priority=medium."""
    project = make_project(client)
    title = f"Task-{unique()}"
    resp = client.post("/api/tasks", json={"title": title, "project_id": project["id"]})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == title
    assert data["status"] == "todo"
    assert data["priority"] == "medium"
    assert data["assignee_id"] is None
    assert data["project_id"] == project["id"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_task_with_all_fields(client):
    """POST /api/tasks with all fields — all stored and returned."""
    project = make_project(client)
    resp = client.post(
        "/api/tasks",
        json={
            "title": f"Full-{unique()}",
            "project_id": project["id"],
            "description": "desc",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-12-31",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"
    assert data["due_date"] == "2026-12-31"
    assert data["description"] == "desc"
    assert data["project_id"] == project["id"]


# --- TASK-02: list tasks ---


def test_list_tasks_returns_list(client):
    """GET /api/tasks → 200 and a JSON array."""
    make_task(client)  # ensure at least one exists
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


# --- TASK-06: update task ---


def test_update_task_partial(client):
    """PUT /api/tasks/{id} with only title — only title changes, other fields intact."""
    task = make_task(client, status="todo", priority="low")
    task_id = task["id"]
    new_title = f"Updated-{unique()}"
    resp = client.put(f"/api/tasks/{task_id}", json={"title": new_title})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == new_title
    # status and priority unchanged (exclude_unset=True)
    assert data["status"] == "todo"
    assert data["priority"] == "low"


def test_update_task_not_found(client):
    """PUT /api/tasks/{random-uuid} → 404."""
    resp = client.put(f"/api/tasks/{uuid.uuid4()}", json={"title": "nope"})
    assert resp.status_code == 404


def test_update_task_rejects_unsupported_fields(client):
    """PUT /api/tasks/{id} with unsupported fields returns 422 (no silent drops)."""
    task = make_task(client)
    resp = client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "Still valid", "needs_review": False},
    )
    assert resp.status_code == 422


# --- TASK-07: delete task ---


def test_delete_task(client):
    """DELETE /api/tasks/{id} → 204; subsequent GET → 404."""
    task = make_task(client)
    task_id = task["id"]
    resp = client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204
    # Confirm gone — GET list and check id not present
    all_tasks = client.get("/api/tasks").json()
    assert not any(t["id"] == task_id for t in all_tasks)


def test_delete_task_not_found(client):
    """DELETE /api/tasks/{random-uuid} → 404."""
    resp = client.delete(f"/api/tasks/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- ASGN-01: assign task ---


def test_assign_task(client):
    """PATCH /api/tasks/{id} with valid assignee_id → 200, assignee_id set."""
    person = make_person(client)
    task = make_task(client)
    resp = client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": person["id"]})
    assert resp.status_code == 200
    assert resp.json()["assignee_id"] == person["id"]


def test_assign_nonexistent_person(client):
    """PATCH with non-existent person UUID → 404."""
    task = make_task(client)
    resp = client.patch(
        f"/api/tasks/{task['id']}", json={"assignee_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404


# --- ASGN-02: unassign task ---


def test_unassign_task(client):
    """PATCH /api/tasks/{id} with assignee_id=null → 200, assignee_id is null."""
    person = make_person(client)
    task = make_task(client)
    # Assign first
    client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": person["id"]})
    # Now unassign
    resp = client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": None})
    assert resp.status_code == 200
    assert resp.json()["assignee_id"] is None


# --- PROJECT FILTERING ---


def test_list_tasks_filter_by_project(client):
    """GET /api/tasks?project_id={uuid} → only tasks in that project."""
    project1 = make_project(client, name="Project 1")
    project2 = make_project(client, name="Project 2")

    task1 = make_task(client, title="Task in Project 1", project_id=project1["id"])
    task2 = make_task(client, title="Task in Project 2", project_id=project2["id"])

    # Filter by project1
    resp = client.get(f"/api/tasks?project_id={project1['id']}")
    assert resp.status_code == 200
    tasks = resp.json()
    task_ids = [t["id"] for t in tasks]
    assert task1["id"] in task_ids
    assert task2["id"] not in task_ids


def test_create_task_requires_valid_project_id(client):
    """POST /api/tasks with invalid project_id → 404."""
    resp = client.post(
        "/api/tasks",
        json={"title": "Task with invalid project", "project_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
    assert "Project not found" in resp.json()["detail"]
