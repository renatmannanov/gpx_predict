"""add telegram_username to users

Revision ID: 017_add_tg_username
Revises: 016_add_city
Create Date: 2026-03-14
"""

revision = "017_add_tg_username"
down_revision = "016_add_city"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_username", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_username")
