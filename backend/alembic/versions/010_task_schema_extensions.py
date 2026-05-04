"""Task schema extensions: status history, estimates, labels, dependencies, archive

Revision ID: 010
Revises: 009
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_archived_at", "tasks", ["archived_at"])

    # Create the enum type once (if missing). The same ENUM instance is later
    # reused in a table definition; `create_type=False` prevents SQLAlchemy from
    # trying to create it again during `CREATE TABLE`.
    taskdependencytype = postgresql.ENUM(
        "blocks",
        "relates_to",
        name="taskdependencytype",
        create_type=False,
    )
    postgresql.ENUM(
        "blocks",
        "relates_to",
        name="taskdependencytype",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "task_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("changed_by_actor_type", sa.String(32), nullable=False),
        sa.Column("changed_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_task_status_history_task_changed_at",
        "task_status_history",
        ["task_id", sa.text("changed_at DESC")],
    )

    op.create_table(
        "task_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("estimated_hours", sa.Float(), nullable=True),
        sa.Column("actual_hours", sa.Float(), nullable=True),
        sa.Column(
            "estimated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_task_estimates_task_recorded_at",
        "task_estimates",
        ["task_id", sa.text("recorded_at DESC")],
    )

    op.create_table(
        "labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("color", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_labels_workspace_id_name",
        "labels",
        ["workspace_id", "name"],
        unique=True,
    )

    op.create_table(
        "task_labels",
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "label_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("labels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dependent_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "blocks_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dependency_type", taskdependencytype, nullable=False),
    )
    op.create_index(
        "ix_task_dependencies_dependent",
        "task_dependencies",
        ["dependent_task_id"],
    )
    op.create_index(
        "ix_task_dependencies_blocks",
        "task_dependencies",
        ["blocks_task_id"],
    )
    op.create_index(
        "uq_task_dependencies_edge",
        "task_dependencies",
        ["dependent_task_id", "blocks_task_id", "dependency_type"],
        unique=True,
    )

    op.execute(
        """
        INSERT INTO task_status_history (
            id,
            task_id,
            from_status,
            to_status,
            changed_at,
            changed_by_actor_type,
            changed_by_actor_id
        )
        SELECT
            gen_random_uuid(),
            e.task_id,
            CASE
                WHEN e.before_value IS NULL THEN NULL
                WHEN jsonb_typeof(e.before_value) = 'string'
                    THEN e.before_value #>> '{}'
                ELSE e.before_value::text
            END,
            CASE
                WHEN e.after_value IS NULL THEN NULL
                WHEN jsonb_typeof(e.after_value) = 'string'
                    THEN e.after_value #>> '{}'
                ELSE e.after_value::text
            END,
            e.occurred_at,
            e.actor_type,
            e.actor_id
        FROM task_activity_events e
        WHERE e.action_type::text = 'status_changed'
          AND e.field_name = 'status'
          AND e.after_value IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_task_dependencies_edge", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_blocks", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_dependent", table_name="task_dependencies")
    op.drop_table("task_dependencies")

    op.drop_table("task_labels")

    op.drop_index("ix_labels_workspace_id_name", table_name="labels")
    op.drop_table("labels")

    op.drop_index("ix_task_estimates_task_recorded_at", table_name="task_estimates")
    op.drop_table("task_estimates")

    op.drop_index(
        "ix_task_status_history_task_changed_at", table_name="task_status_history"
    )
    op.drop_table("task_status_history")

    op.execute("DROP TYPE IF EXISTS taskdependencytype")

    op.drop_index("ix_tasks_archived_at", table_name="tasks")
    op.drop_column("tasks", "archived_at")
