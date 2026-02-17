#!/usr/bin/env python
"""
Recalculate run profile with smart gradient-aware filtering.

Instead of fixed 15 min/km cutoff, use gradient-specific limits
based on what's physiologically reasonable.
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from statistics import mean, stdev
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.user import User
from app.features.trail_run import UserTrailRunProfile as UserRunProfile
from app.models.strava_activity import StravaActivity, StravaActivitySplit


def format_pace(pace: float) -> str:
    if pace is None:
        return "N/A"
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}/km"


def get_max_reasonable_pace(gradient_percent: float) -> float:
    """
    Get maximum reasonable running/power-hiking pace for a gradient.

    Based on real race data and physiology:
    - Flat: max ~12 min/km (very slow jog)
    - +10%: max ~18 min/km
    - +20%: max ~25 min/km (power hike zone)
    - +30%: max ~35 min/km (steep power hike)

    Downhills: similar but slightly lower limits (technical)
    """
    gradient = abs(gradient_percent)

    if gradient < 5:
        return 15.0  # Flat-ish
    elif gradient < 10:
        return 18.0  # Gentle slope
    elif gradient < 15:
        return 22.0  # Moderate slope
    elif gradient < 20:
        return 28.0  # Steep slope
    elif gradient < 25:
        return 35.0  # Very steep
    elif gradient < 30:
        return 42.0  # Power hike territory
    else:
        return 55.0  # Extreme gradient - almost anything goes


def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app.db')
    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as db:
        user = db.query(User).filter(User.strava_connected == True).first()
        if not user:
            print("No user found!")
            return

        print("=" * 80)
        print("SMART RUN PROFILE CALCULATION")
        print(f"User: {user.name}")
        print("=" * 80)
        print()

        # Get running activities, EXCLUDING known hiking activities
        EXCLUDE_PATTERNS = ['trail check', 'check #']  # These are hiking recon

        run_activities = db.query(StravaActivity).filter(
            StravaActivity.user_id == user.id,
            StravaActivity.activity_type.in_(["Run", "TrailRun"])
        ).all()

        # Filter out hiking recon
        filtered_activities = []
        excluded = []
        for act in run_activities:
            name_lower = (act.name or "").lower()
            if any(pattern in name_lower for pattern in EXCLUDE_PATTERNS):
                excluded.append(act)
            else:
                filtered_activities.append(act)

        print(f"Total Run/TrailRun activities: {len(run_activities)}")
        print(f"Excluded as hiking recon: {len(excluded)}")
        for act in excluded:
            print(f"  - {act.name} (https://www.strava.com/activities/{act.strava_id})")
        print(f"Activities for profile: {len(filtered_activities)}")
        print()

        # Get splits from filtered activities
        activity_ids = [a.id for a in filtered_activities]

        all_splits = db.query(StravaActivitySplit).filter(
            StravaActivitySplit.activity_id.in_(activity_ids)
        ).all()

        print(f"Total splits from valid activities: {len(all_splits)}")
        print()

        # Apply smart filtering
        GRADIENT_THRESHOLDS = {
            'steep_downhill': (-100.0, -15.0),
            'moderate_downhill': (-15.0, -8.0),
            'gentle_downhill': (-8.0, -3.0),
            'flat': (-3.0, 3.0),
            'gentle_uphill': (3.0, 8.0),
            'moderate_uphill': (8.0, 15.0),
            'steep_uphill': (15.0, 100.0),
        }

        splits_by_cat = {cat: [] for cat in GRADIENT_THRESHOLDS}

        PACE_MIN = 2.5  # Still filter GPS errors

        old_filtered = 0
        new_filtered = 0
        accepted_splits = []

        print("SMART FILTERING:")
        print("-" * 70)
        print(f"{'Gradient':>10} {'Pace':>10} {'Max Allowed':>12} {'Old Filter':>12} {'Decision':>10}")
        print("-" * 70)

        for split in all_splits:
            if split.pace_min_km is None or split.gradient_percent is None:
                continue

            pace = split.pace_min_km
            gradient = split.gradient_percent

            max_pace = get_max_reasonable_pace(gradient)
            old_max = 15.0

            # Old filter decision
            old_ok = PACE_MIN <= pace <= old_max

            # New smart filter decision
            new_ok = PACE_MIN <= pace <= max_pace

            if not old_ok:
                old_filtered += 1

            if not new_ok:
                new_filtered += 1
                decision = "❌ FILTER"
            elif not old_ok and new_ok:
                decision = "✅ RESCUED"
                print(f"{gradient:>+9.1f}% {format_pace(pace):>10} {format_pace(max_pace):>12} {format_pace(old_max):>12} {decision:>10}")
            else:
                decision = "✅ OK"

            if new_ok:
                accepted_splits.append(split)

                # Classify
                for cat, (min_g, max_g) in GRADIENT_THRESHOLDS.items():
                    if min_g <= gradient < max_g:
                        splits_by_cat[cat].append(pace)
                        break

        print("-" * 70)
        print()
        print(f"Old filter (15 min/km fixed): {old_filtered} filtered")
        print(f"New smart filter: {new_filtered} filtered")
        print(f"Splits rescued: {old_filtered - new_filtered}")
        print(f"Total valid splits: {len(accepted_splits)}")
        print()

        # Calculate new profile
        print("=" * 80)
        print("NEW PROFILE WITH SMART FILTERING")
        print("=" * 80)
        print()

        print(f"{'Category':<20} {'Count':>6} {'Avg Pace':>10} {'Min':>8} {'Max':>8}")
        print("-" * 55)

        new_paces = {}
        for cat in ['steep_downhill', 'moderate_downhill', 'gentle_downhill',
                    'flat', 'gentle_uphill', 'moderate_uphill', 'steep_uphill']:
            paces = splits_by_cat[cat]
            if paces:
                avg = mean(paces)
                new_paces[cat] = avg
                print(f"{cat:<20} {len(paces):>6} {format_pace(avg):>10} {format_pace(min(paces)):>8} {format_pace(max(paces)):>8}")
            else:
                new_paces[cat] = None
                print(f"{cat:<20} {0:>6} {'N/A':>10}")

        print()

        # Compare with old profile
        run_profile = db.query(UserRunProfile).filter(UserRunProfile.user_id == user.id).first()

        if run_profile:
            print("=" * 80)
            print("COMPARISON: OLD vs NEW PROFILE")
            print("=" * 80)
            print()
            print(f"{'Category':<20} {'Old':>10} {'New':>10} {'Diff':>10}")
            print("-" * 55)

            comparisons = [
                ('flat', run_profile.avg_flat_pace_min_km),
                ('gentle_uphill', run_profile.avg_gentle_uphill_pace_min_km),
                ('moderate_uphill', run_profile.avg_moderate_uphill_pace_min_km),
                ('steep_uphill', run_profile.avg_steep_uphill_pace_min_km),
                ('gentle_downhill', run_profile.avg_gentle_downhill_pace_min_km),
                ('moderate_downhill', run_profile.avg_moderate_downhill_pace_min_km),
                ('steep_downhill', run_profile.avg_steep_downhill_pace_min_km),
            ]

            for cat, old_val in comparisons:
                new_val = new_paces.get(cat)
                if old_val and new_val:
                    diff = new_val - old_val
                    diff_str = f"{diff:+.1f}min"
                else:
                    diff_str = "N/A"
                print(f"{cat:<20} {format_pace(old_val):>10} {format_pace(new_val):>10} {diff_str:>10}")

            print()

            # Ask to update
            print("=" * 80)
            print("UPDATE PROFILE?")
            print("=" * 80)
            print()
            print("To update the profile with smart filtering, run with --update flag")

            if "--update" in sys.argv:
                print()
                print("UPDATING PROFILE...")

                run_profile.avg_flat_pace_min_km = new_paces['flat']
                run_profile.avg_gentle_uphill_pace_min_km = new_paces['gentle_uphill']
                run_profile.avg_moderate_uphill_pace_min_km = new_paces['moderate_uphill']
                run_profile.avg_steep_uphill_pace_min_km = new_paces['steep_uphill']
                run_profile.avg_gentle_downhill_pace_min_km = new_paces['gentle_downhill']
                run_profile.avg_moderate_downhill_pace_min_km = new_paces['moderate_downhill']
                run_profile.avg_steep_downhill_pace_min_km = new_paces['steep_downhill']

                # Save sample counts for confidence assessment
                run_profile.flat_sample_count = len(splits_by_cat['flat'])
                run_profile.gentle_uphill_sample_count = len(splits_by_cat['gentle_uphill'])
                run_profile.moderate_uphill_sample_count = len(splits_by_cat['moderate_uphill'])
                run_profile.steep_uphill_sample_count = len(splits_by_cat['steep_uphill'])
                run_profile.gentle_downhill_sample_count = len(splits_by_cat['gentle_downhill'])
                run_profile.moderate_downhill_sample_count = len(splits_by_cat['moderate_downhill'])
                run_profile.steep_downhill_sample_count = len(splits_by_cat['steep_downhill'])

                run_profile.total_activities = len(set(s.activity_id for s in accepted_splits))

                db.commit()
                print("Profile updated!")


if __name__ == "__main__":
    main()
