#!/usr/bin/env python3
"""Update name_normalized for all runners and aliases using phonetic normalization.

Usage:
    # Step 1: detect collisions (read-only)
    python -m scripts.update_phonetic_norm --detect

    # Step 2: merge collisions (if any found)
    python -m scripts.update_phonetic_norm --merge --dry-run
    python -m scripts.update_phonetic_norm --merge

    # Step 3: update all name_normalized
    python -m scripts.update_phonetic_norm --update --dry-run
    python -m scripts.update_phonetic_norm --update
"""

from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

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
from app.features.races.name_utils import normalize_name


# ---------------------------------------------------------------------------
# Phase A: Detect collisions
# ---------------------------------------------------------------------------

def detect_collisions(db: Session) -> list[tuple[int, int, str, str, int, int]]:
    """Find runners that would collide after phonetic normalization.

    Returns list of (keep_id, merge_id, keep_name, merge_name, keep_races, merge_races).
    """
    runners = db.execute(select(Runner)).scalars().all()
    print(f"Total runners: {len(runners)}")

    # Map: new_normalized -> list of (runner_id, runner_name, races_count)
    norm_map: dict[str, list[tuple[int, str, int]]] = defaultdict(list)

    for r in runners:
        new_norm = normalize_name(r.name)
        norm_map[new_norm].append((r.id, r.name, r.races_count or 0))

    # Find collisions: same new_normalized, different runners
    collisions: list[tuple[int, int, str, str, int, int]] = []

    for new_norm, group in sorted(norm_map.items()):
        if len(group) <= 1:
            continue

        # Sort by races_count descending — keep the one with the most races
        group.sort(key=lambda x: x[2], reverse=True)
        keep_id, keep_name, keep_races = group[0]

        for merge_id, merge_name, merge_races in group[1:]:
            collisions.append((keep_id, merge_id, keep_name, merge_name, keep_races, merge_races))

    return collisions


def print_collisions(collisions: list[tuple[int, int, str, str, int, int]]) -> None:
    """Print collisions as CSV."""
    if not collisions:
        print("\nNo collisions found.")
        return

    print(f"\nFound {len(collisions)} collision(s):\n")
    print("keep_id,merge_id,keep_name,merge_name,keep_races,merge_races")
    for keep_id, merge_id, keep_name, merge_name, keep_races, merge_races in collisions:
        # Escape commas in names for CSV
        kn = f'"{keep_name}"' if "," in keep_name else keep_name
        mn = f'"{merge_name}"' if "," in merge_name else merge_name
        print(f"{keep_id},{merge_id},{kn},{mn},{keep_races},{merge_races}")


# ---------------------------------------------------------------------------
# Phase B: Merge collisions (reuses logic from merge_runners.py)
# ---------------------------------------------------------------------------

def merge_runner_pair(db: Session, keep_id: int, merge_id: int, dry_run: bool = False) -> bool:
    """Merge runner merge_id into keep_id.

    Same logic as merge_runners.py:
    1. Reassign all race_results from merge_id to keep_id
    2. Copy aliases from merge_id to keep_id (skip duplicates)
    3. Add merge_runner's own name as alias of keep_runner
    4. Update keep_runner's races_count
    5. Copy birth_year if keep doesn't have one
    6. Delete merge_runner
    """
    keep = db.get(Runner, keep_id)
    merge = db.get(Runner, merge_id)

    if not keep:
        print(f"  ERROR: keep runner {keep_id} not found")
        return False
    if not merge:
        print(f"  ERROR: merge runner {merge_id} not found")
        return False

    merge_results = db.execute(
        select(func.count()).where(RaceResultDB.runner_id == merge_id)
    ).scalar()

    print(f"  Merging: #{merge.id} '{merge.name}' -> #{keep.id} '{keep.name}'")
    print(f"    Results to reassign: {merge_results}")

    if dry_run:
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


