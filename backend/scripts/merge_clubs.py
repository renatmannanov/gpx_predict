#!/usr/bin/env python3
"""Merge duplicate clubs in the database.

Usage:
    # Merge pairs from CSV file (format: keep_id,merge_id per line)
    python backend/scripts/merge_clubs.py --pairs dupes.csv

    # Dry run - show what would happen without committing
    python backend/scripts/merge_clubs.py --pairs dupes.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

# Fix Windows console encoding for Cyrillic club names
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.features.races.db_models import (
    Club,
    ClubNameAlias,
    Runner,
)


def merge_clubs(db: Session, keep_id: int, merge_id: int, dry_run: bool = False) -> bool:
    """Merge club merge_id into keep_id.

    1. Reassign all runners.club_id from merge_id to keep_id
    2. Update runners.club text field to keep_club.name
    3. Copy aliases from merge_club to keep_club (skip duplicates)
    4. Add merge_club's own name as alias of keep_club
    5. Update keep_club's runners_count
    6. Delete merge_club (CASCADE cleans up remaining aliases)

    Returns True if merge was performed, False if skipped.
    """
    keep = db.get(Club, keep_id)
    merge = db.get(Club, merge_id)

    if not keep:
        print(f"  ERROR: keep club {keep_id} not found")
        return False
    if not merge:
        print(f"  ERROR: merge club {merge_id} not found")
        return False

    # Count runners to reassign
    merge_runners_count = db.execute(
        select(func.count()).where(Runner.club_id == merge_id)
    ).scalar()

    print(f"  Merging: #{merge.id} '{merge.name}' -> #{keep.id} '{keep.name}'")
    print(f"    Runners to reassign: {merge_runners_count}")

    if dry_run:
        merge_aliases = db.execute(
            select(ClubNameAlias).where(ClubNameAlias.club_id == merge_id)
        ).scalars().all()
        if merge_aliases:
            print(f"    Aliases to copy: {[a.name for a in merge_aliases]}")
        print(f"    Would also add merge club name as alias: '{merge.name}'")
        print(f"    [DRY RUN] No changes made")
        return True

    # 1. Reassign runners.club_id from merge_id to keep_id
    # 2. Update runners.club text field to keep_club.name
    db.execute(
        sa.update(Runner)
        .where(Runner.club_id == merge_id)
        .values(club_id=keep_id, club=keep.name)
    )

    # 3. Copy aliases from merge_club to keep_club (skip if already exists)
    existing_alias_norms = set(
        db.execute(
            select(ClubNameAlias.name_normalized)
            .where(ClubNameAlias.club_id == keep_id)
        ).scalars().all()
    )

    merge_aliases = db.execute(
        select(ClubNameAlias).where(ClubNameAlias.club_id == merge_id)
    ).scalars().all()

    copied_aliases = 0
    for alias in merge_aliases:
        if alias.name_normalized not in existing_alias_norms:
            db.add(ClubNameAlias(
                club_id=keep_id,
                name=alias.name,
                name_normalized=alias.name_normalized,
                source=alias.source,
            ))
            existing_alias_norms.add(alias.name_normalized)
            copied_aliases += 1

    # 4. Add merge_club's own name as alias of keep_club
    if merge.name_normalized not in existing_alias_norms:
        db.add(ClubNameAlias(
            club_id=keep_id,
            name=merge.name,
            name_normalized=merge.name_normalized,
            source="merge",
        ))
        copied_aliases += 1

    print(f"    Aliases copied: {copied_aliases}")

    # 5. Update keep_club's runners_count
    # (flush first so the reassigned runners are visible)
    db.flush()

    runners_count = db.execute(
        select(func.count()).where(Runner.club_id == keep_id)
    ).scalar()

    keep.runners_count = runners_count
    print(f"    Updated runners_count: {runners_count}")

    # 6. Delete merge_club (CASCADE cleans up remaining aliases)
    db.delete(merge)
    db.flush()

    return True


def main() -> None:
    argp = argparse.ArgumentParser(description="Merge duplicate clubs")
    argp.add_argument(
        "--pairs", required=True,
        help="CSV file with keep_id,merge_id pairs (one per line)"
    )
    argp.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without committing"
    )
    args = argp.parse_args()

    # Load pairs from CSV
    pairs_path = Path(args.pairs)
    if not pairs_path.exists():
        print(f"File not found: {pairs_path}")
        sys.exit(1)

    pairs: list[tuple[int, int]] = []
    with open(pairs_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if len(row) < 2:
                print(f"Skipping invalid row: {row}")
                continue
            try:
                pairs.append((int(row[0].strip()), int(row[1].strip())))
            except ValueError:
                # Skip header row or non-numeric
                if row[0].strip().lower() not in ("keep_id", "keep"):
                    print(f"Skipping non-numeric row: {row}")
                continue

    if not pairs:
        print("No valid pairs found in CSV")
        sys.exit(1)

    print(f"Loaded {len(pairs)} pairs from {pairs_path}")
    if args.dry_run:
        print("[DRY RUN MODE]\n")

    # Initialize DB
    init_db()
    db = SessionLocal()

    try:
        merged = 0
        errors = 0

        for keep_id, merge_id in pairs:
            print(f"\nPair: keep={keep_id}, merge={merge_id}")

            if keep_id == merge_id:
                print("  SKIP: same ID")
                continue

            ok = merge_clubs(db, keep_id, merge_id, dry_run=args.dry_run)
            if ok:
                merged += 1
            else:
                errors += 1

        if not args.dry_run and merged > 0:
            db.commit()
            print(f"\nCommitted. Merged {merged} pairs.")
        else:
            if args.dry_run:
                print(f"\n[DRY RUN] Would merge {merged} pairs.")
            if errors > 0:
                print(f"Errors: {errors}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
