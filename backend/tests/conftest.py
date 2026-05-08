import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import uuid

import pytest
from fastapi import HTTPException, BackgroundTasks
from pydantic import ValidationError

import asyncio
from app.routers import people, projects, tasks, workspaces, ai, task_candidates

from tests.helpers import (
    BaseDirectClient,
    DirectResponse,
    create_test_db,
    patch_sqlite_columns,
)


class DirectClient(BaseDirectClient):
    def _validation_error(self, exc: ValidationError):
        return DirectResponse(422, {"detail": exc.errors()})

    def get(self, url: str, **kwargs):
        path, query = self._parse(url)
        try:
            if path == "/api/workspaces":
                return self._ok(
                    workspaces.list_workspaces(
                        db=self.db, current_user=self.current_user
                    )
                )
            if path.startswith("/api/workspaces/") and path.count("/") == 3:
                workspace_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    workspaces.get_workspace(
                        workspace_id=workspace_id,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            if path.startswith("/api/workspaces/") and path.endswith("/projects"):
                workspace_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    workspaces.list_projects(
                        workspace_id=workspace_id,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            if path.startswith("/api/workspaces/") and path.endswith("/members"):
                workspace_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    workspaces.list_workspace_members(
                        workspace_id=workspace_id,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            if path == "/api/people":
                return self._ok(
                    people.list_people(db=self.db, current_user=self.current_user)
                )
            if path == "/api/tasks":
                project_id = query.get("project_id", [None])[0]
                project_uuid = uuid.UUID(project_id) if project_id else None
                inc = (query.get("include_archived", ["false"])[0] or "").lower()
                include_archived = inc in ("1", "true", "yes")
                return self._ok(
                    tasks.list_tasks(
                        db=self.db,
                        project_id=project_uuid,
                        include_archived=include_archived,
                        current_user=self.current_user,
                    )
                )
            if path.startswith("/api/tasks/") and path.endswith("/sources"):
                task_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    tasks.get_task_sources(
                        task_id=task_id,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            if path.startswith("/api/projects/") and path.endswith("/sources"):
                project_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    projects.list_project_sources(
                        project_id=project_id,
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            if path.startswith("/api/ai/jobs/"):
                job_id = uuid.UUID(path.split("/")[4])
                return self._ok(
                    ai.get_extraction_job_status(
                        job_id=job_id,
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
            if path == "/api/ai/extract-tasks":
                payload = ai.ExtractTasksRequest(**(json or {}))
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
                return self._ok(
                    workspaces.create_workspace(
                        payload=workspaces.WorkspaceCreate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                    ),
                    201,
                )
            if path.startswith("/api/workspaces/") and path.endswith("/projects"):
                workspace_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    workspaces.create_project(
                        workspace_id=workspace_id,
                        payload=workspaces.ProjectCreate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                    ),
                    201,
                )
            if path.startswith("/api/workspaces/") and path.endswith("/members"):
                workspace_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    workspaces.add_workspace_member(
                        workspace_id=workspace_id,
                        payload=workspaces.WorkspaceMemberCreate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                    ),
                    201,
                )
            if path == "/api/people":
                return self._ok(
                    people.create_person(
                        payload=people.PersonCreate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                    ),
                    201,
                )
            if path == "/api/tasks":
                return self._ok(
                    tasks.create_task(
                        payload=tasks.TaskCreate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                        background_tasks=BackgroundTasks(),
                    ),
                    201,
                )
            if path.startswith("/api/task-candidates/") and path.endswith("/approve"):
                candidate_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    task_candidates.approve_candidate(
                        candidate_id=candidate_id,
                        db=self.db,
                        current_user=self.current_user,
                        background_tasks=BackgroundTasks(),
                    )
                )
            raise AssertionError(f"Unhandled POST path: {path}")
        except HTTPException as exc:
            return self._error(exc)
        except ValidationError as exc:
            return self._validation_error(exc)

    def put(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        try:
            if path.startswith("/api/tasks/"):
                task_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    tasks.update_task(
                        task_id=task_id,
                        payload=tasks.TaskUpdate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                        background_tasks=BackgroundTasks(),
                    )
                )
            if path.startswith("/api/people/"):
                person_id = uuid.UUID(path.split("/")[3])
                return self._ok(
                    people.update_person(
                        person_id=person_id,
                        data=people.PersonUpdate(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                    )
                )
            raise AssertionError(f"Unhandled PUT path: {path}")
        except HTTPException as exc:
            return self._error(exc)
        except ValidationError as exc:
            return self._validation_error(exc)

    def patch(self, url: str, json=None, **kwargs):
        path, _ = self._parse(url)
        try:
            if path.startswith("/api/tasks/"):
                parts = path.split("/")
                if len(parts) != 4:
                    raise AssertionError(f"Unhandled PATCH path: {path}")
                task_id = uuid.UUID(parts[3])
                return self._ok(
                    tasks.patch_task(
                        task_id=task_id,
                        payload=tasks.TaskPatch(**(json or {})),
                        db=self.db,
                        current_user=self.current_user,
                        background_tasks=BackgroundTasks(),
                    )
                )
            raise AssertionError(f"Unhandled PATCH path: {path}")
        except HTTPException as exc:
            return self._error(exc)
        except ValidationError as exc:
            return self._validation_error(exc)

    def delete(self, url: str, **kwargs):
        path, _ = self._parse(url)
        try:
            if path.startswith("/api/tasks/"):
                task_id = uuid.UUID(path.split("/")[3])
                tasks.delete_task(
                    task_id=task_id,
                    db=self.db,
                    current_user=self.current_user,
                )
                return DirectResponse(204, None)
            if path.startswith("/api/people/"):
                person_id = uuid.UUID(path.split("/")[3])
                people.delete_person(
                    person_id=person_id,
                    db=self.db,
                    current_user=self.current_user,
                )
                return DirectResponse(204, None)
            raise AssertionError(f"Unhandled DELETE path: {path}")
        except HTTPException as exc:
            return self._error(exc)


@pytest.fixture
def client():
    db, current_user, cleanup = create_test_db()
    try:
        yield DirectClient(db=db, current_user=current_user)
    finally:
        cleanup()
