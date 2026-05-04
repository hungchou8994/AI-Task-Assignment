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


def make_project(client, workspace_id, name=None, description=None):
    """Helper: create a project in a workspace, assert 201, return response dict."""
    payload = {"name": name or f"Project-{unique()}"}
    if description:
        payload["description"] = description
    resp = client.post(f"/api/workspaces/{workspace_id}/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- WORKSPACE TESTS ---


def test_create_workspace_returns_201(client):
    """POST /api/workspaces with name → 201 with WorkspaceResponse."""
    name = f"Workspace-{unique()}"
    resp = client.post("/api/workspaces", json={"name": name})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert data["description"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_workspace_with_description(client):
    """POST /api/workspaces with name and description."""
    name = f"Workspace-{unique()}"
    description = "Test description"
    resp = client.post(
        "/api/workspaces", json={"name": name, "description": description}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert data["description"] == description


def test_list_workspaces_returns_list(client):
    """GET /api/workspaces → 200 and a JSON array."""
    make_workspace(client)  # ensure at least one exists
    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_get_workspace_by_id(client):
    """GET /api/workspaces/{id} → 200 with workspace data."""
    workspace = make_workspace(client)
    resp = client.get(f"/api/workspaces/{workspace['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == workspace["id"]
    assert resp.json()["name"] == workspace["name"]


def test_get_workspace_404_not_found(client):
    """GET /api/workspaces/{random-uuid} → 404."""
    resp = client.get(f"/api/workspaces/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- PROJECT TESTS ---


def test_create_project_in_workspace(client):
    """POST /api/workspaces/{id}/projects → 201 with ProjectResponse."""
    workspace = make_workspace(client)
    name = f"Project-{unique()}"
    resp = client.post(
        f"/api/workspaces/{workspace['id']}/projects",
        json={"name": name, "description": "Test project"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert data["description"] == "Test project"
    assert data["workspace_id"] == workspace["id"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_list_projects_in_workspace(client):
    """GET /api/workspaces/{id}/projects → list of projects."""
    workspace = make_workspace(client)
    project = make_project(client, workspace["id"])
    resp = client.get(f"/api/workspaces/{workspace['id']}/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    assert any(p["id"] == project["id"] for p in projects)


def test_create_project_workspace_not_found_404(client):
    """POST /api/workspaces/{random-uuid}/projects → 404."""
    resp = client.post(
        f"/api/workspaces/{uuid.uuid4()}/projects",
        json={"name": "Test"},
    )
    assert resp.status_code == 404


def test_list_projects_workspace_not_found_404(client):
    """GET /api/workspaces/{random-uuid}/projects → 404."""
    resp = client.get(f"/api/workspaces/{uuid.uuid4()}/projects")
    assert resp.status_code == 404
