"""memory_audit_events

Revision ID: 014_memory_audit_events
Revises: 013_candidate_provenance_graph
Create Date: 2026-04-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "014_memory_audit_events"
down_revision = "013_candidate_provenance_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("query_hash", sa.String(length=128), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_memory_audit_events_org_created",
        "memory_audit_events",
        ["org_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_memory_audit_events_workspace_created",
        "memory_audit_events",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_memory_audit_events_project_created",
        "memory_audit_events",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_memory_audit_events_action_created",
        "memory_audit_events",
        ["action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_memory_audit_events_action_created",
        table_name="memory_audit_events",
    )
    op.drop_index(
        "ix_memory_audit_events_project_created",
        table_name="memory_audit_events",
    )
    op.drop_index(
        "ix_memory_audit_events_workspace_created",
        table_name="memory_audit_events",
    )
    op.drop_index(
        "ix_memory_audit_events_org_created",
        table_name="memory_audit_events",
    )
    op.drop_table("memory_audit_events")
