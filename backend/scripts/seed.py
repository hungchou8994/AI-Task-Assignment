"""Seed realistic English demo data.

Usage (from project root):
    docker compose exec api python scripts/seed.py

Demo login:
    demo@example.com / password123
"""

import sys
from datetime import date, datetime, timedelta, timezone

# Ensure the app package is importable when run inside the container.
sys.path.insert(0, "/app")

from app.auth_utils import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AvailabilityStatus,
    CandidateStatus,
    FeedbackEvent,
    OrgMembership,
    Organization,
    Person,
    Project,
    Task,
    TaskActivityAction,
    TaskActivityEvent,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
    User,
    Workspace,
    WorkspaceMembership,
)


def d(days_from_now: int) -> date:
    return (datetime.now(timezone.utc) + timedelta(days=days_from_now)).date()


def updated_at(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


WORKSPACE_SPEC = {
    "name": "Northstar Product Operations",
    "description": "Internal workspace for product delivery, AI intake, and launch operations.",
    "projects": [
        {
            "key": "platform",
            "name": "AI Task Management Platform",
            "description": "Core web application, API, task workflow, and AI extraction pipeline.",
        },
        {
            "key": "growth",
            "name": "Customer Launch Program",
            "description": "Pilot onboarding, customer feedback loops, and go-to-market readiness.",
        },
        {
            "key": "ops",
            "name": "Operational Excellence",
            "description": "Infrastructure, reliability, support processes, and compliance work.",
        },
    ],
}


PEOPLE = [
    dict(
        name="Maya Chen",
        email="maya.chen@northstar.example",
        role="Frontend Engineer",
        skills=["React", "TypeScript", "Design Systems", "Accessibility", "Playwright"],
        bio="Owns the React application shell, component quality, and accessibility standards for customer-facing workflows.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Ethan Brooks",
        email="ethan.brooks@northstar.example",
        role="Backend Engineer",
        skills=["Python", "FastAPI", "PostgreSQL", "SQLAlchemy", "API Design"],
        bio="Builds reliable APIs, schema migrations, and data integrity checks for the task management platform.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Priya Raman",
        email="priya.raman@northstar.example",
        role="Product Manager",
        skills=["Roadmapping", "Customer Discovery", "Jira", "SQL", "Prioritization"],
        bio="Coordinates product scope, customer feedback, and weekly release planning across engineering and operations.",
        availability=AvailabilityStatus.busy,
    ),
    dict(
        name="Noah Williams",
        email="noah.williams@northstar.example",
        role="DevOps Engineer",
        skills=["Docker", "AWS", "Terraform", "CI/CD", "Observability"],
        bio="Maintains deployment pipelines, staging infrastructure, alerts, and production readiness reviews.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Sofia Martinez",
        email="sofia.martinez@northstar.example",
        role="UX Designer",
        skills=["Figma", "Prototyping", "User Research", "Information Architecture", "UX Writing"],
        bio="Designs task review flows, empty states, and onboarding experiences based on customer research.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Liam Patel",
        email="liam.patel@northstar.example",
        role="Data Analyst",
        skills=["SQL", "Python", "Tableau", "dbt", "Product Analytics"],
        bio="Builds dashboards for activation, review throughput, AI quality, and operational SLA tracking.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Grace Kim",
        email="grace.kim@northstar.example",
        role="QA Engineer",
        skills=["Playwright", "Test Planning", "API Testing", "Regression Testing", "Bug Triage"],
        bio="Owns release test plans, regression coverage, and quality gates for the pilot launch.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Jordan Lee",
        email="jordan.lee@northstar.example",
        role="Customer Success Lead",
        skills=["Onboarding", "Training", "Customer Feedback", "Documentation", "Escalation Management"],
        bio="Runs customer onboarding, collects pilot feedback, and coordinates follow-up actions with product teams.",
        availability=AvailabilityStatus.busy,
    ),
    dict(
        name="Avery Stone",
        email="avery.stone@northstar.example",
        role="Security Engineer",
        skills=["Threat Modeling", "Audit Logging", "SOC 2", "Secrets Management", "Access Control"],
        bio="Reviews security controls, data retention policies, and customer-facing compliance commitments.",
        availability=AvailabilityStatus.available,
    ),
    dict(
        name="Olivia Reed",
        email="olivia.reed@northstar.example",
        role="Technical Writer",
        skills=["Developer Docs", "Release Notes", "API Documentation", "Information Design", "Editing"],
        bio="Creates migration guides, launch notes, and clear product documentation for internal and customer users.",
        availability=AvailabilityStatus.on_leave,
    ),
]


TASKS_SPEC = [
    dict(
        title="Add virtualized rendering to the task table",
        description="The task list becomes sluggish after roughly 600 rows. Replace full-table rendering with a virtualized list while preserving keyboard navigation and row actions.",
        status=TaskStatus.in_progress,
        priority=TaskPriority.high,
        due_date=d(7),
        project_key="platform",
        assignee_name="Maya Chen",
        needs_review=False,
    ),
    dict(
        title="Implement pagination for GET /api/tasks",
        description="Add limit and offset parameters, return total_count, and keep the default response efficient for dashboard usage.",
        status=TaskStatus.in_progress,
        priority=TaskPriority.high,
        due_date=d(5),
        project_key="platform",
        assignee_name="Ethan Brooks",
        needs_review=False,
    ),
    dict(
        title="Provision a production-like staging environment",
        description="Create an ECS and RDS staging stack with GitHub Actions deployment so every main branch merge can be validated before production release.",
        status=TaskStatus.in_progress,
        priority=TaskPriority.medium,
        due_date=d(14),
        project_key="ops",
        assignee_name="Noah Williams",
        needs_review=False,
    ),
    dict(
        title="Redesign empty states across core pages",
        description="Dashboard, Tasks, Team, and Review Queue need useful empty states with clear calls to action instead of blank panels.",
        status=TaskStatus.in_progress,
        priority=TaskPriority.medium,
        due_date=d(10),
        project_key="platform",
        assignee_name="Sofia Martinez",
        needs_review=False,
    ),
    dict(
        title="Create end-to-end tests for AI task extraction",
        description="Cover the text intake happy path, empty input validation, timeout handling, and the zero-task extraction state with Playwright.",
        status=TaskStatus.in_progress,
        priority=TaskPriority.medium,
        due_date=d(12),
        project_key="platform",
        assignee_name="Grace Kim",
        needs_review=False,
    ),
    dict(
        title="Add assignment email notifications",
        description="Send transactional email when a task assignee changes. Include task title, due date, project name, and a deep link to the task.",
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        due_date=d(18),
        project_key="ops",
        assignee_name="Ethan Brooks",
        needs_review=False,
    ),
    dict(
        title="Document the AI extraction architecture",
        description="Write a concise architecture note covering pre-processing, model invocation, schema validation, persistence, review queue state, and retry behavior.",
        status=TaskStatus.todo,
        priority=TaskPriority.low,
        due_date=None,
        project_key="platform",
        assignee_name="Olivia Reed",
        needs_review=False,
    ),
    dict(
        title="Build pilot activation dashboard",
        description="Track invited users, first task created, first candidate reviewed, seven-day retention, and time-to-value for pilot accounts.",
        status=TaskStatus.todo,
        priority=TaskPriority.medium,
        due_date=d(30),
        project_key="growth",
        assignee_name="Liam Patel",
        needs_review=False,
    ),
    dict(
        title="Run WCAG 2.1 AA accessibility audit",
        description="Run axe-core and manual keyboard checks across the primary workflows. Prioritize contrast, focus order, and icon-only button labels.",
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        due_date=d(9),
        project_key="platform",
        assignee_name="Maya Chen",
        needs_review=False,
    ),
    dict(
        title="Review customer data retention commitments",
        description="Confirm whether source excerpts, candidate revisions, and audit events meet the pilot contract retention language before the launch review.",
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        due_date=d(3),
        project_key="ops",
        assignee_name="Avery Stone",
        needs_review=True,
    ),
    dict(
        title="Investigate P99 latency regression on task search",
        description="Datadog shows GET /api/tasks/search P99 increased from 180ms to 940ms after the latest release. Check query plans and recent joins.",
        status=TaskStatus.todo,
        priority=TaskPriority.high,
        due_date=d(2),
        project_key="platform",
        assignee_name=None,
        needs_review=True,
    ),
    dict(
        title="Refresh onboarding checklist for new pilot admins",
        description="Update the checklist to include workspace setup, project creation, team import, AI intake examples, and support escalation paths.",
        status=TaskStatus.todo,
        priority=TaskPriority.medium,
        due_date=d(8),
        project_key="growth",
        assignee_name="Jordan Lee",
        needs_review=True,
    ),
    dict(
        title="Fix filter reset behavior on the Tasks page",
        description="Clearing search now also resets status and assignee filters. Verified with regression coverage.",
        status=TaskStatus.done,
        priority=TaskPriority.medium,
        due_date=None,
        project_key="platform",
        assignee_name="Maya Chen",
        needs_review=False,
        _updated_days_ago=1,
    ),
    dict(
        title="Add needs-review metric to dashboard summary cards",
        description="Dashboard now surfaces pending review queue volume next to active tasks and overdue tasks.",
        status=TaskStatus.done,
        priority=TaskPriority.low,
        due_date=None,
        project_key="platform",
        assignee_name="Ethan Brooks",
        needs_review=False,
        _updated_days_ago=2,
    ),
    dict(
        title="Upgrade FastAPI and Pydantic dependencies",
        description="Completed routine backend dependency update and validated all API tests before merging.",
        status=TaskStatus.done,
        priority=TaskPriority.medium,
        due_date=None,
        project_key="ops",
        assignee_name="Ethan Brooks",
        needs_review=False,
        _updated_days_ago=3,
    ),
    dict(
        title="Publish pilot launch notes draft",
        description="Draft release notes explain the review queue, source provenance, assignee recommendations, and known limitations for pilot users.",
        status=TaskStatus.done,
        priority=TaskPriority.medium,
        due_date=None,
        project_key="growth",
        assignee_name="Olivia Reed",
        needs_review=False,
        _updated_days_ago=4,
    ),
    dict(
        title="Complete usability testing for the review queue",
        description="Five moderated sessions identified confusion around batch approve, undo reject, and recommendation confidence labels.",
        status=TaskStatus.done,
        priority=TaskPriority.medium,
        due_date=None,
        project_key="growth",
        assignee_name="Sofia Martinez",
        needs_review=False,
        _updated_days_ago=5,
    ),
    dict(
        title="Add Playwright smoke tests to CI",
        description="CI now runs smoke tests for login, dashboard load, task creation, and AI analysis navigation.",
        status=TaskStatus.done,
        priority=TaskPriority.medium,
        due_date=None,
        project_key="ops",
        assignee_name="Grace Kim",
        needs_review=False,
        _updated_days_ago=6,
    ),
]


CANDIDATES_SPEC = [
    dict(
        title="Prepare workspace migration notes for support",
        description="Document how legacy single-project accounts map into the new workspace and project hierarchy, including customer-facing FAQ answers.",
        priority=TaskPriority.medium,
        due_date=d(6),
        project_key="platform",
        selected_assignee_name="Olivia Reed",
        confidence_score=0.91,
        source_type="email",
        source_excerpt="Support asked for a migration note by Friday so they can answer pilot customer questions about workspaces and projects.",
        source_summary="Request to create support-ready migration documentation for workspace and project hierarchy changes.",
        recommendation_names=["Olivia Reed", "Ethan Brooks", "Priya Raman"],
    ),
    dict(
        title="Finalize launch checklist for Review Queue UX",
        description="Review empty states, batch approve and reject actions, undo timing, keyboard shortcuts, and copy quality before pilot launch.",
        priority=TaskPriority.high,
        due_date=d(4),
        project_key="platform",
        selected_assignee_name="Grace Kim",
        confidence_score=0.87,
        source_type="text",
        source_excerpt="We need one final pass on review queue interactions, especially batch actions and the undo window, before launch sign-off.",
        source_summary="Final QA pass for review queue launch readiness.",
        recommendation_names=["Grace Kim", "Sofia Martinez", "Maya Chen"],
    ),
    dict(
        title="Coordinate pilot onboarding office hours",
        description="Schedule two office-hour sessions, prepare the invite copy, and define the escalation path for customer admins joining the pilot next week.",
        priority=TaskPriority.medium,
        due_date=d(8),
        project_key="growth",
        selected_assignee_name="Jordan Lee",
        confidence_score=0.83,
        source_type="url",
        source_excerpt="https://intranet.northstar.example/launch/pilot-onboarding-plan",
        source_summary="Pilot onboarding plan requires office hours and escalation process coordination.",
        recommendation_names=["Jordan Lee", "Priya Raman", "Olivia Reed"],
    ),
    dict(
        title="Validate audit log export requirements",
        description="Confirm whether enterprise pilot customers need CSV export for audit events in addition to API access and retention guarantees.",
        priority=TaskPriority.high,
        due_date=d(5),
        project_key="ops",
        selected_assignee_name="Avery Stone",
        confidence_score=0.89,
        source_type="email",
        source_excerpt="Legal wants confirmation on audit event exports before we send the enterprise pilot addendum tomorrow afternoon.",
        source_summary="Security and compliance follow-up for enterprise audit log export requirements.",
        recommendation_names=["Avery Stone", "Noah Williams", "Ethan Brooks"],
    ),
]


def _clear_existing(db) -> None:
    print("Deleting existing data...")
    for model, label in [
        (TaskActivityEvent, "task activity events"),
        (FeedbackEvent, "feedback events"),
        (TaskCandidate, "task candidates"),
        (Task, "tasks"),
        (Project, "projects"),
        (WorkspaceMembership, "workspace memberships"),
        (Workspace, "workspaces"),
        (OrgMembership, "organization memberships"),
        (User, "users"),
        (Organization, "organizations"),
        (Person, "people"),
    ]:
        count = db.query(model).delete()
        print(f"  Deleted {count} {label}.")
    db.commit()


def _seed_user_and_org(db) -> tuple[User, Organization]:
    print("\nInserting demo user and organization...")
    user = User(email="demo@example.com", hashed_password=hash_password("password123"))
    db.add(user)
    db.flush()

    org = Organization(
        name="Northstar Analytics",
        slug="northstar-analytics",
        settings={"industry": "B2B SaaS", "region": "North America"},
    )
    db.add(org)
    db.flush()
    db.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
    return user, org


def _seed_workspace_and_projects(db, user: User, org: Organization) -> tuple[Workspace, dict[str, Project]]:
    print("\nInserting workspace and projects...")
    workspace = Workspace(
        name=WORKSPACE_SPEC["name"],
        description=WORKSPACE_SPEC["description"],
        org_id=org.id,
        owner_id=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="owner"))

    key_to_project: dict[str, Project] = {}
    for spec in WORKSPACE_SPEC["projects"]:
        project = Project(
            name=spec["name"],
            description=spec["description"],
            workspace_id=workspace.id,
        )
        db.add(project)
        db.flush()
        key_to_project[spec["key"]] = project
        print(f"  + {project.name}")

    return workspace, key_to_project


