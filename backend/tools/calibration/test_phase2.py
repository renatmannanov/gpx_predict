"""
Test script for Phase 2: Calculator Adapters

Run from backend directory:
    python -m tools.calibration.test_phase2
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Import all models first to register with SQLAlchemy
from app.features.gpx.models import GPXFile  # noqa
from app.features.users.models import User  # noqa
from app.features.strava.models import StravaActivity, StravaActivitySplit  # noqa
from app.models.prediction import Prediction  # noqa
from app.features.trail_run.models import UserRunProfile  # noqa

from app.db.session import AsyncSessionLocal
from tools.calibration import VirtualRouteBuilder, CalculatorAdapter


def format_time(seconds: float) -> str:
    """Format seconds as Xh Ym or Ym Zs."""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m:02d}m"
    else:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s:02d}s"


async def test():
    print("Testing CalculatorAdapter...")
    print("-" * 60)

    async with AsyncSessionLocal() as session:
        # Get first activity with splits
        result = await session.execute(
            select(StravaActivity)
            .options(selectinload(StravaActivity.splits))
            .where(StravaActivity.splits_synced == 1)
            .limit(1)
        )
        activity = result.scalar_one_or_none()

        if not activity:
            print("ERROR: No activities with splits found")
            return False

        print(f"Activity: {activity.name}")
        print(f"User ID: {activity.user_id}")
        print()

        # Try to get user's run profile
        profile_result = await session.execute(
            select(UserRunProfile)
            .where(UserRunProfile.user_id == activity.user_id)
        )
        profile = profile_result.scalar_one_or_none()

        if profile:
            print(f"Profile found: flat pace = {profile.avg_flat_pace_min_km:.2f} min/km")
        else:
            print("No profile found, using default flat pace")
        print()

        # Build route
        builder = VirtualRouteBuilder()
        route = builder.build_from_activity(activity, activity.splits)

        if not route:
            print("ERROR: Failed to build route")
            return False

        # Calculate predictions
        adapter = CalculatorAdapter(run_profile=profile)
        predictions = adapter.calculate_route(route)

        # Print results
        actual = predictions.actual_time_s
        print(f"Route: {route.total_distance_km:.1f} km, "
              f"D+ {route.total_elevation_gain_m:.0f}m, "
              f"D- {route.total_elevation_loss_m:.0f}m")
        print()

        print(f"Actual time:        {format_time(actual)}")
        print()
        print("Predictions:")
        print(f"  Strava GAP:       {format_time(predictions.strava_gap):>10} "
              f"({(predictions.strava_gap - actual) / actual * 100:+.1f}%)")
        print(f"  Minetti GAP:      {format_time(predictions.minetti_gap):>10} "
              f"({(predictions.minetti_gap - actual) / actual * 100:+.1f}%)")
        print(f"  Strava+Minetti:   {format_time(predictions.strava_minetti_gap):>10} "
              f"({(predictions.strava_minetti_gap - actual) / actual * 100:+.1f}%)")

        if predictions.personalized is not None:
            print(f"  Personalized:     {format_time(predictions.personalized):>10} "
                  f"({(predictions.personalized - actual) / actual * 100:+.1f}%)")

        print(f"  Tobler (hiking):  {format_time(predictions.tobler):>10} "
              f"({(predictions.tobler - actual) / actual * 100:+.1f}%)")
        print(f"  Naismith (hiking):{format_time(predictions.naismith):>10} "
              f"({(predictions.naismith - actual) / actual * 100:+.1f}%)")

        print()
        print(f"Segments analyzed: {len(predictions.segments)}")

        # Show first 3 segment details
        print()
        print("First 3 segments (actual vs strava_gap):")
        for seg in predictions.segments[:3]:
            actual_s = seg.actual_time_s
            pred_s = seg.strava_gap
            error = (pred_s - actual_s) / actual_s * 100
            print(f"  #{seg.segment_index + 1}: {seg.distance_m:.0f}m, {seg.gradient_percent:+.1f}% | "
                  f"actual: {actual_s}s, pred: {pred_s:.0f}s ({error:+.1f}%)")

        print()
        print("-" * 60)
        print("Phase 2 test PASSED!")
        return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
