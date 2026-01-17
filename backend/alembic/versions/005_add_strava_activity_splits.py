"""Add strava_activity_splits table and splits_synced flag

Revision ID: 005_add_strava_activity_splits
Revises: 004_add_user_performance_profile
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_strava_activity_splits'
down_revision: Union[str, None] = '004_add_user_performance_profile'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add splits_synced flag to strava_activities
    op.add_column(
        'strava_activities',
        sa.Column('splits_synced', sa.Integer(), default=0)
    )

    # Create strava_activity_splits table
    op.create_table(
        'strava_activity_splits',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('activity_id', sa.Integer(), sa.ForeignKey('strava_activities.id'), nullable=False),

        # Split info
        sa.Column('split_number', sa.Integer(), nullable=False),
        sa.Column('distance_m', sa.Float(), nullable=False),

        # Time
        sa.Column('moving_time_s', sa.Integer(), nullable=False),
        sa.Column('elapsed_time_s', sa.Integer(), nullable=False),

        # Elevation (key for terrain analysis)
        sa.Column('elevation_diff_m', sa.Float(), nullable=True),

        # Performance
        sa.Column('average_speed_mps', sa.Float(), nullable=True),
        sa.Column('average_heartrate', sa.Float(), nullable=True),
        sa.Column('pace_zone', sa.Integer(), nullable=True),
    )

    # Create indexes
    op.create_index(
        'ix_strava_activity_splits_activity_id',
        'strava_activity_splits',
        ['activity_id']
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_strava_activity_splits_activity_id', 'strava_activity_splits')

    # Drop table
    op.drop_table('strava_activity_splits')

    # Remove splits_synced column
    op.drop_column('strava_activities', 'splits_synced')
