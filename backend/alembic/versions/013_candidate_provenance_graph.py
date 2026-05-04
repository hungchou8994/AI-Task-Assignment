"""candidate_provenance_graph

Revision ID: 013_candidate_provenance_graph
Revises: 012_task_sources_n2n
Create Date: 2026-04-10 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "013_candidate_provenance_graph"
down_revision = "012_task_sources_n2n"
branch_labels = None
depends_on = None


candidateapprovalaction_enum = postgresql.ENUM(
    "approve",
    "reject",
    "undo_reject",
    name="candidateapprovalaction",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE candidateapprovalaction AS ENUM ('approve', 'reject', 'undo_reject')"
    )

    op.create_table(
        "task_candidate_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "medium", "high", name="taskpriority", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "selected_assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("source_summary", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("prompt_template_hash", sa.String(length=64), nullable=True),
        sa.Column("model_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_task_candidate_revisions_candidate_created",
        "task_candidate_revisions",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_task_candidate_revisions_candidate_number",
        "task_candidate_revisions",
        ["candidate_id", "revision_number"],
        unique=True,
    )

    op.create_table(
        "candidate_source_spans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_revision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_candidate_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_candidate_source_spans_revision_id",
        "candidate_source_spans",
        ["candidate_revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_source_spans_source_id",
        "candidate_source_spans",
        ["source_id"],
        unique=False,
    )

    op.create_table(
        "candidate_approval_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", candidateapprovalaction_enum, nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_candidate_approval_events_candidate_created",
        "candidate_approval_events",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_approval_events_task_id",
        "candidate_approval_events",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_approval_events_task_id", table_name="candidate_approval_events"
    )
    op.drop_index(
        "ix_candidate_approval_events_candidate_created",
        table_name="candidate_approval_events",
    )
    op.drop_table("candidate_approval_events")

    op.drop_index(
        "ix_candidate_source_spans_source_id", table_name="candidate_source_spans"
    )
    op.drop_index(
        "ix_candidate_source_spans_revision_id", table_name="candidate_source_spans"
    )
    op.drop_table("candidate_source_spans")

    op.drop_index(
        "uq_task_candidate_revisions_candidate_number",
        table_name="task_candidate_revisions",
    )
    op.drop_index(
        "ix_task_candidate_revisions_candidate_created",
        table_name="task_candidate_revisions",
    )
    op.drop_table("task_candidate_revisions")

    op.execute("DROP TYPE IF EXISTS candidateapprovalaction")
