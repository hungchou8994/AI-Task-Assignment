from sqlalchemy.orm import Session

from app.auth import get_primary_org_id_for_user
from app.models import (
    OrgMembership,
    Organization,
    Project,
    User,
    Workspace,
    WorkspaceMembership,
)


def ensure_default_workspace_for_user(user: User, db: Session) -> Workspace:
    org_id = get_primary_org_id_for_user(user, db)
    if org_id is None:
        org = Organization(
            name="Default Org",
            slug=f"default-{str(user.id)[:8]}",
            settings={},
        )
        db.add(org)
        db.flush()
        db.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
        org_id = org.id

    workspace = Workspace(
        name="Default Workspace",
        description="Auto-created for this account",
        owner_id=user.id,
        org_id=org_id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
    )
    db.add(
        Project(
            name="Default Project",
            description="Auto-created for this workspace",
            workspace_id=workspace.id,
        )
    )
    db.commit()
    db.refresh(workspace)
    return workspace
