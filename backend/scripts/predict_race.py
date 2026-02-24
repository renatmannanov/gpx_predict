#!/usr/bin/env python3
"""CLI script for race time prediction and comparison with past results.

Usage:
    # Predict by flat pace (trail run mode)
    python backend/scripts/predict_race.py \
        --race alpine_race --distance skyrunning --flat-pace 5:30

    # Predict in hiking mode
    python backend/scripts/predict_race.py \
        --race alpine_race --distance skyrunning --flat-pace 6:00 --mode hiking

    # With name search in past results
    python backend/scripts/predict_race.py \
        --race alpine_race --distance skyrunning --flat-pace 5:30 \
        --search-name "Mannanov"

    # Just show stats + search (no prediction, no GPX needed)
    python backend/scripts/predict_race.py \
        --race alpine_race --distance skyrunning \
        --search-name "Mannanov" --stats-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import CONTENT_DIR
from app.features.races.catalog import RaceCatalog, find_distance_results
from app.features.races.matching import find_across_years
from app.features.races.stats import calculate_stats, format_time, get_percentile


def parse_pace(pace_str: str) -> float:
    """Parse pace string to float min/km. '5:30' → 5.5, '6' → 6.0"""
    if ":" in pace_str:
        parts = pace_str.split(":")
        return int(parts[0]) + int(parts[1]) / 60
    return float(pace_str)


def print_race_header(catalog: RaceCatalog, race_id: str, distance_id: str) -> None:
    """Print race info header."""
    race = catalog.get_race(race_id)
    dist = catalog.get_distance(race_id, distance_id)
    if not race or not dist:
        return

    grade_icons = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "orange": "\U0001f7e0", "red": "\U0001f534"}
    grade_labels = {"green": "Easy", "yellow": "Moderate", "orange": "Hard", "red": "Expert"}
    grade_icon = grade_icons.get(dist.grade or "", "")
    grade_label = grade_labels.get(dist.grade or "", "")

    print(f"\n=== {race.name} — {dist.name} ===")
    parts = []
    if dist.distance_km:
        parts.append(f"{dist.distance_km} km")
    if dist.elevation_gain_m:
        parts.append(f"+{dist.elevation_gain_m}m")
    if race.location:
        parts.append(race.location)
    if dist.start_altitude_m and dist.finish_altitude_m:
        parts.append(f"({dist.start_altitude_m}m \u2192 {dist.finish_altitude_m}m)")
    if grade_icon:
        parts.append(f"{grade_icon} {grade_label}")
    if parts:
        print(" | ".join(parts))


def print_prediction(prediction) -> None:
    """Print prediction results."""
    print(f"\n--- Prediction ---")
    print(f"Method: {prediction.method}")
    print(f"Pace:   {prediction.flat_pace_used:.1f} min/km")
    print(f"Time:   {format_time(prediction.predicted_time_s)}")

    if prediction.all_methods:
        print(f"\nAll methods:")
        for method, time_s in sorted(prediction.all_methods.items(), key=lambda x: x[1]):
            marker = " \u2190" if time_s == prediction.predicted_time_s else ""
            print(f"  {method:40s} {format_time(time_s)}{marker}")


def print_comparison(prediction) -> None:
    """Print comparison with past results."""
    if not prediction.stats:
        return

    stats = prediction.stats
    print(f"\n--- vs {prediction.comparison_year} results ---")
    print(
        f"{stats.finishers} finishers | "
        f"Best: {format_time(stats.best_time_s)} | "
        f"Median: {format_time(stats.median_time_s)}"
    )

    if prediction.percentile is not None:
        print(
            f"\nYour {format_time(prediction.predicted_time_s)} \u2192 "
            f"top-{prediction.percentile}% "
            f"(~#{prediction.estimated_place} of {stats.finishers})"
        )

    if stats.time_buckets:
        print(f"\nDistribution:")
        max_count = max(b.count for b in stats.time_buckets) or 1
        for b in stats.time_buckets:
            bar_len = int(b.count / max_count * 15)
            bar = "\u2588" * bar_len + "\u2591" * (15 - bar_len)
            # Mark the bucket where prediction falls
            in_bucket = b.min_s <= prediction.predicted_time_s < b.max_s
            # Last bucket: include max
            if b == stats.time_buckets[-1] and prediction.predicted_time_s >= b.min_s:
                in_bucket = True
            marker = "  \u2190 YOU" if in_bucket else ""
            print(f"  {b.label:>22s}  {bar} {b.count:4d} ({b.percent:4.1f}%){marker}")


def print_search_results(
    catalog: RaceCatalog, race_id: str, distance_id: str, name: str
) -> None:
    """Print user's results across all years."""
    results = find_across_years(catalog, race_id, distance_id, name)
    if not results:
        print(f'\nNo results years available')
        return

    print(f'\n--- History for "{name}" ---')
    found_any = False
    prev_time = None

    for year, r in sorted(results.items()):
        if r:
            found_any = True
            # Get percentile
            data = catalog.load_results(race_id, year)
            dist_info = catalog.get_distance(race_id, distance_id)
            dist_results = find_distance_results(data, dist_info) if data else None
            pct = get_percentile(dist_results.results, r.time_seconds) if dist_results else None

            pct_str = f" (top-{pct}%)" if pct is not None else ""
            diff_str = ""
            if prev_time is not None:
                diff = r.time_seconds - prev_time
                sign = "+" if diff > 0 else ""
                emoji = "\U0001f525" if diff < 0 else ""
                diff_str = f"  [{sign}{format_time(abs(diff))} {emoji}]"

            print(
                f"  {year}: #{r.place}  {r.name}  "
                f"{format_time(r.time_seconds)}  {r.category or ''}{pct_str}{diff_str}"
            )
            prev_time = r.time_seconds
        else:
            print(f"  {year}: --")

    if not found_any:
        print(f'  No results found for "{name}"')


