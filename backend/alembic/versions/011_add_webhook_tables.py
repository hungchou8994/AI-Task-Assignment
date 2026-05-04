"""add_webhook_tables

Revision ID: 98ad8b731960
Revises: 010
Create Date: 2026-04-09 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_add_webhook_tables'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create webhook_subscriptions table
    op.create_table(
        'webhook_subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('target_url', sa.String(length=1024), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_webhook_subscriptions_workspace_id', 'webhook_subscriptions', ['workspace_id'], unique=False)

    # 2. Create webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('subscription_id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['subscription_id'], ['webhook_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_webhook_deliveries_subscription_id', 'webhook_deliveries', ['subscription_id'], unique=False)


def downgrade():
    op.drop_index('ix_webhook_deliveries_subscription_id', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_index('ix_webhook_subscriptions_workspace_id', table_name='webhook_subscriptions')
    op.drop_table('webhook_subscriptions')
