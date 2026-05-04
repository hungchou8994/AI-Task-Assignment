import pytest
from datetime import datetime, timedelta, date
from app.models import Task, TaskStatus, Project, Workspace, Organization, User
from tests.helpers import create_test_db

def test_get_project_forecast():
    db, current_user, cleanup = create_test_db()
    try:
        # 1. Setup Data
        org = Organization(name="Test Org", slug="test-org", settings={})
        db.add(org)
        db.commit()
        workspace = Workspace(name="Test Workspace", org_id=org.id, owner_id=current_user.id)
        db.add(workspace)
        db.commit()
        project = Project(name="Test Project", workspace_id=workspace.id)
        db.add(project)
        db.commit()

        # Add 8 completed tasks in the last 4 weeks
        for i in range(8):
            t = Task(
                title=f"Completed {i}",
                project_id=project.id,
                status=TaskStatus.done,
                updated_at=datetime.now() - timedelta(days=i)
            )
            db.add(t)
        
        # Add 4 remaining tasks
        for i in range(4):
            t = Task(
                title=f"Remaining {i}",
                project_id=project.id,
                status=TaskStatus.todo
            )
            db.add(t)
        
        db.commit()

        # 2. Test Request
        from fastapi.testclient import TestClient
        from app.main import app
        
        # Mock session for TestClient
        with patch("app.auth.get_current_user", return_value=current_user):
            # Wait, I don't need TestClient if I call the function directly or use a better way.
            # But let's use the router directly for a unit-ish test.
            from app.routers.projects import get_project_forecast
            
            resp = get_project_forecast(project_id=project.id, db=db, current_user=current_user)
            
            # 3. Assertions
            # Velocity: 8 completions / 4 weeks = 2.0 tasks/week
            assert resp.velocity_per_week == 2.0
            
            # Remaining: 4 tasks
            assert resp.remaining_tasks == 4
            
            # Estimated completion: 4 tasks / 2.0 velocity = 2 weeks from now
            expected_date = date.today() + timedelta(weeks=2)
            assert resp.estimated_completion_date == expected_date
            
            # Confidence: 8 completions >= 5 -> "medium"
            assert resp.confidence == "medium"

    finally:
        cleanup()

from unittest.mock import patch
