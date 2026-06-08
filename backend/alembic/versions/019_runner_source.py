"""add runners.source and composite unique (name_normalized, birth_year, source)

Switches runner matching from UNIQUE(name_normalized) to a composite key so
that namesakes and cross-source runners are kept apart instead of merged.

NOTE: This migration is applied to EMPTY race tables (after TRUNCATE) locally,
and to existing data on prod (server_default 'athletex' + NULL != NULL keep the
new constraint satisfiable on current rows).

Revision ID: 019_runner_source
Revises: 018_add_name_aliases
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "019_runner_source"
down_revision: Union[str, None] = "018_add_name_aliases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add source column with a default so existing rows are backfilled.
    op.add_column(
        "runners",
        sa.Column("source", sa.String(length=20), nullable=False,
                  server_default="athletex"),
    )
    # 2. Drop the OLD uniqueness objects on name_normalized (both exist:
    #    unique=True + index=True in the model created an index AND a constraint).
    op.drop_constraint("uq_runners_name_normalized", "runners", type_="unique")
    op.drop_index("ix_runners_name_normalized", table_name="runners")
    # 3. New composite unique + index on source.
    op.create_unique_constraint(
        "uq_runner_name_birth_source", "runners",
        ["name_normalized", "birth_year", "source"],
    )
    op.create_index("ix_runner_source", "runners", ["source"])
    # 4. name_normalized stays indexed (non-unique now).
    op.create_index("ix_runners_name_normalized", "runners", ["name_normalized"])


def downgrade() -> None:
    op.drop_index("ix_runners_name_normalized", table_name="runners")
    op.drop_index("ix_runner_source", table_name="runners")
    op.drop_constraint("uq_runner_name_birth_source", "runners", type_="unique")
    op.create_index(
        "ix_runners_name_normalized", "runners", ["name_normalized"], unique=True,
    )
    op.create_unique_constraint(
        "uq_runners_name_normalized", "runners", ["name_normalized"],
    )
    op.drop_column("runners", "source")
