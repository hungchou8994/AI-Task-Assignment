"""Add user model and workspace owner

Revision ID: 007
Revises: 006
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Create default admin user
    default_user_id = str(uuid.uuid4())
    # Using a default password "admin123" - should be changed after first login
    # pbkdf2_sha256 hash of "admin123"
    default_password_hash = "$pbkdf2-sha256$29000$tjZG6D3n3LvvfY8x5rxXig$8P5qt7NAf2LSdsiM0d0Jj4hYrRfBvKTH6LqK9r8ak8Y"

    op.execute(
        f"""
        INSERT INTO users (id, email, hashed_password)
        VALUES ('{default_user_id}', 'admin@example.com', '{default_password_hash}')
        """
    )

    # 3. Add owner_id column to workspaces as NULLABLE initially
    op.add_column(
        "workspaces",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 4. Assign all existing workspaces to default user
    op.execute(
        f"UPDATE workspaces SET owner_id = '{default_user_id}' WHERE owner_id IS NULL"
    )

    # 5. Make owner_id NOT NULL and add FK constraint
    op.alter_column("workspaces", "owner_id", nullable=False)
    op.create_foreign_key(
        "fk_workspaces_owner_id",
        "workspaces",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_workspaces_owner_id", table_name="workspaces")
    op.drop_constraint("fk_workspaces_owner_id", "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