def print_stats_only(catalog: RaceCatalog, race_id: str, distance_id: str) -> None:
    """Print stats for latest year."""
    latest = catalog.get_latest_results_path(race_id)
    if not latest:
        print("No results available")
        return

    year, _ = latest
    data = catalog.load_results(race_id, year)
    dist_info = catalog.get_distance(race_id, distance_id)
    dist_results = find_distance_results(data, dist_info) if data else None

    if not dist_results or not dist_results.results:
        print(f"No results for this distance in {year}")
        return

    stats = calculate_stats(dist_results.results)
    print(f"\n--- {year} Statistics ---")
    print(f"Finishers: {stats.finishers}")
    print(f"Best:      {format_time(stats.best_time_s)} ({dist_results.results[0].name})")
    print(f"Median:    {format_time(stats.median_time_s)}")
    print(f"P25:       {format_time(stats.p25_time_s)}")
    print(f"P75:       {format_time(stats.p75_time_s)}")
    print(f"Worst:     {format_time(stats.worst_time_s)}")

    if stats.time_buckets:
        print(f"\nDistribution:")
        max_count = max(b.count for b in stats.time_buckets) or 1
        for b in stats.time_buckets:
            bar_len = int(b.count / max_count * 15)
            bar = "\u2588" * bar_len + "\u2591" * (15 - bar_len)
            print(f"  {b.label:>22s}  {bar} {b.count:4d} ({b.percent:4.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Race time prediction")
    parser.add_argument("--race", required=True, help="Race ID (e.g. alpine_race)")
    parser.add_argument("--distance", required=True, help="Distance ID (e.g. skyrunning)")
    parser.add_argument("--flat-pace", help="Flat pace in min/km (e.g. 5:30 or 5.5)")
    parser.add_argument(
        "--mode",
        default="trail_run",
        choices=["trail_run", "hiking"],
        help="Prediction mode",
    )
    parser.add_argument("--search-name", help="Search for name in past results")
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show only stats, no prediction",
    )

    args = parser.parse_args()
    catalog = RaceCatalog(CONTENT_DIR)

    # Validate race/distance exist
    race = catalog.get_race(args.race)
    if not race:
        print(f"Race not found: {args.race}")
        print(f"Available: {[r.id for r in catalog.races]}")
        sys.exit(1)

    dist = catalog.get_distance(args.race, args.distance)
    if not dist:
        print(f"Distance not found: {args.distance}")
        print(f"Available: {[d.id for d in race.distances]}")
        sys.exit(1)

    # Header
    print_race_header(catalog, args.race, args.distance)

    # Stats only mode
    if args.stats_only:
        print_stats_only(catalog, args.race, args.distance)
        if args.search_name:
            print_search_results(catalog, args.race, args.distance, args.search_name)
        return

    # Prediction mode — requires flat-pace and GPX
    if args.flat_pace:
        flat_pace = parse_pace(args.flat_pace)
        gpx_path = catalog.get_gpx_path(args.race, args.distance)

        if not gpx_path:
            print(f"\nGPX file not available for {args.race}/{args.distance}")
            print(f"Expected: content/races/gpx/{dist.gpx_file}")
            print("Showing stats instead...")
            print_stats_only(catalog, args.race, args.distance)
        else:
            # Import heavy dependencies only when needed
            from app.features.races.service import RaceService

            service = RaceService(catalog)
            prediction = service.predict_by_pace(
                args.race, args.distance, flat_pace, mode=args.mode
            )
            print_prediction(prediction)
            print_comparison(prediction)

    # Search
    if args.search_name:
        print_search_results(catalog, args.race, args.distance, args.search_name)


if __name__ == "__main__":
    main()
