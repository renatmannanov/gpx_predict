#!/usr/bin/env python
"""
Analyze specific activities to understand outlier splits.
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.strava_activity import StravaActivity, StravaActivitySplit


def format_pace(pace: float) -> str:
    if pace is None:
        return "N/A"
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}/km"


def analyze_activity(db: Session, strava_id: int, name: str):
    print("=" * 80)
    print(f"ACTIVITY: {name}")
    print(f"Strava: https://www.strava.com/activities/{strava_id}")
    print("=" * 80)
    print()

    activity = db.query(StravaActivity).filter(
        StravaActivity.strava_id == str(strava_id)
    ).first()

    if not activity:
        print("Activity not found in database!")
        return

    # Activity summary
    print("ACTIVITY SUMMARY:")
    print(f"  Type: {activity.activity_type}")
    print(f"  Date: {activity.start_date}")
    print(f"  Distance: {activity.distance_m/1000:.2f} km")
    print(f"  Elevation: +{activity.elevation_gain_m:.0f}m" if activity.elevation_gain_m else "  Elevation: N/A")
    print(f"  Moving time: {activity.moving_time_s//3600}h {(activity.moving_time_s%3600)//60}min")

    if activity.distance_m and activity.moving_time_s:
        avg_pace = (activity.moving_time_s / 60) / (activity.distance_m / 1000)
        print(f"  Average pace: {format_pace(avg_pace)}")
    print()

    # Get all splits
    splits = db.query(StravaActivitySplit).filter(
        StravaActivitySplit.activity_id == activity.id
    ).order_by(StravaActivitySplit.split_number).all()

    print(f"SPLITS ({len(splits)} total):")
    print("-" * 70)
    print(f"{'#':>3} {'Pace':>10} {'Gradient':>10} {'Elev':>8} {'Status':>12}")
    print("-" * 70)

    PACE_MIN = 2.5
    PACE_MAX = 15.0

    outlier_count = 0
    valid_count = 0

    for split in splits:
        pace = format_pace(split.pace_min_km)
        gradient = f"{split.gradient_percent:+.1f}%" if split.gradient_percent else "N/A"
        elev = f"{split.elevation_diff_m:+.0f}m" if split.elevation_diff_m else "N/A"

        if split.pace_min_km is None:
            status = "NO PACE"
        elif split.pace_min_km < PACE_MIN:
            status = "⚡ TOO FAST"
            outlier_count += 1
        elif split.pace_min_km > PACE_MAX:
            status = "🐢 TOO SLOW"
            outlier_count += 1
        else:
            status = "✅ Valid"
            valid_count += 1

        print(f"{split.split_number:>3} {pace:>10} {gradient:>10} {elev:>8} {status:>12}")

    print("-" * 70)
    print(f"Valid: {valid_count}, Outliers: {outlier_count}")
    print()

    # Analysis
    print("ANALYSIS:")

    if outlier_count > 0:
        outlier_splits = [s for s in splits if s.pace_min_km and (s.pace_min_km < PACE_MIN or s.pace_min_km > PACE_MAX)]

        # Check if outliers are slow uphills
        slow_uphills = [s for s in outlier_splits if s.gradient_percent and s.gradient_percent > 10]
        slow_flat = [s for s in outlier_splits if s.gradient_percent and -3 <= s.gradient_percent <= 3]
        slow_downhill = [s for s in outlier_splits if s.gradient_percent and s.gradient_percent < -3]

        print(f"  Slow uphills (>10%): {len(slow_uphills)}")
        print(f"  Slow on flat: {len(slow_flat)}")
        print(f"  Slow downhills: {len(slow_downhill)}")

        if slow_uphills:
            print()
            print("  Slow uphill splits might be:")
            print("  - Power hiking (not running)")
            print("  - Stops for photos/rest")
            print("  - Technical sections")

        if slow_flat:
            print()
            print("  Slow flat splits suggest:")
            print("  - Definite stops/breaks")
            print("  - GPS issues")

    print()
    print()


def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        # Activities to analyze
        activities = [
            (15088333660, "Talgar trail check (14 outliers)"),
            (15589508895, "Irbis / Talgar Check #2 (9 outliers)"),
            (15724390211, "Irbis Race / Talgar (4 outliers) - RACE!"),
        ]

        for strava_id, name in activities:
            analyze_activity(db, strava_id, name)

        # Summary recommendations
        print("=" * 80)
        print("RECOMMENDATIONS FOR PROFILE")
        print("=" * 80)
        print()
        print("Based on your feedback:")
        print()
        print("1. Talgar trail check - should be EXCLUDED (hiking, not running)")
        print("   → Mark activity type as 'Hike' in Strava, or")
        print("   → Filter by activity name pattern")
        print()
        print("2. Irbis / Talgar Check #2 - splits might have GPS issues")
        print("   → 9 outliers seems high for a training run")
        print("   → Check the activity in Strava for GPS gaps")
        print()
        print("3. Irbis Race / Talgar - THIS IS YOUR RACE DATA!")
        print("   → 4 outliers on a race is suspicious")
        print("   → These should be your best data")
        print("   → Let's see what's happening with those splits")


if __name__ == "__main__":
    main()
