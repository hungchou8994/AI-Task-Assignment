"""task_comments: add TaskComment table with FK constraints and indexes

Revision ID: 015_task_comments
Revises: 014_memory_audit_events
Create Date: 2026-05-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "015_task_comments"
down_revision = "014_memory_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_task_comments_task_id_created_at",
        "task_comments",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_comments_author_id",
        "task_comments",
        ["author_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes BEFORE dropping the table (required pattern — see 014 template)
    op.drop_index("ix_task_comments_author_id", table_name="task_comments")
    op.drop_index("ix_task_comments_task_id_created_at", table_name="task_comments")
    op.drop_table("task_comments")
