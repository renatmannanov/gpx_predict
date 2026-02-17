"""add profile_snapshots table

Revision ID: 0484604b9b9d
Revises: 010_sync_progress_tracking
Create Date: 2026-02-13 19:41:22.779209

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0484604b9b9d'
down_revision: Union[str, None] = '010_sync_progress_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('profile_snapshots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('profile_type', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.String(length=100), nullable=False),
    sa.Column('profile_data', sa.JSON(), nullable=False),
    sa.Column('activities_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_profile_snapshots_user_id'), 'profile_snapshots', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_profile_snapshots_user_id'), table_name='profile_snapshots')
    op.drop_table('profile_snapshots')
