from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import ensure_workspace_access, get_current_user, get_primary_org_id_for_user
from app.dependencies import get_db
from app.models import (
    Label,
    Organization,
    OrgMembership,
    Workspace,
    WorkspaceMembership,
    Project,
    User,
)
from app.services.workspace_bootstrap import ensure_default_workspace_for_user
from app.schemas import (
    WorkspaceCreate,
    WorkspaceResponse,
    ProjectCreate,
    ProjectResponse,
    LabelCreate,
    LabelResponse,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
DbDep = Annotated[Session, Depends(get_db)]


@router.post("", response_model=WorkspaceResponse, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    org_id = get_primary_org_id_for_user(current_user, db)
    if org_id is None:
        org = Organization(
            name="Default Org",
            slug=f"default-{str(current_user.id)[:8]}",
            settings={},
        )
        db.add(org)
        db.flush()
        db.add(OrgMembership(org_id=org.id, user_id=current_user.id, role="owner"))
        org_id = org.id

    workspace = Workspace(**payload.model_dump(exclude={"org_id"}), owner_id=current_user.id, org_id=org_id)
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=current_user.id, role="owner"
        )
    )
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    stmt = (
        select(Workspace)
        .distinct()
        .outerjoin(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .outerjoin(
            OrgMembership,
            OrgMembership.org_id == Workspace.org_id,
        )
        .where(
            (Workspace.owner_id == current_user.id)
            | (WorkspaceMembership.user_id == current_user.id)
            | (
                (OrgMembership.user_id == current_user.id)
                & (OrgMembership.role.in_(["owner", "admin"]))
            )
        )
    )
    workspaces = db.scalars(stmt).all()
    if workspaces:
        return workspaces

    return [ensure_default_workspace_for_user(current_user, db)]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ensure_workspace_access(workspace_id, current_user, db, min_role="viewer")


@router.get("/{workspace_id}/projects", response_model=list[ProjectResponse])
def list_projects(
    workspace_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_workspace_access(workspace_id, current_user, db, min_role="viewer")
    return db.scalars(select(Project).where(Project.workspace_id == workspace_id)).all()


@router.post(
    "/{workspace_id}/projects", response_model=ProjectResponse, status_code=201
)
def create_project(
    workspace_id: UUID,
    payload: ProjectCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_workspace_access(workspace_id, current_user, db, min_role="member")
    project = Project(
        name=payload.name, description=payload.description, workspace_id=workspace_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{workspace_id}/labels", response_model=list[LabelResponse])
def list_labels(
    workspace_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_workspace_access(workspace_id, current_user, db, min_role="viewer")
    return db.scalars(select(Label).where(Label.workspace_id == workspace_id)).all()


@router.post(
    "/{workspace_id}/labels", response_model=LabelResponse, status_code=201
)
def create_label(
    workspace_id: UUID,
    payload: LabelCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_workspace_access(workspace_id, current_user, db, min_role="member")
    label = Label(
        workspace_id=workspace_id,
        name=payload.name,
        color=payload.color,
    )
    db.add(label)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A label with this name already exists"
        ) from None
    db.refresh(label)
    return label
