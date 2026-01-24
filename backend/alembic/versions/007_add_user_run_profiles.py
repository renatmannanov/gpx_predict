"""Add user_run_profiles table for trail running

Revision ID: 007_add_user_run_profiles
Revises: 006_add_extended_gradient_fields
Create Date: 2026-01-23

Creates separate table for Run/TrailRun performance profiles.
Keeps existing user_performance_profiles for hiking (backward compatible).
"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_user_run_profiles'
down_revision: Union[str, None] = '006_add_extended_gradient_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_run_profiles table (parallel to user_performance_profiles)
    op.create_table(
        'user_run_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False),

        # === 7-category pace metrics for running ===
        sa.Column('avg_flat_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_gentle_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_moderate_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_steep_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_gentle_downhill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_moderate_downhill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_steep_downhill_pace_min_km', sa.Float(), nullable=True),

        # === Walk threshold ===
        # Auto-detected from splits or set manually (default 25%)
        sa.Column('walk_threshold_percent', sa.Float(), nullable=True, default=25.0),

        # === Statistics ===
        sa.Column('total_activities', sa.Integer(), default=0),
        sa.Column('total_distance_km', sa.Float(), default=0.0),
        sa.Column('total_elevation_m', sa.Float(), default=0.0),

        # === Metadata ===
        sa.Column('last_calculated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
    )

    # Create index
    op.create_index('ix_user_run_profiles_user_id', 'user_run_profiles', ['user_id'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_user_run_profiles_user_id', 'user_run_profiles')

    # Drop table
    op.drop_table('user_run_profiles')
