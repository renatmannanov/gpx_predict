"""Add profile recalculation tracking fields

Revision ID: 009_add_recalc_tracking
Revises: 008_add_onboarding
Create Date: 2026-01-24

Adds:
- StravaSyncStatus: last_recalc_checkpoint, new_activities_since_recalc
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_recalc_tracking'
down_revision: Union[str, None] = '008_add_onboarding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Profile recalculation tracking
    op.add_column('strava_sync_status', sa.Column('last_recalc_checkpoint', sa.Integer(), default=0))
    op.add_column('strava_sync_status', sa.Column('new_activities_since_recalc', sa.Integer(), default=0))


def downgrade() -> None:
    op.drop_column('strava_sync_status', 'new_activities_since_recalc')
    op.drop_column('strava_sync_status', 'last_recalc_checkpoint')
