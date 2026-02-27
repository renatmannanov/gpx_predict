#!/usr/bin/env python3
"""Batch parse CLAX race results from catalog.yaml into the database.

Usage:
    # Parse one race (all editions with status: new)
    python backend/scripts/batch_parse.py --race-id amangeldy_race_kz

    # Dry run — show what would be parsed
    python backend/scripts/batch_parse.py --race-id amangeldy_race_kz --dry-run

    # Force re-parse (even if already parsed)
    python backend/scripts/batch_parse.py --race-id alpine_race_kz --force

    # Parse ALL races with status: new
    python backend/scripts/batch_parse.py --all

    # Show summary of all data in DB
    python backend/scripts/batch_parse.py --summary

    # Show summary for one race
    python backend/scripts/batch_parse.py --summary --race-id alpine_race_kz

    # Import existing JSON files into DB
    python backend/scripts/batch_parse.py --import-json --race-id alpine_race_kz
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.features.races.clax_parser import ClaxParser
from app.features.races.db_models import (
    Race,
    RaceDistance,
    RaceEdition,
    RaceResultDB,
)
from app.features.races.models import RaceEditionData
from app.features.races.name_utils import normalize_name
from app.features.races.stats import format_time

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CATALOG_PATH = PROJECT_ROOT / "content" / "races" / "catalog.yaml"
RESULTS_DIR = PROJECT_ROOT / "content" / "races" / "results"


def load_catalog() -> dict:
    """Load catalog.yaml."""
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_catalog(catalog: dict) -> None:
    """Save catalog.yaml."""
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            catalog, f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )


def save_to_db(db: Session, race_id: str, race_name: str, data: RaceEditionData) -> int:
    """Save parsed race data to database.

    Creates Race (if not exists), RaceEdition, RaceDistances, RaceResults.
    Returns total number of results saved.
    """
    # Upsert Race
    race = db.get(Race, race_id)
    if not race:
        race = Race(id=race_id, name=race_name)
        db.add(race)
        db.flush()

    # Check if edition already exists (for --force re-parse)
    existing = db.execute(
        select(RaceEdition).where(
            RaceEdition.race_id == race_id,
            RaceEdition.year == data.year,
        )
    ).scalar_one_or_none()

    if existing:
        # Delete existing edition and cascade (distances, results)
        db.delete(existing)
        db.flush()

    # Create edition
    edition = RaceEdition(
        race_id=race_id,
        year=data.year,
        date=data.date,
        source_url=data.source_url,
        parsed_at=datetime.now(timezone.utc),
    )
    db.add(edition)
    db.flush()

    total_results = 0
    for dist_data in data.distances:
        distance = RaceDistance(
            edition_id=edition.id,
            name=dist_data.distance_name,
            distance_km=dist_data.distance_km,
            elevation_gain_m=dist_data.elevation_gain_m,
        )
        db.add(distance)
        db.flush()

        for r in dist_data.results:
            result = RaceResultDB(
                distance_id=distance.id,
                name=r.name,
                name_normalized=normalize_name(r.name),
                time_seconds=r.time_seconds,
                place=r.place,
                category=r.category,
                gender=r.gender,
                club=r.club,
                bib=r.bib,
                birth_year=r.birth_year,
                nationality=r.nationality,
                over_time_limit=r.over_time_limit,
            )
            db.add(result)
            total_results += 1

    db.commit()
    return total_results


def parse_race(db: Session, race: dict, force: bool = False, dry_run: bool = False) -> dict:
    """Parse all new editions of a race into DB."""
    race_id = race["id"]
    race_name = race["name"]
    editions = race.get("editions", [])

    stats = {"parsed": 0, "skipped": 0, "errors": 0, "error_details": []}

    to_parse = []
    for edition in editions:
        status = edition.get("status", "new")
        year = edition["year"]
        url = edition.get("url")

        if status in ("no_results", "upcoming"):
            continue
        if status == "parsed" and not force:
            stats["skipped"] += 1
            continue
        if not url:
            continue
        to_parse.append(edition)

    if not to_parse:
        print(f"  {race_name}: nothing to parse")
        return stats

    parser = ClaxParser(filter_distances=False)

    for edition in to_parse:
        year = edition["year"]
        url = edition["url"]

        if dry_run:
            print(f"  [DRY RUN] Would parse {race_name} {year}")
            print(f"            URL: {url}")
            stats["parsed"] += 1
            continue

        try:
            print(f"  Parsing {race_name} {year}...", end=" ", flush=True)
            data = parser.parse_url(url)
            total_results = sum(len(d.results) for d in data.distances)
            total_distances = len(data.distances)

            if total_results == 0:
                print(f"WARNING: 0 results!")
            else:
                print(f"{total_distances} distances, {total_results} results", end=" ", flush=True)

            saved = save_to_db(db, race_id, race_name, data)
            print(f"-> DB ({saved} rows)")
            edition["status"] = "parsed"
            stats["parsed"] += 1

            time.sleep(0.5)

        except Exception as e:
            print(f"ERROR: {e}")
            edition["status"] = "error"
            stats["errors"] += 1
            stats["error_details"].append(f"{race_name} {year}: {e}")

    return stats


def import_json_to_db(db: Session, race: dict) -> dict:
    """Import existing JSON result files into DB."""
    race_id = race["id"]
    race_name = race["name"]

    stats = {"imported": 0, "skipped": 0, "errors": 0}

    # Find JSON files matching this race
    # Try both old naming (alpine_race_YYYY.json) and new (alpine_race_kz_YYYY.json)
    old_prefix = race_id.replace("_kz", "")
    patterns = [f"{race_id}_*.json", f"{old_prefix}_*.json"]

    json_files = []
    for pattern in patterns:
        json_files.extend(RESULTS_DIR.glob(pattern))
    json_files = list(set(json_files))  # deduplicate

    if not json_files:
        print(f"  {race_name}: no JSON files found")
        return stats

    for json_path in sorted(json_files):
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            year = raw["year"]

            # Build RaceEditionData from JSON
            from app.features.races.models import RaceDistanceResults, RaceResult as RaceResultDC

            distances = []
            for d in raw["distances"]:
                results = [
                    RaceResultDC(
                        name=r["name"],
                        name_local=r.get("name_local"),
                        time_seconds=r["time_s"],
                        place=r["place"],
                        category=r.get("category"),
                        gender=r.get("gender"),
                        club=r.get("club"),
                        bib=r.get("bib"),
                        pace=r.get("pace"),
                        birth_year=r.get("birth_year"),
                        nationality=r.get("nationality"),
                        over_time_limit=r.get("over_time_limit", False),
                    )
                    for r in d["results"]
                ]
                distances.append(
                    RaceDistanceResults(
                        distance_name=d["name"],
                        distance_km=d.get("distance_km"),
                        elevation_gain_m=d.get("elevation_gain_m"),
                        results=results,
                    )
                )

            data = RaceEditionData(
                race_name=raw["race_name"],
                year=year,
                date=raw.get("date"),
                source_url=raw.get("source_url"),
                distances=distances,
            )

            total = sum(len(d.results) for d in data.distances)
            print(f"  Importing {json_path.name} ({year}, {total} results)...", end=" ", flush=True)

            saved = save_to_db(db, race_id, race_name, data)
            print(f"-> DB ({saved} rows)")
            stats["imported"] += 1

        except Exception as e:
            print(f"  ERROR importing {json_path.name}: {e}")
            stats["errors"] += 1

    return stats


def show_summary(db: Session, race_id: str | None = None) -> None:
    """Show summary from database."""
    # Get all races or specific one
    query = select(Race)
    if race_id:
        query = query.where(Race.id == race_id)
    query = query.order_by(Race.name)

    races = db.execute(query).scalars().all()

    if not races:
        if race_id:
            print(f"Race not found in DB: {race_id}")
        else:
            print("No races in DB")
        return

    for race in races:
        print(f"\n{'=' * 60}")
        print(f"{race.name} ({race.id})")

        editions = db.execute(
            select(RaceEdition)
            .where(RaceEdition.race_id == race.id)
            .order_by(RaceEdition.year.desc())
        ).scalars().all()

        if not editions:
            print("  No editions in DB")
            continue

        print(f"Editions: {len(editions)}")

        for edition in editions:
            distances = db.execute(
                select(RaceDistance)
                .where(RaceDistance.edition_id == edition.id)
                .order_by(RaceDistance.name)
            ).scalars().all()

            for dist in distances:
                # Get stats
                result = db.execute(
                    select(
                        func.count(RaceResultDB.id),
                        func.min(RaceResultDB.time_seconds),
                        func.max(RaceResultDB.time_seconds),
                    ).where(RaceResultDB.distance_id == dist.id)
                ).one()

                finishers, best_s, worst_s = result
                km = f"{dist.distance_km} km" if dist.distance_km else "? km"
                best = format_time(best_s) if best_s else "?"
                worst = format_time(worst_s) if worst_s else "?"

                print(
                    f"  {edition.year} | {dist.name:.<30s} "
                    f"{km:>8s}  {finishers:>4d} fin  "
                    f"best {best}  worst {worst}"
                )


def main() -> None:
    argp = argparse.ArgumentParser(description="Batch parse CLAX race results into DB")
    argp.add_argument("--race-id", help="Parse only this race")
    argp.add_argument("--all", action="store_true", help="Parse all races with new editions")
    argp.add_argument("--force", action="store_true", help="Re-parse even if already parsed")
    argp.add_argument("--dry-run", action="store_true", help="Show what would be parsed")
    argp.add_argument("--summary", action="store_true", help="Show summary from DB")
    argp.add_argument("--import-json", action="store_true", help="Import existing JSON files into DB")

    args = argp.parse_args()

    if not args.race_id and not args.all and not args.summary:
        argp.error("Specify --race-id <id>, --all, or --summary")

    # Initialize all models so SQLAlchemy can resolve relationships
    init_db()

    db = SessionLocal()

    try:
        if args.summary:
            show_summary(db, args.race_id)
            return

        catalog = load_catalog()

        # Find races to process
        races_to_process = []
        for race in catalog["races"]:
            if args.race_id:
                if race["id"] == args.race_id:
                    races_to_process.append(race)
                    break
            elif args.all:
                races_to_process.append(race)

        if args.race_id and not races_to_process:
            print(f"Race not found: {args.race_id}")
            print(f"Available: {', '.join(r['id'] for r in catalog['races'])}")
            sys.exit(1)

        if args.import_json:
            # Import JSON files
            for race in races_to_process:
                print(f"\n--- {race['name']} ---")
                import_json_to_db(db, race)

            # Show summary
            for race in races_to_process:
                show_summary(db, race["id"])
            return

        # Parse from CLAX
        totals = {"parsed": 0, "skipped": 0, "errors": 0, "error_details": []}

        for race in races_to_process:
            print(f"\n--- {race['name']} ---")
            result = parse_race(db, race, force=args.force, dry_run=args.dry_run)
            for key in ("parsed", "skipped", "errors"):
                totals[key] += result[key]
            totals["error_details"].extend(result["error_details"])

        # Save updated catalog (with new statuses)
        if not args.dry_run and totals["parsed"] > 0:
            save_catalog(catalog)
            print(f"\nUpdated {CATALOG_PATH}")

        # Summary
        print(f"\n{'=' * 40}")
        print(f"Parsed: {totals['parsed']}")
        print(f"Skipped: {totals['skipped']}")
        print(f"Errors: {totals['errors']}")
        if totals["error_details"]:
            print("\nError details:")
            for err in totals["error_details"]:
                print(f"  - {err}")

        # Show DB summary for parsed race
        if not args.dry_run and totals["parsed"] > 0 and args.race_id:
            print()
            show_summary(db, args.race_id)

    finally:
        db.close()


if __name__ == "__main__":
    main()
