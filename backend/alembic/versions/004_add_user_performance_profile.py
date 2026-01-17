"""Add user_performance_profiles table

Revision ID: 004_add_user_performance_profile
Revises: 003_add_strava_activities
Create Date: 2026-01-16

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_user_performance_profile'
down_revision: Union[str, None] = '003_add_strava_activities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_performance_profiles table
    op.create_table(
        'user_performance_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False),

        # Pace metrics (calculated from splits)
        sa.Column('avg_flat_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_uphill_pace_min_km', sa.Float(), nullable=True),
        sa.Column('avg_downhill_pace_min_km', sa.Float(), nullable=True),

        # Personal coefficients
        sa.Column('vertical_ability', sa.Float(), default=1.0),

        # Statistics
        sa.Column('total_activities_analyzed', sa.Integer(), default=0),
        sa.Column('total_hike_activities', sa.Integer(), default=0),
        sa.Column('total_distance_km', sa.Float(), default=0.0),
        sa.Column('total_elevation_m', sa.Float(), default=0.0),

        # Metadata
        sa.Column('last_calculated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
    )

    # Create index
    op.create_index('ix_user_performance_profiles_user_id', 'user_performance_profiles', ['user_id'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_user_performance_profiles_user_id', 'user_performance_profiles')

    # Drop table
    op.drop_table('user_performance_profiles')