def _seed_people(db) -> dict[str, Person]:
    print("\nInserting people...")
    name_to_person: dict[str, Person] = {}
    for spec in PEOPLE:
        person = Person(**spec)
        db.add(person)
        db.flush()
        name_to_person[spec["name"]] = person
        print(f"  + {person.name} ({person.role})")
    return name_to_person


def _seed_tasks(db, key_to_project: dict[str, Project], name_to_person: dict[str, Person]) -> None:
    print("\nInserting tasks...")
    for spec in TASKS_SPEC:
        assignee_name = spec.get("assignee_name")
        task = Task(
            title=spec["title"],
            description=spec["description"],
            status=spec["status"],
            priority=spec["priority"],
            due_date=spec["due_date"],
            needs_review=spec["needs_review"],
            assignee_id=name_to_person[assignee_name].id if assignee_name else None,
            project_id=key_to_project[spec["project_key"]].id,
        )
        db.add(task)
        db.flush()

        db.add(
            TaskActivityEvent(
                task_id=task.id,
                project_id=task.project_id,
                action_type=TaskActivityAction.task_created,
                event_metadata={"seeded": True, "source": "demo_seed"},
                actor_type="system",
                actor_label="seed_script",
                occurred_at=task.created_at,
            )
        )

        days_ago = spec.get("_updated_days_ago")
        if days_ago is not None:
            task.updated_at = updated_at(days_ago)

        print(f"  + [{spec['status'].value:11s}] {task.title[:70]}")


