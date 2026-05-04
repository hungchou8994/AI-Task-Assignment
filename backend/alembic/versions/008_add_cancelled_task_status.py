"""Add cancelled value to taskstatus enum

Revision ID: 008
Revises: 007
Create Date: 2026-04-06
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE to add enum values; this is safe on live
    # systems and does not lock the table.
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # To downgrade, ensure no rows have status='cancelled' first, then recreate.
    # Omitting automated downgrade to avoid data loss.
    pass
