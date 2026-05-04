"""Add task_activity_events table and backfill task_created events

Revision ID: 006
Revises: 005
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


taskactivityaction_enum = postgresql.ENUM(
    "task_created",
    "status_changed",
    "assignment_changed",
    "field_changed",
    name="taskactivityaction",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE taskactivityaction AS ENUM (
            'task_created',
            'status_changed',
            'assignment_changed',
            'field_changed'
        )
        """
    )

    op.create_table(
        "task_activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", taskactivityaction_enum, nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=True),
        sa.Column(
            "before_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "after_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_label", sa.String(length=255), nullable=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_task_activity_events_task_occurred_at",
        "task_activity_events",
        ["task_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_task_activity_events_project_occurred_at",
        "task_activity_events",
        ["project_id", sa.text("occurred_at DESC")],
    )

    op.execute(
        """
        INSERT INTO task_activity_events (
            id,
            task_id,
            project_id,
            action_type,
            field_name,
            before_value,
            after_value,
            event_metadata,
            actor_type,
            actor_label,
            actor_id,
            occurred_at,
            created_at
        )
        SELECT
            t.id,
            t.id,
            t.project_id,
            'task_created'::taskactivityaction,
            NULL,
            NULL,
            NULL,
            '{"backfilled": true}'::jsonb,
            'system',
            'migration_backfill',
            NULL,
            t.created_at,
            NOW()
        FROM tasks t
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_activity_events_project_occurred_at", table_name="task_activity_events"
    )
    op.drop_index(
        "ix_task_activity_events_task_occurred_at", table_name="task_activity_events"
    )
    op.drop_table("task_activity_events")
    op.execute("DROP TYPE IF EXISTS taskactivityaction")
