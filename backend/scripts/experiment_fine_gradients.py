"""
Experiment: Fine-grained gradient bins for downhills.

Compare current 11-category profile vs experimental finer bins (~3%)
on two test activities: Asphalt Sky Run (494) and Irbis Race (570).
"""

import asyncio
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app.features.gpx.models import GPXFile  # noqa
from app.features.users.models import User  # noqa
from app.features.strava.models import StravaActivity, StravaActivitySplit  # noqa
from app.models.prediction import Prediction  # noqa
from app.features.trail_run.models import UserRunProfile  # noqa
from app.models.profile_snapshot import ProfileSnapshot  # noqa

from app.db.session import AsyncSessionLocal
from app.services.user_profile import filter_outliers_iqr, calculate_percentiles, PACE_MIN_THRESHOLD_RUN, PACE_MAX_THRESHOLD_RUN
from sqlalchemy import select
from sqlalchemy.orm import selectinload

USER_ID = "2f07778a-8ab2-41b2-a41b-3dfbc0c4fa16"
TEST_ACTIVITIES = [494, 570]  # Asphalt Sky Run, Irbis Race

# Experimental fine bins (~3% for downhills, keep uphills as is)
FINE_THRESHOLDS = {
    'down_50_over': (-100.0, -50.0),
    'down_50_40':   (-50.0, -40.0),
    'down_40_30':   (-40.0, -30.0),
    'down_30_23':   (-30.0, -23.0),
    'down_23_20':   (-23.0, -20.0),
    'down_20_17':   (-20.0, -17.0),
    'down_17_14':   (-17.0, -14.0),
    'down_14_12':   (-14.0, -12.0),
    'down_12_10':   (-12.0, -10.0),
    'down_10_8':    (-10.0, -8.0),
    'down_8_5':     (-8.0, -5.0),
    'down_5_3':     (-5.0, -3.0),
    'flat_3_3':     (-3.0, 3.0),
    'up_3_5':       (3.0, 5.0),
    'up_5_8':       (5.0, 8.0),
    'up_8_10':      (8.0, 10.0),
    'up_10_12':     (10.0, 12.0),
    'up_12_14':     (12.0, 14.0),
    'up_14_17':     (14.0, 17.0),
    'up_17_20':     (17.0, 20.0),
    'up_20_23':     (20.0, 23.0),
    'up_23_30':     (23.0, 30.0),
    'up_30_over':   (30.0, 100.0),
}


def classify_fine(gradient: float) -> str:
    for cat, (lo, hi) in FINE_THRESHOLDS.items():
        if lo <= gradient < hi:
            return cat
    if gradient >= 30.0:
        return 'up_30_over'
    if gradient <= -50.0:
        return 'down_50_over'
    return 'flat_3_3'