def _seed_candidates(db, key_to_project: dict[str, Project], name_to_person: dict[str, Person]) -> None:
    print("\nInserting review-queue task candidates...")
    for spec in CANDIDATES_SPEC:
        recommendations = [
            {
                "rank": idx,
                "person_id": str(name_to_person[name].id),
                "name": name_to_person[name].name,
                "confidence_score": round(spec["confidence_score"] - (idx - 1) * 0.1, 2),
                "reasoning": f"Relevant ownership area for {name_to_person[name].role}.",
            }
            for idx, name in enumerate(spec["recommendation_names"], start=1)
        ]

        selected_name = spec.get("selected_assignee_name")
        candidate = TaskCandidate(
            project_id=key_to_project[spec["project_key"]].id,
            title=spec["title"],
            description=spec["description"],
            priority=spec["priority"],
            due_date=spec["due_date"],
            selected_assignee_id=name_to_person[selected_name].id if selected_name else None,
            confidence_score=spec["confidence_score"],
            source_type=spec["source_type"],
            source_excerpt=spec["source_excerpt"],
            source_summary=spec["source_summary"],
            assignee_recommendations=recommendations,
            status=CandidateStatus.pending,
        )
        db.add(candidate)
        print(f"  + [pending    ] {candidate.title[:70]}")


def seed() -> None:
    db = SessionLocal()
    try:
        _clear_existing(db)
        user, org = _seed_user_and_org(db)
        _workspace, key_to_project = _seed_workspace_and_projects(db, user, org)
        name_to_person = _seed_people(db)
        _seed_tasks(db, key_to_project, name_to_person)
        _seed_candidates(db, key_to_project, name_to_person)

        db.commit()
        print(
            "\nDone. "
            f"1 workspace, {len(WORKSPACE_SPEC['projects'])} projects, "
            f"{len(PEOPLE)} people, {len(TASKS_SPEC)} tasks, "
            f"{len(CANDIDATES_SPEC)} task candidates inserted."
        )
        print("Login with demo@example.com / password123")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
