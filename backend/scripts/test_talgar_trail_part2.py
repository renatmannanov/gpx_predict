#!/usr/bin/env python
"""
Test script comparing Part 1 vs Part 2 features on Talgar Trail.

Part 1 (baseline):
- GAPCalculator (Strava/Minetti modes)

Part 2 (enhanced):
- HikeRunThresholdService (run/walk detection)
- RunnerFatigueService (fatigue with downhill penalty)
- Combined prediction

Compares results with real race data:
- Talgar Trail 25K: Winner 3:18, Top 10 ~3:56, Median ~5:00
- Irbis Trail (same section): Elite 2:47-2:50
"""

import sys
import os

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import gpxpy

from app.models.gpx import GPXFile
from app.services.calculators.segmenter import RouteSegmenter
from app.services.calculators.trail_run import (
    GAPCalculator, GAPMode,
    HikeRunThresholdService, MovementMode,
    RunnerFatigueService,
)
from app.services.calculators.tobler import ToblerCalculator
from app.services.calculators.comparison import ComparisonService


def format_time(hours: float) -> str:
    """Format hours as 'Xh Ymin'."""
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


def format_pace(min_km: float) -> str:
    """Format pace as 'X:YY/km'."""
    mins = int(min_km)
    secs = int((min_km - mins) * 60)
    return f"{mins}:{secs:02d}/km"


def load_gpx_from_db(db: Session, search_term: str = "talgar"):
    """Load GPX file from database by name search."""
    gpx_file = db.query(GPXFile).filter(
        GPXFile.name.ilike(f"%{search_term}%")
    ).first()

    if not gpx_file:
        gpx_file = db.query(GPXFile).filter(
            GPXFile.filename.ilike(f"%{search_term}%")
        ).first()

    return gpx_file


def parse_gpx_content(gpx_content: bytes) -> list:
    """Parse GPX content and extract points."""
    gpx = gpxpy.parse(gpx_content.decode('utf-8'))
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.elevation is not None:
                    points.append((point.latitude, point.longitude, point.elevation))
    for route in gpx.routes:
        for point in route.points:
            if point.elevation is not None:
                points.append((point.latitude, point.longitude, point.elevation))
    return points


def calculate_part1_baseline(segments, base_pace: float) -> dict:
    """Part 1: Basic GAP calculation without enhancements."""
    gap_strava = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.STRAVA)
    gap_minetti = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.MINETTI)

    total_strava, _ = gap_strava.calculate_route(segments)
    total_minetti, _ = gap_minetti.calculate_route(segments)

    return {
        "strava_gap": total_strava,
        "minetti_gap": total_minetti,
    }


def calculate_part2_with_threshold(segments, base_pace: float, dynamic: bool = False) -> dict:
    """Part 2: GAP with hike/run threshold detection."""
    threshold_service = HikeRunThresholdService(
        uphill_threshold=25.0,
        dynamic=dynamic
    )

    gap_run = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.STRAVA)
    tobler_hike = ToblerCalculator()

    total_time = 0.0
    run_time = 0.0
    hike_time = 0.0
    decisions = threshold_service.process_route(segments)

    for decision in decisions:
        segment = decision.segment
        if decision.mode == MovementMode.RUN:
            result = gap_run.calculate_segment(segment)
            run_time += result.time_hours
        else:
            result = tobler_hike.calculate_segment(segment, profile_multiplier=1.0)
            hike_time += result.time_hours
        total_time += result.time_hours

    summary = threshold_service.get_summary(decisions)

    return {
        "total_time": total_time,
        "run_time": run_time,
        "hike_time": hike_time,
        "run_segments": summary["run_segments"],
        "hike_segments": summary["hike_segments"],
        "run_percent": summary["run_percent"],
    }


def calculate_part2_with_fatigue(segments, base_pace: float, distance_km: float) -> dict:
    """Part 2: GAP with runner fatigue model."""
    gap = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.STRAVA)
    fatigue = RunnerFatigueService.create_enabled(distance_km=distance_km)

    total_time = 0.0
    elapsed_hours = 0.0
    fatigue_added = 0.0

    for segment in segments:
        # Base time from GAP
        result = gap.calculate_segment(segment)
        base_time = result.time_hours

        # Apply fatigue
        adjusted_time, multiplier = fatigue.apply_to_segment(
            base_time,
            elapsed_hours,
            segment.gradient_percent
        )

        fatigue_added += (adjusted_time - base_time)
        total_time += adjusted_time
        elapsed_hours += adjusted_time

    return {
        "total_time": total_time,
        "fatigue_added": fatigue_added,
        "fatigue_info": fatigue.get_info(),
    }


