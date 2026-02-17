#!/usr/bin/env python
"""
Compare different threshold values (25%, 20%, 15%) on Talgar Trail.
Shows detailed segment analysis and prediction accuracy vs real results.
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import gpxpy

from app.models.gpx import GPXFile
from app.features.gpx import RouteSegmenter
from app.features.trail_run.calculators import (
    GAPCalculator, GAPMode,
    HikeRunThresholdService, MovementMode,
    RunnerFatigueService,
)
from app.features.hiking.calculators import ToblerCalculator


def format_time(hours: float) -> str:
    """Format hours as 'Xh Ymin'."""
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


def format_time_short(hours: float) -> str:
    """Format hours as 'X:YY'."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}:{m:02d}"


def load_gpx_from_db(db: Session, search_term: str = "talgar"):
    gpx_file = db.query(GPXFile).filter(
        GPXFile.name.ilike(f"%{search_term}%")
    ).first()
    if not gpx_file:
        gpx_file = db.query(GPXFile).filter(
            GPXFile.filename.ilike(f"%{search_term}%")
        ).first()
    return gpx_file


def parse_gpx_content(gpx_content: bytes) -> list:
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


def get_decisions(segments, threshold: float):
    """Get run/hike decisions for given threshold."""
    service = HikeRunThresholdService(uphill_threshold=threshold)
    return service.process_route(segments)


def calculate_time_with_threshold(segments, base_pace: float, threshold: float, distance_km: float):
    """Calculate total time with given threshold (threshold + fatigue)."""
    threshold_service = HikeRunThresholdService(uphill_threshold=threshold)
    gap_run = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.STRAVA)
    tobler_hike = ToblerCalculator()
    fatigue = RunnerFatigueService.create_enabled(distance_km=distance_km)

    total_time = 0.0
    run_time = 0.0
    hike_time = 0.0
    elapsed_hours = 0.0

    decisions = threshold_service.process_route(segments)

    for decision in decisions:
        segment = decision.segment

        if decision.mode == MovementMode.RUN:
            result = gap_run.calculate_segment(segment)
            run_time += result.time_hours
        else:
            result = tobler_hike.calculate_segment(segment, profile_multiplier=1.0)
            hike_time += result.time_hours

        base_time = result.time_hours

        adjusted_time, _ = fatigue.apply_to_segment(
            base_time,
            elapsed_hours,
            segment.gradient_percent
        )

        total_time += adjusted_time
        elapsed_hours += adjusted_time

    summary = threshold_service.get_summary(decisions)

    return {
        "total_time": total_time,
        "run_time": run_time,
        "hike_time": hike_time,
        "run_segments": summary["run_segments"],
        "hike_segments": summary["hike_segments"],
        "run_percent": summary["run_percent"],
        "hike_distance_km": summary["hike_distance_km"],
    }


