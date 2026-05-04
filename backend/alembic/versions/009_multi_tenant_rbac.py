"""Multi-tenant RBAC (orgs, memberships, service identities)

Revision ID: 009
Revises: 008
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # 2) org_memberships
    op.create_table(
        "org_memberships",
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_org_memberships_user_id", "org_memberships", ["user_id"])
    op.create_index("ix_org_memberships_org_id", "org_memberships", ["org_id"])

    # 3) Add org_id to workspaces; backfill to a default org
    op.add_column(
        "workspaces",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    default_org_id = str(uuid.uuid4())
    op.execute(
        f"""
        INSERT INTO organizations (id, name, slug, settings)
        VALUES ('{default_org_id}', 'Default Org', 'default', '{{}}'::jsonb)
        """
    )

    op.execute(
        f"UPDATE workspaces SET org_id = '{default_org_id}' WHERE org_id IS NULL"
    )

    # Create org membership for all existing users (safe default: owner)
    op.execute(
        f"""
        INSERT INTO org_memberships (org_id, user_id, role)
        SELECT '{default_org_id}', u.id, 'owner'
        FROM users u
        ON CONFLICT DO NOTHING
        """
    )

    op.alter_column("workspaces", "org_id", nullable=False)
    op.create_foreign_key(
        "fk_workspaces_org_id",
        "workspaces",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_workspaces_org_id", "workspaces", ["org_id"])

    # 4) workspace_memberships (role per workspace)
    op.create_table(
        "workspace_memberships",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"]
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
    )

    # Backfill: workspace owners become workspace owners in membership table
    op.execute(
        """
        INSERT INTO workspace_memberships (workspace_id, user_id, role)
        SELECT w.id, w.owner_id, 'owner'
        FROM workspaces w
        ON CONFLICT DO NOTHING
        """
    )

    # 5) feature_entitlements
    op.create_table(
        "feature_entitlements",
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("feature_key", sa.String(128), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_feature_entitlements_org_id", "feature_entitlements", ["org_id"]
    )

    # 6) service_identities
    op.create_table(
        "service_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "kind",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'automation_actor'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_service_identities_org_id", "service_identities", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_service_identities_org_id", table_name="service_identities")
    op.drop_table("service_identities")

    op.drop_index("ix_feature_entitlements_org_id", table_name="feature_entitlements")
    op.drop_table("feature_entitlements")

    op.drop_index(
        "ix_workspace_memberships_workspace_id", table_name="workspace_memberships"
    )
    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")

    op.drop_index("ix_workspaces_org_id", table_name="workspaces")
    op.drop_constraint("fk_workspaces_org_id", "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "org_id")

    op.drop_index("ix_org_memberships_org_id", table_name="org_memberships")
    op.drop_index("ix_org_memberships_user_id", table_name="org_memberships")
    op.drop_table("org_memberships")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

