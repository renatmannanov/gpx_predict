"""add race_search_name to users

Revision ID: add_race_search_name
Revises: 94b0f02c9957
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_race_search_name'
down_revision: Union[str, None] = '94b0f02c9957'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('race_search_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'race_search_name')
