"""add clubs, runners tables and runner_id FK in race_results

Revision ID: 014_add_runners
Revises: 013_add_name_norm
Create Date: 2026-03-01

Creates `clubs` and `runners` tables for unique identification,
adds `runner_id` FK to `race_results`, adds `club_id` FK to `runners`,
and populates both from existing race_results data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014_add_runners'
down_revision: Union[str, None] = '013_add_name_norm'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create clubs table
    op.create_table(
        'clubs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('name_normalized', sa.String(length=255), nullable=False),
        sa.Column('runners_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name_normalized', name='uq_clubs_name_normalized'),
    )
    op.create_index('ix_clubs_name_normalized', 'clubs', ['name_normalized'], unique=True)

    # 2. Create runners table
    op.create_table(
        'runners',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('name_normalized', sa.String(length=255), nullable=False),
        sa.Column('club', sa.String(length=255), nullable=True),
        sa.Column('club_id', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(length=4), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=True),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('races_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name_normalized', name='uq_runners_name_normalized'),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], name='fk_runners_club_id'),
    )
    op.create_index('ix_runners_name_normalized', 'runners', ['name_normalized'], unique=True)

    # 3. Add runner_id column to race_results (nullable for now)
    op.add_column('race_results', sa.Column('runner_id', sa.Integer(), nullable=True))
    op.create_index('ix_race_results_runner_id', 'race_results', ['runner_id'], unique=False)
    op.create_foreign_key(
        'fk_race_results_runner_id', 'race_results', 'runners',
        ['runner_id'], ['id'],
    )

    # 4. Populate clubs from existing race_results (unique club names)
    # Group by LOWER(TRIM(club)) to avoid duplicates from case differences
    op.execute("""
        INSERT INTO clubs (name, name_normalized, runners_count, created_at, updated_at)
        SELECT
            MAX(club),
            LOWER(TRIM(club)),
            COUNT(DISTINCT name_normalized),
            NOW(),
            NOW()
        FROM race_results
        WHERE club IS NOT NULL AND TRIM(club) != ''
        GROUP BY LOWER(TRIM(club))
        ORDER BY LOWER(TRIM(club))
    """)

    # 5. Populate runners from existing race_results
    # Use DISTINCT ON to get latest result per runner (highest id = most recent parse)
    op.execute("""
        INSERT INTO runners (name, name_normalized, club, gender, category, birth_year, races_count, created_at, updated_at)
        SELECT DISTINCT ON (rr.name_normalized)
            rr.name,
            rr.name_normalized,
            rr.club,
            rr.gender,
            rr.category,
            rr.birth_year,
            (
                SELECT COUNT(DISTINCT rd2.edition_id)
                FROM race_results rr2
                JOIN race_distances rd2 ON rr2.distance_id = rd2.id
                WHERE rr2.name_normalized = rr.name_normalized
            ),
            NOW(),
            NOW()
        FROM race_results rr
        WHERE rr.name_normalized IS NOT NULL
        ORDER BY rr.name_normalized, rr.id DESC
    """)

    # 6. Link runners to clubs
    op.execute("""
        UPDATE runners r
        SET club_id = c.id
        FROM clubs c
        WHERE r.club IS NOT NULL
            AND LOWER(TRIM(r.club)) = c.name_normalized
    """)

    # 7. Update race_results.runner_id from runners
    op.execute("""
        UPDATE race_results rr
        SET runner_id = r.id
        FROM runners r
        WHERE rr.name_normalized = r.name_normalized
            AND rr.name_normalized IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_constraint('fk_race_results_runner_id', 'race_results', type_='foreignkey')
    op.drop_index('ix_race_results_runner_id', table_name='race_results')
    op.drop_column('race_results', 'runner_id')
    op.drop_index('ix_runners_name_normalized', table_name='runners')
    op.drop_table('runners')
    op.drop_index('ix_clubs_name_normalized', table_name='clubs')
    op.drop_table('clubs')
