"""add name_normalized to race_results

Revision ID: 013_add_name_norm
Revises: 012_add_race_tables
Create Date: 2026-02-27 15:15:32.111616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013_add_name_norm'
down_revision: Union[str, None] = '012_add_race_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('race_results', sa.Column('name_normalized', sa.String(length=255), nullable=True))
    op.drop_index('ix_race_results_name', table_name='race_results')
    op.create_index('ix_race_results_name_normalized', 'race_results', ['name_normalized'], unique=False)
    # Widen nationality from varchar(8) to varchar(32) — some CLAX data has full country names
    op.alter_column('race_results', 'nationality', type_=sa.String(length=32), existing_type=sa.String(length=8))


def downgrade() -> None:
    op.alter_column('race_results', 'nationality', type_=sa.String(length=8), existing_type=sa.String(length=32))
    op.drop_index('ix_race_results_name_normalized', table_name='race_results')
    op.create_index('ix_race_results_name', 'race_results', ['name'], unique=False)
    op.drop_column('race_results', 'name_normalized')
