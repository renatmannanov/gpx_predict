"""add city column to race_results

Revision ID: 016_add_city
Revises: 015_add_status
Create Date: 2026-03-02

Adds `city` column to race_results for storing participant city
separately from club (AM parser was writing city into club field).
"""

revision = "016_add_city"
down_revision = "015_add_status"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("race_results", sa.Column("city", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("race_results", "city")
