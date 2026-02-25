"""align telegram_id and strava_athlete_id types to BigInteger

Revision ID: 011_align_id_types
Revises: add_race_search_name
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_align_id_types'
down_revision: Union[str, None] = 'add_race_search_name'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert telegram_id from String(20) to BigInteger
    op.alter_column(
        'users', 'telegram_id',
        type_=sa.BigInteger(),
        postgresql_using='telegram_id::bigint',
        existing_nullable=True
    )

    # Convert strava_athlete_id on users table from String(20) to BigInteger
    op.alter_column(
        'users', 'strava_athlete_id',
        type_=sa.BigInteger(),
        postgresql_using='strava_athlete_id::bigint',
        existing_nullable=True
    )

    # Convert strava_athlete_id on strava_tokens table from String(20) to BigInteger
    op.alter_column(
        'strava_tokens', 'strava_athlete_id',
        type_=sa.BigInteger(),
        postgresql_using='strava_athlete_id::bigint',
        existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        'strava_tokens', 'strava_athlete_id',
        type_=sa.String(20),
        existing_nullable=False
    )
    op.alter_column(
        'users', 'strava_athlete_id',
        type_=sa.String(20),
        existing_nullable=True
    )
    op.alter_column(
        'users', 'telegram_id',
        type_=sa.String(20),
        existing_nullable=True
    )
