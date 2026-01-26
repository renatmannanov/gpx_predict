"""Add sample count columns to user_run_profiles

Revision ID: 007a_add_sample_count_columns
Revises: 007_add_user_run_profiles
Create Date: 2026-01-23 15:22:12.156239

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007a_add_sample_count_columns'
down_revision: Union[str, None] = '007_add_user_run_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sample count columns to track data quality per gradient category
    op.add_column('user_run_profiles', sa.Column('flat_sample_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user_run_profiles', sa.Column('gentle_uphill_sample_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user_run_profiles', sa.Column('moderate_uphill_sample_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user_run_profiles', sa.Column('steep_uphill_sample_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user_run_profiles', sa.Column('gentle_downhill_sample_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user_run_profiles', sa.Column('moderate_downhill_sample_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user_run_profiles', sa.Column('steep_downhill_sample_count', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('user_run_profiles', 'steep_downhill_sample_count')
    op.drop_column('user_run_profiles', 'moderate_downhill_sample_count')
    op.drop_column('user_run_profiles', 'gentle_downhill_sample_count')
    op.drop_column('user_run_profiles', 'steep_uphill_sample_count')
    op.drop_column('user_run_profiles', 'moderate_uphill_sample_count')
    op.drop_column('user_run_profiles', 'gentle_uphill_sample_count')
    op.drop_column('user_run_profiles', 'flat_sample_count')
