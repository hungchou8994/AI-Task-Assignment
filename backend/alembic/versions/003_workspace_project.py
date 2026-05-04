"""Add workspace and project tables, migrate existing tasks

Revision ID: 003
Revises: 002
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 2. Create projects table with index on workspace_id
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

    # 3. Add project_id column to tasks as NULLABLE initially
    op.add_column(
        "tasks",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 4. Create default workspace and project with generated UUIDs
    default_workspace_id = str(uuid.uuid4())
    default_project_id = str(uuid.uuid4())

    op.execute(
        f"""
        INSERT INTO workspaces (id, name, description)
        VALUES ('{default_workspace_id}', 'Default Workspace', 'Auto-created during migration')
        """
    )
    op.execute(
        f"""
        INSERT INTO projects (id, name, description, workspace_id)
        VALUES ('{default_project_id}', 'Default Project', 'Auto-created during migration', '{default_workspace_id}')
        """
    )

    # 5. Migrate existing tasks to default project
    op.execute(
        f"UPDATE tasks SET project_id = '{default_project_id}' WHERE project_id IS NULL"
    )

    # 6. Make project_id NOT NULL and add FK constraint + index
    op.alter_column("tasks", "project_id", nullable=False)
    op.create_foreign_key(
        "fk_tasks_project_id",
        "tasks",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_constraint("fk_tasks_project_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "project_id")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("workspaces")
