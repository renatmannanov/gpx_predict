#!/usr/bin/env python
"""
Test TrailRunService on Talgar Trail GPX.

Validates Part 3 implementation against real race results.
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
from app.services.calculators.trail_run import TrailRunService, GAPMode


def format_time(hours: float) -> str:
    """Format hours as 'Xh Ymin'."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m:02d}min"


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


def main():
    print("=" * 70)
    print("TRAIL RUN SERVICE TEST - Talgar Trail 25K")
    print("=" * 70)
    print()

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

        print(f"Track: {gpx_file.name}")
        print(f"Points: {len(points)}")
        print()

        # Real race reference
        print("REAL RACE DATA:")
        print("  Elite (Irbis):  2:47-2:50")
        print("  Fast (Winner):  3:18")
        print("  Moderate:       3:47-3:56")
        print("  Recreational:   4:20-4:40")
        print()

        # Test profiles
        profiles = [
            ("Elite", 5.0, 2.78),
            ("Fast", 6.0, 3.30),
            ("Moderate", 7.0, 3.85),
            ("Recreational", 8.0, 4.50),
        ]

        print("=" * 70)
        print("TRAIL RUN SERVICE RESULTS")
        print("=" * 70)
        print()

        for name, pace, real_hours in profiles:
            print(f"--- {name} Runner (base pace: {int(pace)}:{int((pace%1)*60):02d}/km) ---")

            # Without fatigue
            service = TrailRunService(
                gap_mode=GAPMode.STRAVA,
                flat_pace_min_km=pace,
                apply_fatigue=False,
            )
            result = service.calculate_route(points)

            # With fatigue
            service_fatigue = TrailRunService(
                gap_mode=GAPMode.STRAVA,
                flat_pace_min_km=pace,
                apply_fatigue=True,
            )
            result_fatigue = service_fatigue.calculate_route(points)

            print(f"  Without fatigue:")
            print(f"    Combined:     {format_time(result.totals['combined'])}")
            print(f"    Strava GAP:   {format_time(result.totals['strava_gap'])}")
            print(f"    Minetti GAP:  {format_time(result.totals['minetti_gap'])}")
            print()

            print(f"  With fatigue:")
            print(f"    Combined:     {format_time(result_fatigue.totals['combined'])}")
            print()

            # Summary
            s = result.summary
            print(f"  Route breakdown:")
            print(f"    Running:      {s.running_distance_km:.1f} km ({s.running_distance_km/s.total_distance_km*100:.0f}%)")
            print(f"    Hiking:       {s.hiking_distance_km:.1f} km")
            print(f"    Elev impact:  +{s.elevation_impact_percent:.0f}%")
            print()

            # Error vs real
            error_no_fatigue = (result.totals['combined'] - real_hours) / real_hours * 100
            error_fatigue = (result_fatigue.totals['combined'] - real_hours) / real_hours * 100
            print(f"  Error vs real:")
            print(f"    No fatigue:   {error_no_fatigue:+.1f}%")
            print(f"    With fatigue: {error_fatigue:+.1f}%")
            print()
            print()

        # Summary table
        print("=" * 70)
        print("SUMMARY: TrailRunService vs Real Results")
        print("=" * 70)
        print()
        print("| Profile      | Real   | No Fatigue | With Fatigue | Best Error |")
        print("|--------------|--------|------------|--------------|------------|")

        for name, pace, real_hours in profiles:
            service = TrailRunService(flat_pace_min_km=pace, apply_fatigue=False)
            service_fat = TrailRunService(flat_pace_min_km=pace, apply_fatigue=True)

            result = service.calculate_route(points)
            result_fat = service_fat.calculate_route(points)

            time_no_fat = result.totals['combined']
            time_fat = result_fat.totals['combined']

            err_no_fat = (time_no_fat - real_hours) / real_hours * 100
            err_fat = (time_fat - real_hours) / real_hours * 100

            best_err = min(abs(err_no_fat), abs(err_fat))
            best_str = "no fat" if abs(err_no_fat) < abs(err_fat) else "fatigue"

            real_str = f"{int(real_hours)}:{int((real_hours%1)*60):02d}"
            no_fat_str = format_time(time_no_fat)
            fat_str = format_time(time_fat)

            print(f"| {name:12} | {real_str:6} | {no_fat_str:10} | {fat_str:12} | {best_err:+.1f}% ({best_str}) |")

        print()
        print("Note: Positive error = prediction slower than reality")
        print()

        # Service info
        print("=" * 70)
        print("SERVICE INFO")
        print("=" * 70)
        service = TrailRunService(apply_fatigue=True)
        info = service.get_info()
        for key, value in info.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
