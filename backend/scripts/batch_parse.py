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

# Windows consoles default to cp1252 and crash printing Cyrillic names
# (UnicodeEncodeError). Force UTF-8 so summary output of AM races doesn't abort.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.features.races.am_parser import AlmatyMarathonParser
from app.features.races.clax_parser import ClaxParser
from app.features.races.db_models import (
    Club,
    ClubNameAlias,
    Race,
    RaceDistance,
    RaceEdition,
    RaceResultDB,
    Runner,
    RunnerNameAlias,
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


def _resolve_club(db: Session, club_text: str) -> tuple[int, str] | None:
    """Resolve club text to (club_id, canonical_name).

    Lookup order:
    1. clubs.name_normalized (exact match)
    2. club_name_aliases.name_normalized (alias → canonical club)
    3. Create new club if not found

    Returns (club_id, canonical_club_name) or None if club_text is empty.
    """
    if not club_text or not club_text.strip():
        return None

    club_norm = club_text.strip().lower()

    # 1. Direct match in clubs
    club = db.execute(
        select(Club).where(Club.name_normalized == club_norm)
    ).scalar_one_or_none()
    if club:
        return club.id, club.name

    # 2. Match via alias → get canonical club
    alias = db.execute(
        select(ClubNameAlias).where(ClubNameAlias.name_normalized == club_norm)
    ).scalar_one_or_none()
    if alias:
        club = db.get(Club, alias.club_id)
        if club:
            return club.id, club.name

    # 3. Not found — create new club
    club = Club(
        name=club_text.strip(),
        name_normalized=club_norm,
        runners_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(club)
    db.flush()
    return club.id, club.name


def _fuzzy_match_runner(
    db: Session, name_normalized: str, birth_year: int | None,
) -> tuple[Runner | None, list[str]]:
    """Find existing runner by fuzzy name match + birth_year.

    NOTE: No longer called at import — matching there is strict on
    (name_normalized, birth_year, source). Reserved for the future
    merge-candidates API (manual merge UI).

    Uses pg_trgm similarity to catch transliteration variants like
    Baikashev/Bajkashev, Anastasiya/Anastassiya, Assel/Asel.

    Returns (runner, warnings):
    - similarity > 0.85 + same birth_year → auto-merge (runner returned)
    - similarity 0.7-0.85 + same birth_year → warning for manual review
    - Only matches when birth_year is available and identical — this prevents
      false merges (e.g. Pavlenko Alexandr 1988 vs Pavlenko Alexandra 1987).
    """
    if not birth_year or not name_normalized:
        return None, []

    # Look for candidates with similarity > 0.7 and same birth_year
    rows = db.execute(
        select(
            Runner,
            sa.func.similarity(Runner.name_normalized, name_normalized).label("sim"),
        ).where(
            sa.func.similarity(Runner.name_normalized, name_normalized) > 0.7,
            Runner.birth_year == birth_year,
        ).order_by(
            sa.literal_column("sim").desc()
        ).limit(3)
    ).all()

    if not rows:
        return None, []

    best_runner, best_sim = rows[0]

    # High confidence — auto-merge
    if best_sim > 0.85:
        return best_runner, []

    # Suspect zone — warn for manual review
    warnings = []
    for runner, sim in rows:
        warnings.append(
            f"  [!] Possible dupe: \"{name_normalized}\" (new, by={birth_year}) "
            f"~ \"{runner.name_normalized}\" (id={runner.id}, \"{runner.name}\", "
            f"sim={sim:.2f})"
        )
    return None, warnings


def save_to_db(
    db: Session, race_id: str, race_name: str, data: RaceEditionData, source: str = "clax",
) -> tuple[int, list[str]]:
    """Save parsed race data to database.

    Creates Race (if not exists), RaceEdition, RaceDistances, RaceResults.
    Returns (total_results_saved, suspect_dupe_warnings).

    NOTE: suspect_dupe_warnings is now always empty — fuzzy matching was removed
    from import (namesakes go to separate runners by design). The second tuple
    element is kept for backward-compatible call sites.
    """
    suspect_warnings: list[str] = []
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
    # Track (runner_id, alias_norm) added during THIS edition import. A DB select
    # only sees flushed rows, so two results of the same runner+name within one
    # import would both pass the "not exists" check and insert a duplicate alias,
    # violating ix_runner_aliases_unique. This set dedupes pending aliases.
    seen_aliases: set[tuple[int, str]] = set()
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
            name_norm = normalize_name(r.name)

            # Get or create runner.
            # Matching is strict: (name_normalized, birth_year, source).
            # - source isolates AM runners from athletex runners (never merged).
            # - birth_year IS NULL → always a new runner (fragment); we do not guess.
            # - No fuzzy matching at import — namesakes go to separate runners on
            #   purpose; fuzzy only added false merges. (_fuzzy_match_runner is kept,
            #   unused, reserved for the future merge-candidates API.)
            runner_source = "am" if source == "almaty-marathon" else "athletex"
            runner_id = None
            if name_norm:
                runner = None
                if r.birth_year is not None:
                    runner = db.execute(
                        select(Runner).where(
                            Runner.name_normalized == name_norm,
                            Runner.birth_year == r.birth_year,
                            Runner.source == runner_source,
                        )
                    ).scalar_one_or_none()

                if not runner:
                    # Resolve club via aliases
                    club_id = None
                    club_canonical = r.club
                    resolved = _resolve_club(db, r.club)
                    if resolved:
                        club_id, club_canonical = resolved

                    runner = Runner(
                        name=r.name,
                        name_normalized=name_norm,
                        source=runner_source,
                        club=club_canonical,
                        club_id=club_id,
                        gender=r.gender,
                        category=r.category,
                        birth_year=r.birth_year,
                        races_count=0,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    db.add(runner)
                    db.flush()
                else:
                    # Update runner with latest data
                    runner.name = r.name
                    if r.club:
                        resolved = _resolve_club(db, r.club)
                        if resolved:
                            runner.club_id = resolved[0]
                            runner.club = resolved[1]  # canonical name
                    if r.gender:
                        runner.gender = r.gender
                    if r.category:
                        runner.category = r.category
                    if r.birth_year:
                        runner.birth_year = r.birth_year
                    runner.updated_at = datetime.now(timezone.utc)

                runner_id = runner.id

                # Save name alias
                if runner and r.name:
                    alias_norm = normalize_name(r.name)
                    alias_key = (runner.id, alias_norm)
                    if alias_key not in seen_aliases:
                        existing_alias = db.execute(
                            select(RunnerNameAlias).where(
                                RunnerNameAlias.runner_id == runner.id,
                                RunnerNameAlias.name_normalized == alias_norm,
                            )
                        ).scalar_one_or_none()
                        if not existing_alias:
                            db.add(RunnerNameAlias(
                                runner_id=runner.id,
                                name=r.name,
                                name_normalized=alias_norm,
                                source=source,
                            ))
                        seen_aliases.add(alias_key)

            result = RaceResultDB(
                distance_id=distance.id,
                runner_id=runner_id,
                name=r.name,
                name_normalized=name_norm,
                time_seconds=r.time_seconds,
                place=r.place,
                category=r.category,
                gender=r.gender,
                club=r.club,
                city=r.city,
                bib=r.bib,
                birth_year=r.birth_year,
                nationality=r.nationality,
                over_time_limit=r.over_time_limit,
                status=r.status,
            )
            db.add(result)
            total_results += 1

    db.commit()

    # Update runners_count for runners and clubs after commit
    _update_runner_counts(db)
    _update_club_counts(db)

    return total_results, suspect_warnings


def _update_runner_counts(db: Session) -> None:
    """Update races_count cache for all runners."""
    db.execute(sa.text("""
        UPDATE runners r
        SET races_count = (
            SELECT COUNT(DISTINCT rd.edition_id)
            FROM race_results rr
            JOIN race_distances rd ON rr.distance_id = rd.id
            WHERE rr.runner_id = r.id
        )
    """))
    db.commit()


def _update_club_counts(db: Session) -> None:
    """Update runners_count cache for all clubs."""
    db.execute(sa.text("""
        UPDATE clubs c
        SET runners_count = (
            SELECT COUNT(*)
            FROM runners r
            WHERE r.club_id = c.id
        )
    """))
    db.commit()


def parse_race(db: Session, race: dict, force: bool = False, dry_run: bool = False) -> dict:
    """Parse all new editions of a race into DB."""
    race_id = race["id"]
    race_name = race["name"]
    source = race.get("source", "clax")  # "clax" or "almaty-marathon"
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

    # Sort chronologically (oldest first) so runner.club ends up from latest race
    to_parse.sort(key=lambda e: e["year"])

    for edition in to_parse:
        year = edition["year"]
        url = edition["url"]

        if dry_run:
            print(f"  [DRY RUN] Would parse {race_name} {year} (source: {source})")
            print(f"            URL: {url}")
            stats["parsed"] += 1
            continue

        try:
            print(f"  Parsing {race_name} {year} ({source})...", end=" ", flush=True)

            if source == "almaty-marathon":
                with AlmatyMarathonParser(delay=0.3) as am_parser:
                    data = am_parser.parse_race(url)
            else:
                clax_parser = ClaxParser(filter_distances=False)
                data = clax_parser.parse_url(url)

            total_results = sum(len(d.results) for d in data.distances)
            total_distances = len(data.distances)

            if total_results == 0:
                print(f"WARNING: 0 results!")
            else:
                print(f"{total_distances} distances, {total_results} results", end=" ", flush=True)

            saved, warnings = save_to_db(db, race_id, race_name, data, source=source)
            print(f"-> DB ({saved} rows)")
            if warnings:
                for w in warnings:
                    print(w)
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

            source = race.get("source", "clax")
            saved, warnings = save_to_db(db, race_id, race_name, data, source=source)
            print(f"-> DB ({saved} rows)")
            if warnings:
                for w in warnings:
                    print(w)
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
