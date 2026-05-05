import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.models import Task, TaskComment, TaskStatus, TaskPriority, User, WorkspaceMembership
from app.routers import task_comments, workspaces, tasks
from app.schemas import TaskCommentCreate, TaskCommentUpdate

from tests.helpers import BaseDirectClient, create_test_db, unique


class DirectClient(BaseDirectClient):
    def get(self, url: str, **kwargs):
        path, _ = self._parse(url)
        try:
            parts = path.strip("/").split("/")
            # GET /api/tasks/{task_id}/comments
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "tasks"
                and parts[3] == "comments"
            ):
                task_id = uuid.UUID(parts[2])
                return self._ok(
                    task_comments.list_task_comments(
                        task_id=task_id,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            raise AssertionError(f"Unhandled GET path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def post(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        try:
            parts = path.strip("/").split("/")
            # POST /api/workspaces
            if path == "/api/workspaces":
                response = workspaces.create_workspace(
                    payload=workspaces.WorkspaceCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response, 201)
            # POST /api/workspaces/{workspace_id}/projects
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "workspaces"
                and parts[3] == "projects"
            ):
                workspace_id = uuid.UUID(parts[2])
                response = workspaces.create_project(
                    workspace_id=workspace_id,
                    payload=workspaces.ProjectCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(response, 201)
            # POST /api/tasks
            if path == "/api/tasks":
                response = tasks.create_task(
                    payload=tasks.TaskCreate(**json),
                    db=self.db,
                    current_user=self.current_user,
                    background_tasks=BackgroundTasks(),
                )
                return self._ok(response, 201)
            # POST /api/tasks/{task_id}/comments
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "tasks"
                and parts[3] == "comments"
            ):
                task_id = uuid.UUID(parts[2])
                payload = TaskCommentCreate(**json)
                return self._ok(
                    task_comments.create_task_comment(
                        task_id=task_id,
                        payload=payload,
                        db=self.db,
                        current_user=self.current_user,
                    ),
                    status_code=201,
                )
            raise AssertionError(f"Unhandled POST path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def put(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        try:
            parts = path.strip("/").split("/")
            # PUT /api/tasks/{task_id}/comments/{comment_id}
            if (
                len(parts) == 5
                and parts[0] == "api"
                and parts[1] == "tasks"
                and parts[3] == "comments"
            ):
                task_id = uuid.UUID(parts[2])
                comment_id = uuid.UUID(parts[4])
                payload = TaskCommentUpdate(**json)
                return self._ok(
                    task_comments.update_task_comment(
                        task_id=task_id,
                        comment_id=comment_id,
                        payload=payload,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            raise AssertionError(f"Unhandled PUT path: {path}")
        except HTTPException as exc:
            return self._error(exc)

    def delete(self, url: str, **kwargs):
        path, _ = self._parse(url)
        try:
            parts = path.strip("/").split("/")
            # DELETE /api/tasks/{task_id}/comments/{comment_id}
            if (
                len(parts) == 5
                and parts[0] == "api"
                and parts[1] == "tasks"
                and parts[3] == "comments"
            ):
                task_id = uuid.UUID(parts[2])
                comment_id = uuid.UUID(parts[4])
                task_comments.delete_task_comment(
                    task_id=task_id,
                    comment_id=comment_id,
                    db=self.db,
                    current_user=self.current_user,
                )
                return self._ok(None, status_code=204)
            raise AssertionError(f"Unhandled DELETE path: {path}")
        except HTTPException as exc:
            return self._error(exc)


# ─── Fixtures ──────────────────────────────────────────────────────────────────


def make_workspace_via_client(client, name=None):
    resp = client.post("/api/workspaces", json={"name": name or f"WS-{unique()}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_project_via_client(client, workspace_id, name=None):
    resp = client.post(
        f"/api/workspaces/{workspace_id}/projects",
        json={"name": name or f"Proj-{unique()}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_task_via_client(client, project_id, title=None):
    resp = client.post(
        "/api/tasks",
        json={
            "title": title or f"Task-{unique()}",
            "project_id": project_id,
            "description": "test task",
            "priority": "medium",
            "status": "todo",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_second_user(db, email=None):
    """Create a second User in the test DB."""
    second = User(
        id=uuid.uuid4(),
        email=email or f"other-{unique()}@test.com",
        hashed_password="x",
    )
    db.add(second)
    db.commit()
    db.refresh(second)
    return second


@pytest.fixture
def ctx():
    db, user, cleanup = create_test_db(caller_globals=globals())
    # Re-fetch the actual User ORM object (create_test_db returns SimpleNamespace)
    from app.models import User as UserModel
    db_user = db.get(UserModel, user.id)
    client = DirectClient(db=db, current_user=user)
    ws = make_workspace_via_client(client)
    proj = make_project_via_client(client, ws["id"])
    task = make_task_via_client(client, proj["id"])
    yield {
        "db": db,
        "user": user,
        "db_user": db_user,
        "workspace": ws,
        "project": proj,
        "task": task,
        "client": client,
    }
    cleanup()


# ─── Tests ─────────────────────────────────────────────────────────────────────


def test_list_comments_empty(ctx):
    resp = ctx["client"].get(f"/api/tasks/{ctx['task']['id']}/comments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_comments_chronological(ctx):
    client = ctx["client"]
    task_id = ctx["task"]["id"]
    client.post(f"/api/tasks/{task_id}/comments", json={"body": "first"})
    client.post(f"/api/tasks/{task_id}/comments", json={"body": "second"})
    resp = client.get(f"/api/tasks/{task_id}/comments")
    assert resp.status_code == 200
    bodies = [c["body"] for c in resp.json()]
    assert bodies == ["first", "second"]


def test_create_comment_returns_201_with_body(ctx):
    task_id = ctx["task"]["id"]
    resp = ctx["client"].post(
        f"/api/tasks/{task_id}/comments", json={"body": "hello"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "hello"
    assert data["is_edited"] is False
    assert data["author_email"] == ctx["db_user"].email


def test_create_comment_rejects_whitespace_body(ctx):
    from pydantic import ValidationError

    with pytest.raises((ValidationError, HTTPException)):
        TaskCommentCreate(body="   ")


def test_create_comment_rejects_oversized_body(ctx):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TaskCommentCreate(body="x" * 10001)


def test_create_comment_non_member_returns_403(ctx):
    """A user with no workspace membership cannot post."""
    db = ctx["db"]
    task_id = ctx["task"]["id"]
    outsider = make_second_user(db)
    outsider_client = DirectClient(db=db, current_user=outsider)
    resp = outsider_client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "intruder"}
    )
    assert resp.status_code == 403


def test_update_own_comment_returns_200_with_is_edited(ctx):
    client = ctx["client"]
    task_id = ctx["task"]["id"]
    create_resp = client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "original"}
    )
    comment_id = create_resp.json()["id"]
    update_resp = client.put(
        f"/api/tasks/{task_id}/comments/{comment_id}", json={"body": "updated"}
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["body"] == "updated"
    assert data["is_edited"] is True


def test_update_other_users_comment_returns_403(ctx):
    db = ctx["db"]
    task_id = ctx["task"]["id"]
    client = ctx["client"]
    # Author creates a comment
    create_resp = client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "mine"}
    )
    comment_id = create_resp.json()["id"]
    # Another user added as member (so ensure_task_access passes) but is not author
    other = make_second_user(db)
    from app.models import Project
    proj_id = uuid.UUID(ctx["project"]["id"])
    proj = db.get(Project, proj_id)
    membership = WorkspaceMembership(
        workspace_id=proj.workspace_id,
        user_id=other.id,
        role="member",
    )
    db.add(membership)
    db.commit()
    other_client = DirectClient(db=db, current_user=other)
    resp = other_client.put(
        f"/api/tasks/{task_id}/comments/{comment_id}", json={"body": "hijacked"}
    )
    assert resp.status_code == 403


def test_delete_own_comment_returns_204(ctx):
    client = ctx["client"]
    task_id = ctx["task"]["id"]
    create_resp = client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "to delete"}
    )
    comment_id = create_resp.json()["id"]
    del_resp = client.delete(f"/api/tasks/{task_id}/comments/{comment_id}")
    assert del_resp.status_code == 204
    # Comment no longer appears in list
    list_resp = client.get(f"/api/tasks/{task_id}/comments")
    ids = [c["id"] for c in list_resp.json()]
    assert comment_id not in ids


def test_delete_by_non_author_non_admin_returns_403(ctx):
    db = ctx["db"]
    task_id = ctx["task"]["id"]
    client = ctx["client"]
    create_resp = client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "sensitive"}
    )
    comment_id = create_resp.json()["id"]
    # Other member (member role — not admin, not author)
    other = make_second_user(db)
    from app.models import Project
    proj_id = uuid.UUID(ctx["project"]["id"])
    proj = db.get(Project, proj_id)
    membership = WorkspaceMembership(
        workspace_id=proj.workspace_id,
        user_id=other.id,
        role="member",
    )
    db.add(membership)
    db.commit()
    other_client = DirectClient(db=db, current_user=other)
    resp = other_client.delete(f"/api/tasks/{task_id}/comments/{comment_id}")
    assert resp.status_code == 403


def test_delete_by_workspace_admin_returns_204(ctx):
    db = ctx["db"]
    task_id = ctx["task"]["id"]
    client = ctx["client"]
    create_resp = client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "admin target"}
    )
    comment_id = create_resp.json()["id"]
    # Admin user (not the author)
    admin = make_second_user(db)
    from app.models import Project
    proj_id = uuid.UUID(ctx["project"]["id"])
    proj = db.get(Project, proj_id)
    membership = WorkspaceMembership(
        workspace_id=proj.workspace_id,
        user_id=admin.id,
        role="admin",
    )
    db.add(membership)
    db.commit()
    admin_client = DirectClient(db=db, current_user=admin)
    resp = admin_client.delete(f"/api/tasks/{task_id}/comments/{comment_id}")
    assert resp.status_code == 204


def test_edited_comment_has_is_edited_true_in_list(ctx):
    client = ctx["client"]
    task_id = ctx["task"]["id"]
    create_resp = client.post(
        f"/api/tasks/{task_id}/comments", json={"body": "original"}
    )
    comment_id = create_resp.json()["id"]
    client.put(
        f"/api/tasks/{task_id}/comments/{comment_id}", json={"body": "edited"}
    )
    list_resp = client.get(f"/api/tasks/{task_id}/comments")
    comments = {c["id"]: c for c in list_resp.json()}
    assert comments[comment_id]["is_edited"] is True
