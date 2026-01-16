"""Add strava_activities and strava_sync_status tables

Revision ID: 003_add_strava_activities
Revises: 002_add_strava_tokens
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_strava_activities'
down_revision: Union[str, None] = '002_add_strava_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create strava_activities table
    op.create_table(
        'strava_activities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('strava_id', sa.BigInteger(), unique=True, nullable=False),

        # Activity info
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),

        # Core metrics
        sa.Column('distance_m', sa.Float(), nullable=True),
        sa.Column('moving_time_s', sa.Integer(), nullable=True),
        sa.Column('elapsed_time_s', sa.Integer(), nullable=True),
        sa.Column('elevation_gain_m', sa.Float(), nullable=True),
        sa.Column('elevation_loss_m', sa.Float(), nullable=True),

        # Speed
        sa.Column('avg_speed_mps', sa.Float(), nullable=True),
        sa.Column('max_speed_mps', sa.Float(), nullable=True),

        # Heart rate
        sa.Column('avg_heartrate', sa.Float(), nullable=True),
        sa.Column('max_heartrate', sa.Float(), nullable=True),

        # Running specific
        sa.Column('avg_cadence', sa.Float(), nullable=True),

        # Strava computed
        sa.Column('suffer_score', sa.Integer(), nullable=True),

        # Metadata
        sa.Column('synced_at', sa.DateTime(), nullable=True),
    )

    # Create strava_sync_status table
    op.create_table(
        'strava_sync_status',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False),

        # Sync progress
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('oldest_synced_date', sa.DateTime(), nullable=True),
        sa.Column('newest_synced_date', sa.DateTime(), nullable=True),

        # Counts
        sa.Column('total_activities_synced', sa.Integer(), default=0),

        # Status
        sa.Column('sync_in_progress', sa.Integer(), default=0),
        sa.Column('last_error', sa.String(500), nullable=True),
    )

    # Create indexes
    op.create_index('ix_strava_activities_user_id', 'strava_activities', ['user_id'])
    op.create_index('ix_strava_activities_start_date', 'strava_activities', ['start_date'])
    op.create_index('ix_strava_activities_strava_id', 'strava_activities', ['strava_id'])
    op.create_index('ix_strava_sync_status_user_id', 'strava_sync_status', ['user_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_strava_sync_status_user_id', 'strava_sync_status')
    op.drop_index('ix_strava_activities_strava_id', 'strava_activities')
    op.drop_index('ix_strava_activities_start_date', 'strava_activities')
    op.drop_index('ix_strava_activities_user_id', 'strava_activities')

    # Drop tables
    op.drop_table('strava_sync_status')
    op.drop_table('strava_activities')
