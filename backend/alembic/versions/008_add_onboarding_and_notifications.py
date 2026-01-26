"""Add onboarding fields and notifications table

Revision ID: 008_add_onboarding_and_notifications
Revises: 007_add_user_run_profiles
Create Date: 2026-01-24

Adds:
- User: preferred_activity_type, onboarding_complete
- StravaSyncStatus: total_activities_estimated, activities_with_splits, initial_sync_complete
- New notifications table
"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_onboarding_and_notifications'
down_revision: Union[str, None] = '537cb9c6ae39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === User table: onboarding fields ===
    op.add_column('users', sa.Column('preferred_activity_type', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('onboarding_complete', sa.Boolean(), default=False))

    # === StravaSyncStatus: extended sync tracking ===
    op.add_column('strava_sync_status', sa.Column('total_activities_estimated', sa.Integer(), nullable=True))
    op.add_column('strava_sync_status', sa.Column('activities_with_splits', sa.Integer(), default=0))
    op.add_column('strava_sync_status', sa.Column('initial_sync_complete', sa.Integer(), default=0))

    # === Notifications table ===
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('read', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )

    # Create index for faster lookups
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_read', 'notifications', ['read'])


def downgrade() -> None:
    # Drop notifications
    op.drop_index('ix_notifications_read', 'notifications')
    op.drop_index('ix_notifications_user_id', 'notifications')
    op.drop_table('notifications')

    # Remove StravaSyncStatus columns
    op.drop_column('strava_sync_status', 'initial_sync_complete')
    op.drop_column('strava_sync_status', 'activities_with_splits')
    op.drop_column('strava_sync_status', 'total_activities_estimated')

    # Remove User columns
    op.drop_column('users', 'onboarding_complete')
    op.drop_column('users', 'preferred_activity_type')
