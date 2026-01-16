"""Add strava_tokens table

Revision ID: 002_add_strava_tokens
Revises: 001_initial
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_strava_tokens'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create strava_tokens table
    op.create_table(
        'strava_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), unique=True, nullable=False),
        sa.Column('strava_athlete_id', sa.String(20), unique=True, nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Create indexes
    op.create_index('ix_strava_tokens_user_id', 'strava_tokens', ['user_id'])
    op.create_index('ix_strava_tokens_strava_athlete_id', 'strava_tokens', ['strava_athlete_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_strava_tokens_strava_athlete_id', 'strava_tokens')
    op.drop_index('ix_strava_tokens_user_id', 'strava_tokens')

    # Drop table
    op.drop_table('strava_tokens')
