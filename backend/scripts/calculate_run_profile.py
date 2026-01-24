#!/usr/bin/env python
"""
Calculate run profile for a user from Strava activity splits.

This script:
1. Finds user by telegram_id
2. Calculates run profile from Run/TrailRun splits
3. Shows the profile data
4. Tests personalized predictions on Talgar Trail
"""

import sys
import os
import asyncio

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import gpxpy

from app.models.user import User
from app.models.user_profile import UserPerformanceProfile
from app.models.user_run_profile import UserRunProfile
from app.models.strava_activity import StravaActivity, StravaActivitySplit
from app.models.gpx import GPXFile
from app.services.user_profile import UserProfileService
from app.services.calculators.trail_run import TrailRunService, GAPMode


def format_time(hours: float) -> str:
    """Format hours as 'Xh Ymin'."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m:02d}min"


def format_pace(pace: float) -> str:
    """Format pace as 'X:YY/km'."""
    if pace is None:
        return "N/A"
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}/km"


def main():
    print("=" * 70)
    print("RUN PROFILE CALCULATOR")
    print("=" * 70)
    print()

    # Connect to database (sync)
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return

    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        # Find users with Strava connected
        print("Users with Strava connected:")
        print("-" * 40)
        users = db.query(User).filter(User.strava_connected == True).all()

        if not users:
            print("No users with Strava connected!")
            return

        for user in users:
            print(f"  - telegram_id: {user.telegram_id}")
            print(f"    name: {user.name}")
            print(f"    strava_athlete_id: {user.strava_athlete_id}")
            print()

        # Get first user (you)
        user = users[0]
        print(f"Using user: {user.telegram_id} ({user.name})")
        print()

        # Count activities by type
        print("Activity statistics:")
        print("-" * 40)

        activity_types = db.query(
            StravaActivity.activity_type,
            db.query(StravaActivity).filter(
                StravaActivity.user_id == user.id
            ).count()
        ).filter(
            StravaActivity.user_id == user.id
        ).distinct().all()

        # Actually count by type
        for activity_type in ["Run", "TrailRun", "Hike", "Walk"]:
            count = db.query(StravaActivity).filter(
                StravaActivity.user_id == user.id,
                StravaActivity.activity_type == activity_type
            ).count()
            if count > 0:
                print(f"  {activity_type}: {count}")
        print()

        # Count splits by activity type
        print("Splits statistics:")
        print("-" * 40)

        for activity_type in ["Run", "TrailRun", "Hike", "Walk"]:
            count = db.query(StravaActivitySplit).join(StravaActivity).filter(
                StravaActivity.user_id == user.id,
                StravaActivity.activity_type == activity_type
            ).count()
            if count > 0:
                print(f"  {activity_type}: {count} splits")
        print()

        # Check existing run profile
        print("Existing run profile:")
        print("-" * 40)

        run_profile = db.query(UserRunProfile).filter(
            UserRunProfile.user_id == user.id
        ).first()

        if run_profile:
            print(f"  Flat pace: {format_pace(run_profile.avg_flat_pace_min_km)}")
            print(f"  Gentle uphill: {format_pace(run_profile.avg_gentle_uphill_pace_min_km)}")
            print(f"  Moderate uphill: {format_pace(run_profile.avg_moderate_uphill_pace_min_km)}")
            print(f"  Steep uphill: {format_pace(run_profile.avg_steep_uphill_pace_min_km)}")
            print(f"  Gentle downhill: {format_pace(run_profile.avg_gentle_downhill_pace_min_km)}")
            print(f"  Moderate downhill: {format_pace(run_profile.avg_moderate_downhill_pace_min_km)}")
            print(f"  Steep downhill: {format_pace(run_profile.avg_steep_downhill_pace_min_km)}")
            print(f"  Walk threshold: {run_profile.walk_threshold_percent}%")
            print(f"  Activities: {run_profile.total_activities}")
            print(f"  Total distance: {run_profile.total_distance_km:.1f} km")
        else:
            print("  No run profile yet!")
        print()

        # Calculate run profile manually (sync version since async is complex)
        print("=" * 70)
        print("CALCULATING RUN PROFILE FROM SPLITS")
        print("=" * 70)
        print()

        # Get all running splits
        splits = db.query(StravaActivitySplit).join(StravaActivity).filter(
            StravaActivity.user_id == user.id,
            StravaActivity.activity_type.in_(["Run", "TrailRun"])
        ).all()

        print(f"Found {len(splits)} running splits")

        if len(splits) < 5:
            print("Not enough splits for profile calculation!")
            return

        # Classify by gradient
        from statistics import mean

        GRADIENT_THRESHOLDS = {
            'steep_downhill': (-100.0, -15.0),
            'moderate_downhill': (-15.0, -8.0),
            'gentle_downhill': (-8.0, -3.0),
            'flat': (-3.0, 3.0),
            'gentle_uphill': (3.0, 8.0),
            'moderate_uphill': (8.0, 15.0),
            'steep_uphill': (15.0, 100.0),
        }

        splits_by_category = {cat: [] for cat in GRADIENT_THRESHOLDS}

        PACE_MIN = 2.5
        PACE_MAX = 15.0
        filtered = 0

        for split in splits:
            if split.gradient_percent is None or split.pace_min_km is None:
                continue

            pace = split.pace_min_km
            gradient = split.gradient_percent

            # Filter outliers
            if pace < PACE_MIN or pace > PACE_MAX:
                filtered += 1
                continue

            # Classify
            for cat, (min_g, max_g) in GRADIENT_THRESHOLDS.items():
                if min_g <= gradient < max_g:
                    splits_by_category[cat].append(pace)
                    break
            else:
                if gradient >= 15.0:
                    splits_by_category['steep_uphill'].append(pace)
                elif gradient <= -15.0:
                    splits_by_category['steep_downhill'].append(pace)

        print(f"Filtered {filtered} outlier splits")
        print()

        # Calculate averages
        print("Calculated paces by gradient category:")
        print("-" * 50)

        extended_paces = {}
        for cat in ['steep_downhill', 'moderate_downhill', 'gentle_downhill',
                    'flat', 'gentle_uphill', 'moderate_uphill', 'steep_uphill']:
            paces = splits_by_category[cat]
            if paces:
                avg = mean(paces)
                extended_paces[cat] = avg
                print(f"  {cat:20}: {format_pace(avg)} ({len(paces)} splits)")
            else:
                extended_paces[cat] = None
                print(f"  {cat:20}: N/A (0 splits)")
        print()

        # Update or create profile
        print("Saving run profile...")

        if not run_profile:
            run_profile = UserRunProfile(
                user_id=user.id,
            )
            db.add(run_profile)

        run_profile.avg_flat_pace_min_km = extended_paces['flat']
        run_profile.avg_gentle_uphill_pace_min_km = extended_paces['gentle_uphill']
        run_profile.avg_moderate_uphill_pace_min_km = extended_paces['moderate_uphill']
        run_profile.avg_steep_uphill_pace_min_km = extended_paces['steep_uphill']
        run_profile.avg_gentle_downhill_pace_min_km = extended_paces['gentle_downhill']
        run_profile.avg_moderate_downhill_pace_min_km = extended_paces['moderate_downhill']
        run_profile.avg_steep_downhill_pace_min_km = extended_paces['steep_downhill']

        # Save sample counts for confidence assessment
        run_profile.flat_sample_count = len(splits_by_category['flat'])
        run_profile.gentle_uphill_sample_count = len(splits_by_category['gentle_uphill'])
        run_profile.moderate_uphill_sample_count = len(splits_by_category['moderate_uphill'])
        run_profile.steep_uphill_sample_count = len(splits_by_category['steep_uphill'])
        run_profile.gentle_downhill_sample_count = len(splits_by_category['gentle_downhill'])
        run_profile.moderate_downhill_sample_count = len(splits_by_category['moderate_downhill'])
        run_profile.steep_downhill_sample_count = len(splits_by_category['steep_downhill'])

        run_profile.walk_threshold_percent = 25.0  # Default
        run_profile.total_activities = len(set(s.activity_id for s in splits))
        run_profile.total_distance_km = sum(
            a.distance_m / 1000 for a in db.query(StravaActivity).filter(
                StravaActivity.user_id == user.id,
                StravaActivity.activity_type.in_(["Run", "TrailRun"])
            ).all()
        )

        db.commit()
        db.refresh(run_profile)

        print("Run profile saved!")
        print()

        # Now test on Talgar Trail
        print("=" * 70)
        print("TESTING PERSONALIZED PREDICTION ON TALGAR TRAIL")
        print("=" * 70)
        print()

        # Load GPX
        gpx_file = db.query(GPXFile).filter(
            GPXFile.name.ilike("%talgar%")
        ).first()

        if not gpx_file or not gpx_file.gpx_content:
            print("Talgar Trail GPX not found!")
            return

        # Parse points
        gpx = gpxpy.parse(gpx_file.gpx_content.decode('utf-8'))
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    if point.elevation is not None:
                        points.append((point.latitude, point.longitude, point.elevation))

        print(f"Track: {gpx_file.name}")
        print(f"Points: {len(points)}")
        print()

        # Get hike profile too
        hike_profile = db.query(UserPerformanceProfile).filter(
            UserPerformanceProfile.user_id == user.id
        ).first()

        print("Your profiles:")
        print("-" * 40)
        print(f"  Run profile: {'Yes' if run_profile else 'No'}")
        print(f"  Hike profile: {'Yes' if hike_profile else 'No'}")
        if run_profile:
            print(f"  Flat run pace: {format_pace(run_profile.avg_flat_pace_min_km)}")
        print()

        # Real race reference
        print("Real race data (Talgar Trail 25K):")
        print("-" * 40)
        print("  Elite:        2:47-2:50")
        print("  Fast:         3:18")
        print("  Moderate:     3:47-3:56")
        print()

        # Test with different configurations
        print("=" * 70)
        print("PREDICTIONS")
        print("=" * 70)
        print()

        # 1. Generic prediction (no profile)
        print("1. Generic (no personalization):")
        service_generic = TrailRunService(
            gap_mode=GAPMode.STRAVA,
            flat_pace_min_km=run_profile.avg_flat_pace_min_km or 6.0,
            apply_fatigue=False,
        )
        result_generic = service_generic.calculate_route(points)
        print(f"   Combined: {format_time(result_generic.totals['combined'])}")
        print()

        # 2. With run profile personalization
        print("2. With RUN profile personalization:")
        service_personalized = TrailRunService(
            gap_mode=GAPMode.STRAVA,
            flat_pace_min_km=run_profile.avg_flat_pace_min_km or 6.0,
            run_profile=run_profile,
            hike_profile=hike_profile,
            apply_fatigue=False,
        )
        result_personalized = service_personalized.calculate_route(points)

        print(f"   Combined: {format_time(result_personalized.totals['combined'])}")
        if 'run_personalized' in result_personalized.totals:
            print(f"   Run personalized: {format_time(result_personalized.totals['run_personalized'])}")
        if 'hike_personalized' in result_personalized.totals:
            print(f"   Hike personalized: {format_time(result_personalized.totals['hike_personalized'])}")
        print(f"   Personalized: {result_personalized.personalized}")
        print(f"   Run activities used: {result_personalized.run_activities_used}")
        print(f"   Hike activities used: {result_personalized.hike_activities_used}")
        print()

        # Summary
        print("=" * 70)
        print("SUMMARY: Your Personalized Prediction")
        print("=" * 70)
        print()
        print(f"Your flat running pace: {format_pace(run_profile.avg_flat_pace_min_km)}")
        print()

        s = result_personalized.summary
        print(f"Route breakdown:")
        print(f"  Total distance: {s.total_distance_km:.1f} km")
        print(f"  Elevation: +{s.total_elevation_gain_m:.0f}m / -{s.total_elevation_loss_m:.0f}m")
        print(f"  Running: {s.running_distance_km:.1f} km ({s.running_distance_km/s.total_distance_km*100:.0f}%)")
        print(f"  Hiking: {s.hiking_distance_km:.1f} km")
        print()

        print(f"Predicted time: {format_time(result_personalized.totals['combined'])}")
        print()

        # Compare to real results
        predicted_hours = result_personalized.totals['combined']

        # Map your pace to real runners
        your_pace = run_profile.avg_flat_pace_min_km or 6.0

        if your_pace <= 5.5:
            ref_time = 2.78  # Elite
            ref_label = "Elite (2:47)"
        elif your_pace <= 6.5:
            ref_time = 3.30  # Fast
            ref_label = "Fast (3:18)"
        elif your_pace <= 7.5:
            ref_time = 3.85  # Moderate
            ref_label = "Moderate (3:51)"
        else:
            ref_time = 4.50  # Recreational
            ref_label = "Recreational (4:30)"

        error = (predicted_hours - ref_time) / ref_time * 100
        print(f"Reference category: {ref_label}")
        print(f"Prediction error: {error:+.1f}%")


if __name__ == "__main__":
    main()
