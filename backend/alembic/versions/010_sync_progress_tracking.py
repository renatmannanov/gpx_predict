"""Add sync progress tracking fields

Revision ID: 010_sync_progress_tracking
Revises: a1dfa27fcacc
Create Date: 2026-01-29

Adds:
- StravaSyncStatus: first_batch_notified, last_progress_checkpoint
- Renames: last_recalc_checkpoint -> last_progress_checkpoint (reused for new purpose)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_sync_progress_tracking'
down_revision: Union[str, None] = 'a1dfa27fcacc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add first_batch_notified flag
    op.add_column(
        'strava_sync_status',
        sa.Column('first_batch_notified', sa.Integer(), default=0)
    )

    # last_recalc_checkpoint already exists, we'll reuse it as last_progress_checkpoint
    # Just reset all values to 0 for clean state
    op.execute("UPDATE strava_sync_status SET last_recalc_checkpoint = 0")


def downgrade() -> None:
    op.drop_column('strava_sync_status', 'first_batch_notified')
