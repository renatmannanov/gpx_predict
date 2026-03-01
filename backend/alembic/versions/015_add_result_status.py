"""add status column to race_results

Revision ID: 015_add_status
Revises: 014_add_runners
Create Date: 2026-03-01

Adds `status` column to race_results for DNF/DNS tracking.
Populates from existing `over_time_limit` column.
Does NOT remove `over_time_limit` (backward compat).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015_add_status'
down_revision: Union[str, None] = '014_add_runners'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'race_results',
        sa.Column('status', sa.String(length=20), server_default='finished', nullable=True),
    )

    # Populate status from over_time_limit
    op.execute("""
        UPDATE race_results
        SET status = CASE
            WHEN over_time_limit = true THEN 'over_time_limit'
            ELSE 'finished'
        END
    """)


def downgrade() -> None:
    op.drop_column('race_results', 'status')
