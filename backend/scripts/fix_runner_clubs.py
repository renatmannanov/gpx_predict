#!/usr/bin/env python3
"""Fix runner club assignments using alias resolution and latest race result.

For each runner, finds the latest race result with a non-empty club,
resolves it through club_name_aliases, and sets the canonical club.

Usage:
    python backend/scripts/fix_runner_clubs.py --dry-run
    python backend/scripts/fix_runner_clubs.py
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.features.races.db_models import Club, ClubNameAlias, Runner


def fix_runner_clubs(db: Session, dry_run: bool = False) -> None:
    """Fix club assignments for all runners based on latest result + aliases."""

    # Step 1: Get latest club text for each runner from race_results
    # (latest = highest year, then latest edition date)
    latest_clubs_sql = text("""
        SELECT DISTINCT ON (rr.runner_id)
            rr.runner_id,
            rr.club as club_text,
            re.year
        FROM race_results rr
        JOIN race_distances rd ON rr.distance_id = rd.id
        JOIN race_editions re ON rd.edition_id = re.id
        WHERE rr.runner_id IS NOT NULL
          AND rr.club IS NOT NULL
          AND TRIM(rr.club) != ''
        ORDER BY rr.runner_id, re.year DESC, re.date DESC NULLS LAST
    """)

    rows = db.execute(latest_clubs_sql).fetchall()
    print(f"Runners with club in results: {len(rows)}")

    # Build alias lookup: name_normalized -> (club_id, canonical_name)
    aliases = db.execute(
        select(ClubNameAlias.name_normalized, ClubNameAlias.club_id)
    ).fetchall()
    alias_map: dict[str, int] = {a.name_normalized: a.club_id for a in aliases}

    # Build club lookup: id -> Club
    clubs = db.execute(select(Club)).scalars().all()
    club_by_id: dict[int, Club] = {c.id: c for c in clubs}
    club_by_norm: dict[str, Club] = {c.name_normalized: c for c in clubs}

    changed = 0
    alias_resolved = 0
    not_found = 0

    for row in rows:
        runner_id = row.runner_id
        club_text = row.club_text.strip()
        club_norm = club_text.lower()

        # Resolve: direct match first, then alias
        club = club_by_norm.get(club_norm)
        resolved_via = "direct"

        if not club:
            club_id = alias_map.get(club_norm)
            if club_id:
                club = club_by_id.get(club_id)
                resolved_via = "alias"

        if not club:
            not_found += 1
            continue

        # Check if runner needs update
        runner = db.get(Runner, runner_id)
        if not runner:
            continue

        old_club = runner.club
        old_club_id = runner.club_id
        new_club = club.name  # canonical
        new_club_id = club.id

        if old_club_id == new_club_id and old_club == new_club:
            continue  # already correct

        if resolved_via == "alias":
            alias_resolved += 1

        if dry_run:
            if old_club != new_club:
                print(f"  [{runner.name}] club: '{old_club}' -> '{new_club}' (via {resolved_via}, year {row.year})")
        else:
            runner.club = new_club
            runner.club_id = new_club_id
            runner.updated_at = datetime.now(timezone.utc)

        changed += 1

    if not dry_run:
        db.commit()

        # Recalculate club runners_count
        db.execute(text("""
            UPDATE clubs c
            SET runners_count = (
                SELECT COUNT(*) FROM runners r WHERE r.club_id = c.id
            )
        """))
        db.commit()

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Results:")
    print(f"  Changed: {changed}")
    print(f"  Resolved via alias: {alias_resolved}")
    print(f"  Club not found: {not_found}")


def main() -> None:
    argp = argparse.ArgumentParser(description="Fix runner club assignments via aliases")
    argp.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = argp.parse_args()

    init_db()
    db = SessionLocal()

    try:
        fix_runner_clubs(db, dry_run=args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    main()
