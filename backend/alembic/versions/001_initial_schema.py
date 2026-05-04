"""Initial schema: people and tasks tables

Revision ID: 001
Revises:
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# Pre-define ENUM types with create_type=False so op.create_table does NOT
# auto-create them (we manage creation explicitly via op.execute below).
taskstatus_enum = postgresql.ENUM(
    "todo", "in_progress", "done", name="taskstatus", create_type=False
)
taskpriority_enum = postgresql.ENUM(
    "low", "medium", "high", name="taskpriority", create_type=False
)


def upgrade() -> None:
    # Create PostgreSQL ENUM types with raw SQL to avoid SQLAlchemy ORM-level
    # type tracking that ignores create_type=False in some SQLAlchemy 2.x versions.
    op.execute("CREATE TYPE taskstatus AS ENUM ('todo', 'in_progress', 'done')")
    op.execute("CREATE TYPE taskpriority AS ENUM ('low', 'medium', 'high')")

    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            taskstatus_enum,
            nullable=False,
            server_default="todo",
        ),
        sa.Column(
            "priority",
            taskpriority_enum,
            nullable=False,
            server_default="medium",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="SET NULL"),
            nullable=True,
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

    # Indexes for the three columns used in Phase 3 filtering
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_priority", "tasks", ["priority"])
    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_assignee_id", table_name="tasks")
    op.drop_index("ix_tasks_priority", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("people")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS taskpriority")
