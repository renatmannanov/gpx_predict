"""merge_heads

Revision ID: a1dfa27fcacc
Revises: 009_add_recalc_tracking, 009_rename_to_hiking_profile
Create Date: 2026-01-28 18:11:24.900263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1dfa27fcacc'
down_revision: Union[str, None] = ('009_add_recalc_tracking', '009_rename_to_hiking_profile')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
