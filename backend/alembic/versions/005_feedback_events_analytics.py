"""Add feedback_events table for review analytics

Revision ID: 005
Revises: 004
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


feedbackaction_enum = postgresql.ENUM(
    "accept", "reject", "edit", name="feedbackaction", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE TYPE feedbackaction AS ENUM ('accept', 'reject', 'edit')")

    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", feedbackaction_enum, nullable=False),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "field_deltas", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "selected_assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("selected_assignee_rank", sa.String(length=32), nullable=True),
        sa.Column(
            "metadata",
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

    op.create_index(
        "ix_feedback_events_project_acted_at",
        "feedback_events",
        ["project_id", "acted_at"],
    )
    op.create_index(
        "ix_feedback_events_project_action_acted_at",
        "feedback_events",
        ["project_id", "action", "acted_at"],
    )
    op.create_index(
        "ix_feedback_events_candidate_acted_at",
        "feedback_events",
        ["candidate_id", "acted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_events_candidate_acted_at", table_name="feedback_events")
    op.drop_index(
        "ix_feedback_events_project_action_acted_at", table_name="feedback_events"
    )
    op.drop_index("ix_feedback_events_project_acted_at", table_name="feedback_events")
    op.drop_table("feedback_events")
    op.execute("DROP TYPE IF EXISTS feedbackaction")
