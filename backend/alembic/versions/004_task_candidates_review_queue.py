"""Add task_candidates table for review queue

Revision ID: 004
Revises: 003
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


candidatestatus_enum = postgresql.ENUM(
    "pending", "approved", "rejected", name="candidatestatus", create_type=False
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE candidatestatus AS ENUM ('pending', 'approved', 'rejected')"
    )

    op.create_table(
        "task_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "medium", "high", name="taskpriority", create_type=False
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "selected_assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("source_summary", sa.Text(), nullable=False),
        sa.Column(
            "assignee_recommendations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            candidatestatus_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "approved_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undo_expires_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_index(
        "ix_task_candidates_project_status_created",
        "task_candidates",
        ["project_id", "status", "created_at"],
    )
    op.create_index(
        "ix_task_candidates_status_undo_expires",
        "task_candidates",
        ["status", "undo_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_candidates_status_undo_expires", table_name="task_candidates"
    )
    op.drop_index(
        "ix_task_candidates_project_status_created", table_name="task_candidates"
    )
    op.drop_table("task_candidates")
    op.execute("DROP TYPE IF EXISTS candidatestatus")
