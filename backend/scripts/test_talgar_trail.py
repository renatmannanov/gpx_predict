#!/usr/bin/env python
"""
Test script to load Talgar Trail from database and run through GAP calculator.

This script:
1. Loads the GPX file from database
2. Parses it to extract route points
3. Runs through GAP calculator (both Strava and Minetti modes)
4. Compares with Tobler hiking estimates
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
from app.services.calculators.trail_run import GAPCalculator, GAPMode, compare_gap_modes
from app.services.calculators.tobler import ToblerCalculator
from app.services.calculators.comparison import ComparisonService


def format_time(hours: float) -> str:
    """Format hours as 'Xh Ymin'."""
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f"{h}h {m}min"
    return f"{m}min"


def load_gpx_from_db(db: Session, search_term: str = "talgar"):
    """Load GPX file from database by name search."""
    gpx_file = db.query(GPXFile).filter(
        GPXFile.name.ilike(f"%{search_term}%")
    ).first()

    if not gpx_file:
        # Try filename
        gpx_file = db.query(GPXFile).filter(
            GPXFile.filename.ilike(f"%{search_term}%")
        ).first()

    return gpx_file


def parse_gpx_content(gpx_content: bytes) -> list:
    """Parse GPX content and extract points as (lat, lon, elevation) tuples."""
    gpx = gpxpy.parse(gpx_content.decode('utf-8'))

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.elevation is not None:
                    points.append((point.latitude, point.longitude, point.elevation))

    # Also check routes
    for route in gpx.routes:
        for point in route.points:
            if point.elevation is not None:
                points.append((point.latitude, point.longitude, point.elevation))

    return points


def main():
    print("=" * 60)
    print("Talgar Trail GAP Calculator Test")
    print("=" * 60)
    print()

    # Connect to database
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        print("Looking for app.db in backend directory...")
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app.db')

    if not os.path.exists(db_path):
        print(f"Database not found!")
        return

    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        # List all GPX files first
        print("Available GPX files in database:")
        print("-" * 40)
        all_gpx = db.query(GPXFile).all()

        if not all_gpx:
            print("No GPX files found in database!")
            return

        for gpx in all_gpx:
            print(f"  - {gpx.name or gpx.filename}")
            print(f"    Distance: {gpx.distance_km:.2f} km" if gpx.distance_km else "    Distance: N/A")
            print(f"    Elevation: +{gpx.elevation_gain_m:.0f}m" if gpx.elevation_gain_m else "    Elevation: N/A")
            print()

        # Load Talgar Trail
        print("-" * 40)
        print("Loading Talgar Trail...")
        gpx_file = load_gpx_from_db(db, "talgar")

        if not gpx_file:
            print("Talgar Trail not found! Trying first available GPX...")
            gpx_file = all_gpx[0]

        print(f"Found: {gpx_file.name or gpx_file.filename}")
        print(f"  Distance: {gpx_file.distance_km:.2f} km" if gpx_file.distance_km else "  Distance: N/A")
        print(f"  Elevation gain: +{gpx_file.elevation_gain_m:.0f}m" if gpx_file.elevation_gain_m else "  Elevation: N/A")
        print(f"  Elevation loss: -{gpx_file.elevation_loss_m:.0f}m" if gpx_file.elevation_loss_m else "")
        print()

        if not gpx_file.gpx_content:
            print("GPX content is empty!")
            return

        # Parse GPX
        print("Parsing GPX content...")
        points = parse_gpx_content(gpx_file.gpx_content)
        print(f"  Extracted {len(points)} points")
        print()

        # Segment the route
        print("Segmenting route...")
        segments = RouteSegmenter.segment_route(points)
        print(f"  Created {len(segments)} macro-segments")
        print()

        # Calculate route stats
        total_distance = sum(s.distance_km for s in segments)
        total_ascent = sum(s.elevation_gain_m for s in segments)
        total_descent = sum(s.elevation_loss_m for s in segments)

        print("Route Statistics:")
        print(f"  Total distance: {total_distance:.2f} km")
        print(f"  Total ascent: +{total_ascent:.0f} m")
        print(f"  Total descent: -{total_descent:.0f} m")
        print()

        # Test GAP Calculator with different base paces
        print("=" * 60)
        print("GAP Calculator Results")
        print("=" * 60)
        print()

        base_paces = [
            (5.0, "Elite (5:00/km)"),
            (6.0, "Fast (6:00/km)"),
            (7.0, "Moderate (7:00/km)"),
            (8.0, "Comfortable (8:00/km)"),
        ]

        for base_pace, pace_label in base_paces:
            print(f"Base flat pace: {pace_label}")
            print("-" * 40)

            # Strava GAP
            gap_strava = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.STRAVA)
            total_strava, _ = gap_strava.calculate_route(segments)

            # Minetti GAP
            gap_minetti = GAPCalculator(base_flat_pace_min_km=base_pace, mode=GAPMode.MINETTI)
            total_minetti, _ = gap_minetti.calculate_route(segments)

            print(f"  Strava GAP:  {format_time(total_strava)}")
            print(f"  Minetti GAP: {format_time(total_minetti)}")
            print()

        # Compare with hiking estimates
        print("=" * 60)
        print("Comparison with Hiking Estimates")
        print("=" * 60)
        print()

        comparison_service = ComparisonService()
        comparison = comparison_service.compare_route(points, profile_multiplier=1.0)

        print("Hiking estimates (profile multiplier = 1.0):")
        for method_name, total_hours in comparison.totals.items():
            print(f"  {method_name}: {format_time(total_hours)}")
        print()

        # Summary comparison
        print("=" * 60)
        print("SUMMARY: Talgar Trail Time Estimates")
        print("=" * 60)
        print()

        # Hiking
        tobler_time = comparison.totals.get('tobler', 0)
        naismith_time = comparison.totals.get('naismith', 0)

        print("HIKING (walking):")
        print(f"  Tobler method:   {format_time(tobler_time)}")
        print(f"  Naismith method: {format_time(naismith_time)}")
        print()

        # Trail running
        gap_moderate = GAPCalculator(base_flat_pace_min_km=6.0, mode=GAPMode.STRAVA)
        trail_run_time, _ = gap_moderate.calculate_route(segments)

        print("TRAIL RUNNING (6:00/km flat pace):")
        print(f"  Strava GAP: {format_time(trail_run_time)}")
        print()

        # Speed-up factor
        if tobler_time > 0:
            speedup = tobler_time / trail_run_time
            print(f"Trail running is ~{speedup:.1f}x faster than hiking")


if __name__ == "__main__":
    main()