def calculate_part2_full(segments, base_pace: float, distance_km: float, dynamic_threshold: bool = False) -> dict:
    """Part 2: Full calculation with threshold + fatigue."""
    threshold_service = HikeRunThresholdService(
        uphill_threshold=25.0,
        dynamic=dynamic_threshold
    )
    gap_run = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.STRAVA)
    tobler_hike = ToblerCalculator()
    fatigue = RunnerFatigueService.create_enabled(distance_km=distance_km)

    total_time = 0.0
    run_time = 0.0
    hike_time = 0.0
    elapsed_hours = 0.0
    fatigue_added = 0.0

    decisions = threshold_service.process_route(segments, total_distance_km=distance_km)

    for decision in decisions:
        segment = decision.segment

        # Calculate base time based on mode
        if decision.mode == MovementMode.RUN:
            result = gap_run.calculate_segment(segment)
            run_time += result.time_hours
        else:
            result = tobler_hike.calculate_segment(segment, profile_multiplier=1.0)
            hike_time += result.time_hours

        base_time = result.time_hours

        # Apply fatigue
        adjusted_time, multiplier = fatigue.apply_to_segment(
            base_time,
            elapsed_hours,
            segment.gradient_percent
        )

        fatigue_added += (adjusted_time - base_time)
        total_time += adjusted_time
        elapsed_hours += adjusted_time

    summary = threshold_service.get_summary(decisions)

    return {
        "total_time": total_time,
        "run_time": run_time,
        "hike_time": hike_time,
        "fatigue_added": fatigue_added,
        "run_segments": summary["run_segments"],
        "hike_segments": summary["hike_segments"],
        "run_percent": summary["run_percent"],
    }