def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return

    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        gpx_file = load_gpx_from_db(db, "talgar")
        if not gpx_file or not gpx_file.gpx_content:
            print("Talgar Trail GPX not found!")
            return

        points = parse_gpx_content(gpx_file.gpx_content)
        segments = RouteSegmenter.segment_route(points)
        total_distance = sum(s.distance_km for s in segments)

        # Get decisions for all three thresholds
        decisions_25 = get_decisions(segments, 25.0)
        decisions_20 = get_decisions(segments, 20.0)
        decisions_15 = get_decisions(segments, 15.0)

        print("=" * 120)
        print("TALGAR TRAIL 25K - THRESHOLD COMPARISON (25% vs 20% vs 15%)")
        print("=" * 120)
        print()

        # Segment table with all three thresholds
        print("| #  | Dist km | Gradient | Type        | 25% threshold | 20% threshold | 15% threshold |")
        print("|----|---------|----------|-------------|---------------|---------------|---------------|")

        for i, (seg, d25, d20, d15) in enumerate(zip(segments, decisions_25, decisions_20, decisions_15)):
            if seg.gradient_percent > 3:
                seg_type = "Uphill"
            elif seg.gradient_percent < -3:
                seg_type = "Downhill"
            else:
                seg_type = "Flat"

            m25 = "🏃 RUN" if d25.mode == MovementMode.RUN else "🚶 HIKE"
            m20 = "🏃 RUN" if d20.mode == MovementMode.RUN else "🚶 HIKE"
            m15 = "🏃 RUN" if d15.mode == MovementMode.RUN else "🚶 HIKE"

            # Highlight changed segments
            changed = ""
            if d25.mode != d20.mode or d20.mode != d15.mode:
                changed = " ⚠️"

            print(f"| {i+1:2} |   {seg.distance_km:5.2f} |  {seg.gradient_percent:+6.1f}% | {seg_type:11} | {m25:13} | {m20:13} | {m15:13} |{changed}")

        print()

        # Summary for each threshold
        print("=" * 120)
        print("SUMMARY BY THRESHOLD")
        print("=" * 120)
        print()

        thresholds = [25.0, 20.0, 15.0]
        summaries = {}

        for threshold in thresholds:
            service = HikeRunThresholdService(uphill_threshold=threshold)
            decisions = service.process_route(segments)
            summary = service.get_summary(decisions)
            summaries[threshold] = summary

        print("| Threshold | Run Segments | Hike Segments | Run Distance | Hike Distance | Run % |")
        print("|-----------|--------------|---------------|--------------|---------------|-------|")

        for threshold in thresholds:
            s = summaries[threshold]
            print(f"|    {threshold:4.0f}%  |      {s['run_segments']:2}      |       {s['hike_segments']:2}      |    {s['run_distance_km']:5.2f} km  |    {s['hike_distance_km']:5.2f} km  | {s['run_percent']:5.1f}% |")

        print()

        # Time predictions with different thresholds vs real results
        print("=" * 120)
        print("TIME PREDICTIONS VS REAL RESULTS")
        print("=" * 120)
        print()

        profiles = [
            ("Elite", 5.0, "2:47-2:50", 2.78),      # Irbis elite
            ("Fast (Winner)", 6.0, "3:18", 3.30),   # Talgar winner
            ("Moderate (Top10)", 7.0, "3:47-3:56", 3.85),  # Top 5-10
            ("Recreational", 8.0, "4:20-4:40", 4.50),  # Average finisher
        ]

        print("| Profile            | Real Time | 25% thresh | 20% thresh | 15% thresh | Best Match |")
        print("|--------------------|-----------|------------|------------|------------|------------|")

        for name, pace, real_str, real_hours in profiles:
            results = {}
            for threshold in thresholds:
                r = calculate_time_with_threshold(segments, pace, threshold, total_distance)
                results[threshold] = r["total_time"]

            # Find best match
            errors = {t: abs(results[t] - real_hours) / real_hours * 100 for t in thresholds}
            best_threshold = min(errors, key=errors.get)

            print(f"| {name:18} | {real_str:9} | {format_time_short(results[25.0]):>10} | {format_time_short(results[20.0]):>10} | {format_time_short(results[15.0]):>10} | {best_threshold:.0f}% ({errors[best_threshold]:+.1f}%) |")

        print()

        # Detailed error analysis
        print("=" * 120)
        print("ERROR ANALYSIS (Prediction vs Reality)")
        print("=" * 120)
        print()
        print("| Profile            | Real hrs | 25% error | 20% error | 15% error |")
        print("|--------------------|----------|-----------|-----------|-----------|")

        for name, pace, real_str, real_hours in profiles:
            results = {}
            for threshold in thresholds:
                r = calculate_time_with_threshold(segments, pace, threshold, total_distance)
                results[threshold] = r["total_time"]

            errors = {t: (results[t] - real_hours) / real_hours * 100 for t in thresholds}

            print(f"| {name:18} |   {real_hours:.2f}   |  {errors[25.0]:+6.1f}%  |  {errors[20.0]:+6.1f}%  |  {errors[15.0]:+6.1f}%  |")

        print()
        print("Note: Positive = prediction slower than reality, Negative = faster than reality")
        print()

        # Which segments change with lower thresholds
        print("=" * 120)
        print("SEGMENTS THAT CHANGE WITH LOWER THRESHOLDS")
        print("=" * 120)
        print()

        for i, (seg, d25, d20, d15) in enumerate(zip(segments, decisions_25, decisions_20, decisions_15)):
            changes = []
            if d25.mode != d20.mode:
                changes.append(f"25%→20%: {d25.mode.value}→{d20.mode.value}")
            if d20.mode != d15.mode:
                changes.append(f"20%→15%: {d20.mode.value}→{d15.mode.value}")

            if changes:
                print(f"Segment #{i+1}: {seg.distance_km:.2f} km, gradient {seg.gradient_percent:+.1f}%")
                for change in changes:
                    print(f"    {change}")
                print()


if __name__ == "__main__":
    main()
