"""person_max_capacity: add max_capacity column to people table

Revision ID: 016_person_max_capacity
Revises: 015_task_comments
Create Date: 2026-05-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "016_person_max_capacity"
down_revision = "015_task_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "people",
        sa.Column(
            "max_capacity",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
    )


def downgrade() -> None:
    op.drop_column("people", "max_capacity")