def main():
    print("=" * 70)
    print("Talgar Trail 25K: Part 1 vs Part 2 Comparison")
    print("=" * 70)
    print()

    # Connect to database
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return

    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        # Load Talgar Trail
        gpx_file = load_gpx_from_db(db, "talgar")
        if not gpx_file or not gpx_file.gpx_content:
            print("Talgar Trail GPX not found!")
            return

        print(f"Track: {gpx_file.name}")
        print(f"Distance: {gpx_file.distance_km:.2f} km")
        print(f"Elevation: +{gpx_file.elevation_gain_m:.0f}m" if gpx_file.elevation_gain_m else "")
        print()

        # Parse and segment
        points = parse_gpx_content(gpx_file.gpx_content)
        segments = RouteSegmenter.segment_route(points)

        total_distance = sum(s.distance_km for s in segments)
        total_ascent = sum(s.elevation_gain_m for s in segments)
        total_descent = sum(s.elevation_loss_m for s in segments)

        print(f"Segments: {len(segments)}")
        print(f"Total distance: {total_distance:.2f} km")
        print(f"Total ascent: +{total_ascent:.0f} m")
        print(f"Total descent: -{total_descent:.0f} m")
        print()

        # Real race reference data
        print("=" * 70)
        print("REAL RACE DATA (Reference)")
        print("=" * 70)
        print()
        print("Talgar Trail 25K (full race):")
        print("  Winner:     3:18:16 (Iyemberdiyev Diyas)")
        print("  Top 3:      3:36-3:41")
        print("  Top 10:     ~3:56")
        print("  Median:     ~5:00")
        print()
        print("Irbis Trail (elite on same section):")
        print("  Top 1:      2:47:17 (Vizuete Castro Pedro)")
        print("  Top 2:      2:50:24 (Baikashev Shyngys)")
        print()

        # Test different runner profiles
        profiles = [
            ("Elite", 5.0, "Irbis elite: 2:47-2:50"),
            ("Fast", 6.0, "Talgar winner: 3:18"),
            ("Moderate", 7.0, "Top 5-10: 3:47-3:56"),
            ("Recreational", 8.0, "~4:20-4:40"),
        ]

        print("=" * 70)
        print("PART 1 vs PART 2 COMPARISON")
        print("=" * 70)
        print()

        for profile_name, base_pace, reference in profiles:
            print(f"--- {profile_name} Runner (base pace: {format_pace(base_pace)}) ---")
            print(f"    Reference: {reference}")
            print()

            # Part 1: Baseline
            p1 = calculate_part1_baseline(segments, base_pace)

            # Part 2: With threshold only
            p2_threshold = calculate_part2_with_threshold(segments, base_pace)

            # Part 2: With fatigue only
            p2_fatigue = calculate_part2_with_fatigue(segments, base_pace, total_distance)

            # Part 2: Full (threshold + fatigue)
            p2_full = calculate_part2_full(segments, base_pace, total_distance)

            # Part 2: Full with dynamic threshold
            p2_full_dynamic = calculate_part2_full(segments, base_pace, total_distance, dynamic_threshold=True)

            print(f"  PART 1 (baseline):")
            print(f"    Strava GAP:           {format_time(p1['strava_gap'])}")
            print(f"    Minetti GAP:          {format_time(p1['minetti_gap'])}")
            print()

            print(f"  PART 2 (with threshold, 25%):")
            print(f"    Total:                {format_time(p2_threshold['total_time'])}")
            print(f"    Running:              {format_time(p2_threshold['run_time'])} ({p2_threshold['run_percent']:.0f}%)")
            print(f"    Hiking:               {format_time(p2_threshold['hike_time'])}")
            print(f"    Segments:             {p2_threshold['run_segments']} run / {p2_threshold['hike_segments']} hike")
            print()

            print(f"  PART 2 (with fatigue):")
            print(f"    Total:                {format_time(p2_fatigue['total_time'])}")
            print(f"    Fatigue added:        +{format_time(p2_fatigue['fatigue_added'])}")
            print()

            print(f"  PART 2 FULL (threshold + fatigue):")
            print(f"    Total:                {format_time(p2_full['total_time'])}")
            print(f"    Running:              {format_time(p2_full['run_time'])}")
            print(f"    Hiking:               {format_time(p2_full['hike_time'])}")
            print(f"    Fatigue added:        +{format_time(p2_full['fatigue_added'])}")
            print()

            print(f"  PART 2 FULL (dynamic threshold):")
            print(f"    Total:                {format_time(p2_full_dynamic['total_time'])}")
            print(f"    Running:              {format_time(p2_full_dynamic['run_time'])} ({p2_full_dynamic['run_percent']:.0f}%)")
            print(f"    Hiking:               {format_time(p2_full_dynamic['hike_time'])}")
            print(f"    Fatigue added:        +{format_time(p2_full_dynamic['fatigue_added'])}")
            print()

            # Comparison summary
            diff_threshold = p2_threshold['total_time'] - p1['strava_gap']
            diff_fatigue = p2_fatigue['total_time'] - p1['strava_gap']
            diff_full = p2_full['total_time'] - p1['strava_gap']

            print(f"  COMPARISON vs Part 1 Strava GAP:")
            print(f"    + Threshold only:     {'+' if diff_threshold > 0 else ''}{format_time(abs(diff_threshold))}")
            print(f"    + Fatigue only:       +{format_time(diff_fatigue)}")
            print(f"    + Full Part 2:        +{format_time(diff_full)}")
            print()
            print()

        # Summary table
        print("=" * 70)
        print("SUMMARY: Best Predictions vs Real Results")
        print("=" * 70)
        print()
        print("| Runner     | Real Time | Part 1 GAP | Part 2 Full | Error   |")
        print("|------------|-----------|------------|-------------|---------|")

        summary_data = [
            ("Elite", "2:47-2:50", 5.0),
            ("Fast", "3:18", 6.0),
            ("Moderate", "3:47-3:56", 7.0),
        ]

        for name, real, pace in summary_data:
            p1 = calculate_part1_baseline(segments, pace)
            p2 = calculate_part2_full(segments, pace, total_distance)

            p1_time = format_time(p1['strava_gap'])
            p2_time = format_time(p2['total_time'])

            # Rough error calculation
            if name == "Elite":
                real_hours = 2.78  # ~2:47
            elif name == "Fast":
                real_hours = 3.30  # ~3:18
            else:
                real_hours = 3.85  # ~3:51

            p2_error = ((p2['total_time'] - real_hours) / real_hours) * 100

            print(f"| {name:10} | {real:9} | {p1_time:10} | {p2_time:11} | {p2_error:+5.1f}%  |")

        print()
        print("Note: Part 2 Full = threshold detection + fatigue model")
        print("      Positive error = prediction slower than reality")
        print()


if __name__ == "__main__":
    main()
