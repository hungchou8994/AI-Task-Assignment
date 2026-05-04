from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import (
    OrgMembership,
    Person,
    Project,
    Task,
    TaskCandidate,
    User,
    Workspace,
    WorkspaceMembership,
    Organization,
)

ORG_ROLE_PRIORITY = {"owner": 3, "admin": 2, "member": 1}
WORKSPACE_ROLE_PRIORITY = {"owner": 5, "admin": 4, "manager": 3, "member": 2, "viewer": 1}


def _check_role_sufficient(role: str, min_role: str, priority_map: dict[str, int]) -> None:
    if priority_map.get(role, 0) < priority_map.get(min_role, 0):
        raise HTTPException(status_code=403, detail=f"Forbidden: Requires {min_role} role")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    user = db.get(User, parsed_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


def ensure_org_access(org_id: UUID, user: User, db: Session, min_role: str = "member") -> Organization:
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    membership = db.scalar(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user.id,
        )
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Forbidden: Not an org member")

    _check_role_sufficient(membership.role, min_role, ORG_ROLE_PRIORITY)
    return org


def ensure_workspace_access(
    workspace_id: UUID, user: User, db: Session, min_role: str = "viewer"
) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Org owners/admins get full workspace access
    org_membership = db.scalar(
        select(OrgMembership).where(
            OrgMembership.org_id == workspace.org_id,
            OrgMembership.user_id == user.id,
        )
    )
    if org_membership and org_membership.role in ("owner", "admin"):
        return workspace

    # Workspace owner gets full access
    if workspace.owner_id == user.id:
        return workspace

    # Check workspace membership
    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Forbidden: Not a workspace member")

    _check_role_sufficient(membership.role, min_role, WORKSPACE_ROLE_PRIORITY)
    return workspace


def ensure_project_access(
    project_id: UUID, user: User, db: Session, min_role: str = "viewer"
) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_workspace_access(project.workspace_id, user, db, min_role=min_role)
    return project


def ensure_task_access(
    task_id: UUID, user: User, db: Session, min_role: str = "viewer"
) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    ensure_project_access(task.project_id, user, db, min_role=min_role)
    return task


def ensure_candidate_access(
    candidate_id: UUID, user: User, db: Session, min_role: str = "viewer"
) -> TaskCandidate:
    candidate = db.get(TaskCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Task candidate not found")

    ensure_project_access(candidate.project_id, user, db, min_role=min_role)
    return candidate


def ensure_person_access(person_id: UUID, user: User, db: Session) -> Person:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


def get_primary_org_id_for_user(user: User, db: Session) -> UUID | None:
    membership = db.scalar(
        select(OrgMembership)
        .where(OrgMembership.user_id == user.id)
        .order_by(OrgMembership.created_at.asc())
    )
    return membership.org_id if membership else None
