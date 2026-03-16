"""add runner_name_aliases and club_name_aliases tables

Revision ID: 018_add_name_aliases
Revises: 017_add_tg_username
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "018_add_name_aliases"
down_revision: Union[str, None] = "017_add_tg_username"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. runner_name_aliases
    op.create_table(
        "runner_name_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("runner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_normalized", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["runner_id"],
            ["runners.id"],
            name="fk_runner_aliases_runner_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_runner_aliases_runner_id",
        "runner_name_aliases",
        ["runner_id"],
        unique=False,
    )
    op.create_index(
        "ix_runner_aliases_name_norm",
        "runner_name_aliases",
        ["name_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_runner_aliases_unique",
        "runner_name_aliases",
        ["runner_id", "name_normalized"],
        unique=True,
    )

    # 2. club_name_aliases
    op.create_table(
        "club_name_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_normalized", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
            name="fk_club_aliases_club_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_club_aliases_club_id",
        "club_name_aliases",
        ["club_id"],
        unique=False,
    )
    op.create_index(
        "ix_club_aliases_name_norm",
        "club_name_aliases",
        ["name_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_club_aliases_unique",
        "club_name_aliases",
        ["club_id", "name_normalized"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_club_aliases_unique", table_name="club_name_aliases")
    op.drop_index("ix_club_aliases_name_norm", table_name="club_name_aliases")
    op.drop_index("ix_club_aliases_club_id", table_name="club_name_aliases")
    op.drop_table("club_name_aliases")

    op.drop_index("ix_runner_aliases_unique", table_name="runner_name_aliases")
    op.drop_index("ix_runner_aliases_name_norm", table_name="runner_name_aliases")
    op.drop_index("ix_runner_aliases_runner_id", table_name="runner_name_aliases")
    op.drop_table("runner_name_aliases")