async def main():
    async with AsyncSessionLocal() as session:
        # 1. Load ALL splits for profile building
        result = await session.execute(
            select(StravaActivitySplit)
            .join(StravaActivity)
            .where(StravaActivity.user_id == USER_ID)
            .where(StravaActivity.activity_type.in_(["Run", "TrailRun", "VirtualRun"]))
        )
        all_splits = result.scalars().all()

        # Build fine profile
        fine_bins = {cat: [] for cat in FINE_THRESHOLDS}
        for s in all_splits:
            if s.gradient_percent is None or s.pace_min_km is None:
                continue
            if s.pace_min_km < PACE_MIN_THRESHOLD_RUN or s.pace_min_km > PACE_MAX_THRESHOLD_RUN:
                continue
            cat = classify_fine(s.gradient_percent)
            fine_bins[cat].append(s.pace_min_km)

        # Apply IQR + calculate avg
        fine_profile = {}
        print("=" * 90)
        print("EXPERIMENTAL FINE PROFILE (~3% bins)")
        print("=" * 90)
        print(f"{'Category':20s} {'N raw':>6} {'N IQR':>6} {'Avg':>7} {'P25':>7} {'P50':>7} {'P75':>7}")
        print("-" * 90)

        for cat in FINE_THRESHOLDS:
            paces = fine_bins[cat]
            if not paces:
                continue
            filtered = filter_outliers_iqr(paces)
            if not filtered:
                continue
            avg = mean(filtered)
            percs = calculate_percentiles(filtered)
            fine_profile[cat] = avg

            p25 = percs['p25'] if percs else avg
            p50 = percs['p50'] if percs else avg
            p75 = percs['p75'] if percs else avg

            print(f"{cat:20s} {len(paces):6d} {len(filtered):6d} {avg:7.2f} {p25:7.2f} {p50:7.2f} {p75:7.2f}")

        # Load current 11-cat profile
        result = await session.execute(
            select(UserRunProfile)
            .where(UserRunProfile.user_id == USER_ID)
        )
        profile = result.scalar_one()
        current_11cat = {}
        for cat, data in profile.gradient_paces.items():
            current_11cat[cat] = data['avg']

        # 2. Load test activities and predict
        for act_id in TEST_ACTIVITIES:
            result = await session.execute(
                select(StravaActivity)
                .options(selectinload(StravaActivity.splits))
                .where(StravaActivity.id == act_id)
            )
            activity = result.scalar_one()

            print(f"\n{'=' * 90}")
            print(f"ACTIVITY: {activity.name} (ID={act_id})")
            print(f"Distance: {activity.distance_m/1000:.1f}km, D+: {activity.elevation_gain_m:.0f}m, "
                  f"Actual: {activity.moving_time_s/60:.0f}min")
            print("=" * 90)

            splits = sorted(activity.splits, key=lambda s: s.split_number)

            total_actual = 0
            total_11cat = 0
            total_fine = 0
            total_gap = 0

            print(f"{'#':>3} {'Dist':>6} {'Grade':>7} {'Actual':>8} {'11-cat':>8} {'Fine':>8} {'Diff':>8} {'Cat (fine)':>20}")
            print("-" * 90)

            from app.features.trail_run.calculators.gap import GAPCalculator, GAPMode
            gap_calc = GAPCalculator(profile.avg_flat_pace_min_km, GAPMode.STRAVA)

            for i, s in enumerate(splits):
                if s.pace_min_km is None or s.gradient_percent is None:
                    continue

                dist_km = (s.distance_m or 1000) / 1000
                actual_time = s.moving_time_s / 60  # minutes
                total_actual += actual_time

                # 11-cat prediction
                from app.shared.gradients import classify_gradient
                cat_11 = classify_gradient(s.gradient_percent)
                pace_11 = current_11cat.get(cat_11)
                if pace_11 is None:
                    gap_result = gap_calc.calculate(s.gradient_percent)
                    pace_11 = gap_result.adjusted_pace_min_km
                time_11 = pace_11 * dist_km
                total_11cat += time_11

                # Fine prediction
                cat_fine = classify_fine(s.gradient_percent)
                pace_fine = fine_profile.get(cat_fine)
                if pace_fine is None:
                    gap_result = gap_calc.calculate(s.gradient_percent)
                    pace_fine = gap_result.adjusted_pace_min_km
                time_fine = pace_fine * dist_km
                total_fine += time_fine

                diff = time_fine - time_11

                print(f"{i+1:3d} {s.distance_m:6.0f} {s.gradient_percent:+6.1f}% "
                      f"{actual_time:8.1f} {time_11:8.1f} {time_fine:8.1f} {diff:+7.1f}m {cat_fine:>20}")

            print("-" * 90)
            err_11 = (total_11cat - total_actual) / total_actual * 100
            err_fine = (total_fine - total_actual) / total_actual * 100

            print(f"{'TOTAL':>3} {'':>6} {'':>7} {total_actual:8.1f} {total_11cat:8.1f} {total_fine:8.1f}")
            print(f"\n11-cat error:  {err_11:+.1f}%")
            print(f"Fine error:    {err_fine:+.1f}%")
            print(f"Improvement:   {abs(err_11) - abs(err_fine):+.1f}% points")


asyncio.run(main())
