#!/usr/bin/env python3
"""CLI script for parsing CLAX race results and viewing statistics.

Usage:
    # Parse from URL and save to JSON
    python backend/scripts/parse_race.py \
        --url "https://live.myrace.info/?f=bases/kz/2025/alpinrace2025/alpinrace2025.clax" \
        --save content/races/results/alpine_race_2025.json

    # Search by name in saved JSON
    python backend/scripts/parse_race.py \
        --file content/races/results/alpine_race_2025.json \
        --search "Renat"

    # Show statistics for a distance
    python backend/scripts/parse_race.py \
        --file content/races/results/alpine_race_2025.json \
        --stats --distance "Skyrunning"

    # Parse and immediately show stats + search
    python backend/scripts/parse_race.py \
        --url "https://live.myrace.info/?f=bases/kz/2025/alpinrace2025/alpinrace2025.clax" \
        --save content/races/results/alpine_race_2025.json \
        --stats --search "Renat"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.features.races.clax_parser import ClaxParser
from app.features.races.models import (
    RaceDistanceResults,
    RaceEditionData,
    RaceResult,
    RaceStats,
)
from app.features.races.stats import (
    calculate_stats,
    format_time,
    get_percentile,
    search_by_name,
)


def save_to_json(data: RaceEditionData, path: Path) -> None:
    """Save RaceEditionData to JSON with stats included."""
    output = {
        "race_name": data.race_name,
        "year": data.year,
        "date": data.date,
        "source_url": data.source_url,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "distances": [],
    }

    for d in data.distances:
        stats = calculate_stats(d.results)
        dist_data = {
            "name": d.distance_name,
            "distance_km": d.distance_km,
            "elevation_gain_m": d.elevation_gain_m,
            "finishers": stats.finishers,
            "stats": {
                "best_time_s": stats.best_time_s,
                "worst_time_s": stats.worst_time_s,
                "median_s": stats.median_time_s,
                "p25_s": stats.p25_time_s,
                "p75_s": stats.p75_time_s,
            },
            "results": [
                {
                    "name": r.name,
                    "name_local": r.name_local,
                    "time_s": r.time_seconds,
                    "place": r.place,
                    "category": r.category,
                    "gender": r.gender,
                    "club": r.club,
                    "bib": r.bib,
                    "pace": r.pace,
                    "birth_year": r.birth_year,
                    "nationality": r.nationality,
                    "over_time_limit": r.over_time_limit,
                }
                for r in d.results
            ],
        }
        output["distances"].append(dist_data)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {path} ({sum(len(d.results) for d in data.distances)} results)")


def load_from_json(path: Path) -> RaceEditionData:
    """Load RaceEditionData from JSON."""
    raw = json.loads(path.read_text(encoding="utf-8"))

    distances = []
    for d in raw["distances"]:
        results = [
            RaceResult(
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

    return RaceEditionData(
        race_name=raw["race_name"],
        year=raw["year"],
        date=raw.get("date"),
        source_url=raw.get("source_url"),
        distances=distances,
    )


def print_stats(data: RaceEditionData, distance_name: str | None = None) -> None:
    """Print statistics for each (or specified) distance."""
    for d in data.distances:
        if distance_name and d.distance_name.lower() != distance_name.lower():
            continue

        stats = calculate_stats(d.results)
        winner = d.results[0].name if d.results else "—"

        print(f"\n=== {data.race_name} {data.year} — {d.distance_name} ===")
        if d.distance_km:
            print(f"{d.distance_km} km", end="")
            if d.elevation_gain_m:
                print(f", +{d.elevation_gain_m}m", end="")
            print()

        print(f"Finishers: {stats.finishers}")
        print(f"Best:      {format_time(stats.best_time_s)} ({winner})")
        print(f"Median:    {format_time(stats.median_time_s)}")
        print(f"P25:       {format_time(stats.p25_time_s)}")
        print(f"P75:       {format_time(stats.p75_time_s)}")
        print(f"Worst:     {format_time(stats.worst_time_s)}")

        if stats.time_buckets:
            print(f"\nDistribution:")
            max_count = max(b.count for b in stats.time_buckets)
            for b in stats.time_buckets:
                bar_len = int(b.count / max_count * 15) if max_count else 0
                bar = "\u2588" * bar_len + "\u2591" * (15 - bar_len)
                print(f"  {b.label:>22s}  {bar} {b.count:4d} ({b.percent:4.1f}%)")


def print_search(
    data: RaceEditionData, query: str, distance_name: str | None = None
) -> None:
    """Search for a name across distances and print results."""
    print(f'\nSearch "{query}":')
    found_any = False

    for d in data.distances:
        if distance_name and d.distance_name.lower() != distance_name.lower():
            continue

        found = search_by_name(d.results, query)
        for r in found:
            found_any = True
            pct = get_percentile(d.results, r.time_seconds)
            club_str = f"  {r.club}" if r.club else ""
            print(
                f"  [{d.distance_name}] #{r.place}  {r.name}  "
                f"{format_time(r.time_seconds)}  {r.category or ''}{club_str}  "
                f"(top-{pct}%)"
            )

    if not found_any:
        print(f'  No results for "{query}"')


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and view CLAX race results")
    parser.add_argument("--url", help="CLAX URL to parse (myrace.info)")
    parser.add_argument("--file", help="Load from saved JSON file")
    parser.add_argument("--save", help="Save parsed results to JSON file")
    parser.add_argument("--search", help="Search for participant by name")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--distance", help="Filter by distance name")
    parser.add_argument(
        "--all-distances",
        action="store_true",
        help="Parse all distances (not just Skyrunning)",
    )

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("Either --url or --file is required")

    # Load data
    if args.url:
        print(f"Parsing {args.url}...")
        clax = ClaxParser(filter_distances=not args.all_distances)
        data = clax.parse_url(args.url)
        print(
            f"Parsed: {data.race_name} {data.year} "
            f"({len(data.distances)} distances, "
            f"{sum(len(d.results) for d in data.distances)} results)"
        )
    else:
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)
        data = load_from_json(path)

    # Save if requested
    if args.save:
        save_to_json(data, Path(args.save))

    # Show stats if requested (or default when parsing)
    if args.stats or (args.url and not args.save and not args.search):
        print_stats(data, args.distance)

    # Search if requested
    if args.search:
        print_search(data, args.search, args.distance)


if __name__ == "__main__":
    main()
