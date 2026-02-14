"""add gradient_paces percentiles and sample_counts to hiking profile

Revision ID: 94b0f02c9957
Revises: 87c79ac722ec
Create Date: 2026-02-14 13:27:18.267828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94b0f02c9957'
down_revision: Union[str, None] = '87c79ac722ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_hiking_profiles', sa.Column('flat_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('gentle_uphill_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('moderate_uphill_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('steep_uphill_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('gentle_downhill_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('moderate_downhill_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('steep_downhill_sample_count', sa.Integer(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('gradient_paces', sa.JSON(), nullable=True))
    op.add_column('user_hiking_profiles', sa.Column('gradient_percentiles', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_hiking_profiles', 'gradient_percentiles')
    op.drop_column('user_hiking_profiles', 'gradient_paces')
    op.drop_column('user_hiking_profiles', 'steep_downhill_sample_count')
    op.drop_column('user_hiking_profiles', 'moderate_downhill_sample_count')
    op.drop_column('user_hiking_profiles', 'gentle_downhill_sample_count')
    op.drop_column('user_hiking_profiles', 'steep_uphill_sample_count')
    op.drop_column('user_hiking_profiles', 'moderate_uphill_sample_count')
    op.drop_column('user_hiking_profiles', 'gentle_uphill_sample_count')
    op.drop_column('user_hiking_profiles', 'flat_sample_count')
