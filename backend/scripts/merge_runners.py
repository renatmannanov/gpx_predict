#!/usr/bin/env python3
"""Merge duplicate runners in the database.

Usage:
    # Merge pairs from CSV file (format: keep_id,merge_id per line)
    python backend/scripts/merge_runners.py --pairs dupes.csv

    # Dry run - show what would happen without committing
    python backend/scripts/merge_runners.py --pairs dupes.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.features.races.db_models import (
    RaceDistance,
    RaceResultDB,
    Runner,
    RunnerNameAlias,
)


def merge_runners(db: Session, keep_id: int, merge_id: int, dry_run: bool = False) -> bool:
    """Merge runner merge_id into keep_id.

    1. Reassign all race_results from merge_id to keep_id
    2. Copy aliases from merge_id to keep_id (skip duplicates)
    3. Add merge_runner's own name as alias of keep_runner
    4. Update keep_runner's races_count
    5. Copy birth_year if keep doesn't have one
    6. Delete merge_runner

    Returns True if merge was performed, False if skipped.
    """
    keep = db.get(Runner, keep_id)
    merge = db.get(Runner, merge_id)

    if not keep:
        print(f"  ERROR: keep runner {keep_id} not found")
        return False
    if not merge:
        print(f"  ERROR: merge runner {merge_id} not found")
        return False

    # Count results to reassign
    merge_results = db.execute(
        select(func.count()).where(RaceResultDB.runner_id == merge_id)
    ).scalar()

    print(f"  Merging: #{merge.id} '{merge.name}' -> #{keep.id} '{keep.name}'")
    print(f"    Results to reassign: {merge_results}")

    if dry_run:
        # Show aliases that would be copied
        merge_aliases = db.execute(
            select(RunnerNameAlias).where(RunnerNameAlias.runner_id == merge_id)
        ).scalars().all()
        if merge_aliases:
            print(f"    Aliases to copy: {[a.name for a in merge_aliases]}")
        if merge.birth_year and not keep.birth_year:
            print(f"    Would copy birth_year: {merge.birth_year}")
        print(f"    [DRY RUN] No changes made")
        return True

    # 1. Reassign race_results
    db.execute(
        sa.update(RaceResultDB)
        .where(RaceResultDB.runner_id == merge_id)
        .values(runner_id=keep_id)
    )

    # 2. Copy aliases from merge_runner to keep_runner (skip if already exists)
    existing_alias_norms = set(
        db.execute(
            select(RunnerNameAlias.name_normalized)
            .where(RunnerNameAlias.runner_id == keep_id)
        ).scalars().all()
    )

    merge_aliases = db.execute(
        select(RunnerNameAlias).where(RunnerNameAlias.runner_id == merge_id)
    ).scalars().all()

    copied_aliases = 0
    for alias in merge_aliases:
        if alias.name_normalized not in existing_alias_norms:
            db.add(RunnerNameAlias(
                runner_id=keep_id,
                name=alias.name,
                name_normalized=alias.name_normalized,
                source=alias.source,
            ))
            existing_alias_norms.add(alias.name_normalized)
            copied_aliases += 1

    # 3. Add merge_runner's own name as alias of keep_runner
    if merge.name_normalized not in existing_alias_norms:
        db.add(RunnerNameAlias(
            runner_id=keep_id,
            name=merge.name,
            name_normalized=merge.name_normalized,
            source="merge",
        ))
        copied_aliases += 1

    print(f"    Aliases copied: {copied_aliases}")

    # 4. Copy birth_year if keep doesn't have one
    if merge.birth_year and not keep.birth_year:
        keep.birth_year = merge.birth_year
        print(f"    Copied birth_year: {merge.birth_year}")

    # 5. Delete merge_runner (CASCADE deletes remaining aliases)
    db.delete(merge)
    db.flush()

    # 6. Update keep_runner's races_count
    races_count = db.execute(
        select(func.count(func.distinct(RaceDistance.edition_id)))
        .select_from(RaceResultDB)
        .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
        .where(RaceResultDB.runner_id == keep_id)
    ).scalar()

    keep.races_count = races_count
    print(f"    Updated races_count: {races_count}")

    return True


def main() -> None:
    argp = argparse.ArgumentParser(description="Merge duplicate runners")
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

            ok = merge_runners(db, keep_id, merge_id, dry_run=args.dry_run)
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
