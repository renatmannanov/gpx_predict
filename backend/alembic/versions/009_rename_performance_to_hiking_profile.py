"""Rename user_performance_profiles to user_hiking_profiles

Revision ID: 009_rename_to_hiking_profile
Revises: 008_add_onboarding
Create Date: 2026-01-27

Renames:
- Table: user_performance_profiles -> user_hiking_profiles
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '009_rename_to_hiking_profile'
down_revision: Union[str, None] = '008_add_onboarding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('user_performance_profiles', 'user_hiking_profiles')


def downgrade() -> None:
    op.rename_table('user_hiking_profiles', 'user_performance_profiles')
