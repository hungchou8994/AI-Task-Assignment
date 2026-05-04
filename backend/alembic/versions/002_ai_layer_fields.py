"""AI layer fields: person profile + needs_review flag

Revision ID: 002
Revises: 001
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

# Pre-define ENUM type with create_type=False so add_column does NOT
# auto-create it (we manage creation explicitly via op.execute below).
availabilitystatus_enum = postgresql.ENUM(
    "available", "busy", "on_leave", name="availabilitystatus", create_type=False
)


def upgrade() -> None:
    # Create the new ENUM type via raw SQL (same pattern as migration 001)
    op.execute(
        "CREATE TYPE availabilitystatus AS ENUM ('available', 'busy', 'on_leave')"
    )

    # Add new columns to the people table
    op.add_column("people", sa.Column("role", sa.String(255), nullable=True))
    op.add_column(
        "people",
        sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column("people", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column(
        "people",
        sa.Column("availability", availabilitystatus_enum, nullable=True),
    )

    # Add needs_review column to the tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "needs_review")
    op.drop_column("people", "availability")
    op.drop_column("people", "bio")
    op.drop_column("people", "skills")
    op.drop_column("people", "role")
    op.execute("DROP TYPE IF EXISTS availabilitystatus")
