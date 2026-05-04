"""task_sources_n2n

Revision ID: 5eb4f83b2760
Revises: 011
Create Date: 2026-04-09 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "012_task_sources_n2n"
down_revision = "011_add_webhook_tables"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("uri", sa.String(length=2048), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sources_workspace_id", "sources", ["workspace_id"], unique=False
    )
    op.create_index("ix_sources_project_id", "sources", ["project_id"], unique=False)
    op.create_index(
        "ix_sources_content_hash", "sources", ["content_hash"], unique=False
    )

    # 2. Create task_sources table
    op.create_table(
        "task_sources",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "link_type",
            sa.String(length=32),
            server_default="derived_from",
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "source_id", "link_type"),
    )
    op.create_index(
        "ix_task_sources_task_id", "task_sources", ["task_id"], unique=False
    )
    op.create_index(
        "ix_task_sources_source_id", "task_sources", ["source_id"], unique=False
    )

    # 3. Backfill data from task_candidates (set-based to avoid bind errors)
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            INSERT INTO sources (
                id,
                workspace_id,
                project_id,
                source_type,
                summary,
                excerpt,
                payload,
                created_at
            )
            SELECT DISTINCT ON (
                p.workspace_id,
                tc.project_id,
                tc.source_type,
                COALESCE(tc.source_summary, ''),
                COALESCE(tc.source_excerpt, '')
            )
                gen_random_uuid(),
                p.workspace_id,
                tc.project_id,
                tc.source_type,
                tc.source_summary,
                tc.source_excerpt,
                '{}'::jsonb,
                NOW()
            FROM task_candidates tc
            JOIN projects p ON p.id = tc.project_id
            WHERE tc.source_type IS NOT NULL
            ORDER BY
                p.workspace_id,
                tc.project_id,
                tc.source_type,
                COALESCE(tc.source_summary, ''),
                COALESCE(tc.source_excerpt, ''),
                tc.created_at DESC
            """
        )
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO task_sources (
                task_id,
                source_id,
                link_type,
                created_at
            )
            SELECT
                tc.approved_task_id,
                s.id,
                'derived_from',
                NOW()
            FROM task_candidates tc
            JOIN projects p ON p.id = tc.project_id
            JOIN sources s
              ON s.workspace_id = p.workspace_id
             AND s.project_id = tc.project_id
             AND s.source_type = tc.source_type
             AND COALESCE(s.summary, '') = COALESCE(tc.source_summary, '')
             AND COALESCE(s.excerpt, '') = COALESCE(tc.source_excerpt, '')
            WHERE tc.approved_task_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade():
    op.drop_index("ix_task_sources_source_id", table_name="task_sources")
    op.drop_index("ix_task_sources_task_id", table_name="task_sources")
    op.drop_table("task_sources")
    op.drop_index("ix_sources_content_hash", table_name="sources")
    op.drop_index("ix_sources_project_id", table_name="sources")
    op.drop_index("ix_sources_workspace_id", table_name="sources")
    op.drop_table("sources")
