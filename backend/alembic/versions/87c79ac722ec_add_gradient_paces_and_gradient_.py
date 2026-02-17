"""add gradient_paces and gradient_percentiles JSON fields

Revision ID: 87c79ac722ec
Revises: 0484604b9b9d
Create Date: 2026-02-13 20:08:32.170316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87c79ac722ec'
down_revision: Union[str, None] = '0484604b9b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_run_profiles', sa.Column('gradient_paces', sa.JSON(), nullable=True))
    op.add_column('user_run_profiles', sa.Column('gradient_percentiles', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_run_profiles', 'gradient_percentiles')
    op.drop_column('user_run_profiles', 'gradient_paces')