def merge_collisions(db: Session, dry_run: bool = False) -> None:
    """Detect and merge all collisions."""
    collisions = detect_collisions(db)

    if not collisions:
        print("\nNo collisions to merge.")
        return

    print_collisions(collisions)

    if dry_run:
        print(f"\n[DRY RUN MODE]\n")

    merged = 0
    errors = 0

    for keep_id, merge_id, keep_name, merge_name, _, _ in collisions:
        print(f"\nPair: keep={keep_id} '{keep_name}', merge={merge_id} '{merge_name}'")

        ok = merge_runner_pair(db, keep_id, merge_id, dry_run=dry_run)
        if ok:
            merged += 1
        else:
            errors += 1

    if not dry_run and merged > 0:
        db.commit()
        print(f"\nCommitted. Merged {merged} pairs.")
    else:
        if dry_run:
            print(f"\n[DRY RUN] Would merge {merged} pairs.")
        if errors > 0:
            print(f"Errors: {errors}")


# ---------------------------------------------------------------------------
# Phase C: Update all name_normalized
# ---------------------------------------------------------------------------

def update_all(db: Session, dry_run: bool = False) -> None:
    """Update name_normalized for all runners and aliases."""
    batch_size = 1000

    # --- Runners ---
    runners = db.execute(select(Runner)).scalars().all()
    total_runners = len(runners)
    updated_runners = 0
    unchanged_runners = 0

    print(f"Processing {total_runners} runners...")

    for i, runner in enumerate(runners):
        new_norm = normalize_name(runner.name)
        if runner.name_normalized != new_norm:
            runner.name_normalized = new_norm
            updated_runners += 1
        else:
            unchanged_runners += 1

        if (i + 1) % batch_size == 0:
            if not dry_run:
                db.flush()
            print(f"  Runners: {i + 1}/{total_runners} processed...")

    print(f"\nRunners: {updated_runners} updated, {unchanged_runners} unchanged")

    # --- Aliases ---
    aliases = db.execute(select(RunnerNameAlias)).scalars().all()
    total_aliases = len(aliases)
    updated_aliases = 0
    unchanged_aliases = 0

    print(f"\nProcessing {total_aliases} aliases...")

    for i, alias in enumerate(aliases):
        new_norm = normalize_name(alias.name)
        if alias.name_normalized != new_norm:
            alias.name_normalized = new_norm
            updated_aliases += 1
        else:
            unchanged_aliases += 1

        if (i + 1) % batch_size == 0:
            if not dry_run:
                db.flush()
            print(f"  Aliases: {i + 1}/{total_aliases} processed...")

    print(f"Aliases: {updated_aliases} updated, {unchanged_aliases} unchanged")

    # --- Commit ---
    if not dry_run:
        db.commit()
        print(f"\nCommitted all changes.")
    else:
        db.rollback()
        print(f"\n[DRY RUN] No changes committed.")

    print(f"\nSummary:")
    print(f"  Runners: {updated_runners}/{total_runners} updated")
    print(f"  Aliases: {updated_aliases}/{total_aliases} updated")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    argp = argparse.ArgumentParser(
        description="Update name_normalized for all runners and aliases using phonetic normalization"
    )
    argp.add_argument("--detect", action="store_true", help="Phase A: detect collisions (read-only)")
    argp.add_argument("--merge", action="store_true", help="Phase B: merge collision pairs")
    argp.add_argument("--update", action="store_true", help="Phase C: update all name_normalized")
    argp.add_argument("--dry-run", action="store_true", help="Don't commit changes")
    args = argp.parse_args()

    if not any([args.detect, args.merge, args.update]):
        argp.print_help()
        sys.exit(1)

    init_db()
    db = SessionLocal()

    try:
        if args.detect:
            collisions = detect_collisions(db)
            print_collisions(collisions)

        elif args.merge:
            merge_collisions(db, dry_run=args.dry_run)

        elif args.update:
            update_all(db, dry_run=args.dry_run)

    finally:
        db.close()


if __name__ == "__main__":
    main()
