"""Add extended 7-category gradient fields to user_performance_profiles

Revision ID: 006_add_extended_gradient_fields
Revises: 005_add_strava_activity_splits
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_extended_gradient_fields'
down_revision: Union[str, None] = '005_add_strava_activity_splits'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add extended gradient pace fields (7-category system)
    # Downhill categories
    op.add_column(
        'user_performance_profiles',
        sa.Column('avg_steep_downhill_pace_min_km', sa.Float(), nullable=True)
    )
    op.add_column(
        'user_performance_profiles',
        sa.Column('avg_moderate_downhill_pace_min_km', sa.Float(), nullable=True)
    )
    op.add_column(
        'user_performance_profiles',
        sa.Column('avg_gentle_downhill_pace_min_km', sa.Float(), nullable=True)
    )

    # Uphill categories
    op.add_column(
        'user_performance_profiles',
        sa.Column('avg_gentle_uphill_pace_min_km', sa.Float(), nullable=True)
    )
    op.add_column(
        'user_performance_profiles',
        sa.Column('avg_moderate_uphill_pace_min_km', sa.Float(), nullable=True)
    )
    op.add_column(
        'user_performance_profiles',
        sa.Column('avg_steep_uphill_pace_min_km', sa.Float(), nullable=True)
    )


def downgrade() -> None:
    # Remove extended gradient fields
    op.drop_column('user_performance_profiles', 'avg_steep_uphill_pace_min_km')
    op.drop_column('user_performance_profiles', 'avg_moderate_uphill_pace_min_km')
    op.drop_column('user_performance_profiles', 'avg_gentle_uphill_pace_min_km')
    op.drop_column('user_performance_profiles', 'avg_gentle_downhill_pace_min_km')
    op.drop_column('user_performance_profiles', 'avg_moderate_downhill_pace_min_km')
    op.drop_column('user_performance_profiles', 'avg_steep_downhill_pace_min_km')
