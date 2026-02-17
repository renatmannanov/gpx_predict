"""
Test script for Phase 1: VirtualRouteBuilder

Run from backend directory:
    python -m tools.calibration.test_phase1
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

from app.db.session import AsyncSessionLocal
from tools.calibration import VirtualRouteBuilder


async def test():
    print("Testing VirtualRouteBuilder...")
    print("-" * 50)

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
            print("ERROR: No activities with splits found in database")
            return False

        print(f"Found activity: {activity.name}")
        print(f"  Strava ID: {activity.strava_id}")
        print(f"  Type: {activity.activity_type}")
        print(f"  Splits count: {len(activity.splits)}")
        print()

        # Build route
        builder = VirtualRouteBuilder()
        route = builder.build_from_activity(activity, activity.splits)

        if not route:
            print("ERROR: Failed to build route from activity")
            return False

        print("VirtualRoute built successfully!")
        print(f"  Activity: {route.activity_name}")
        print(f"  Date: {route.activity_date}")
        print(f"  Segments: {len(route.segments)}")
        print(f"  Distance: {route.total_distance_km:.1f} km")
        print(f"  D+: {route.total_elevation_gain_m:.0f} m")
        print(f"  D-: {route.total_elevation_loss_m:.0f} m")
        print(f"  Actual time: {route.actual_total_time_s / 60:.0f} min")
        print()

        print("First 5 segments:")
        for i, seg in enumerate(route.segments[:5], 1):
            print(f"  {i}. {seg.distance_m:.0f}m, {seg.gradient_percent:+.1f}%, "
                  f"elev: {seg.elevation_diff_m:+.0f}m, time: {seg.actual_time_s}s")

        print()
        print("-" * 50)
        print("Phase 1 test PASSED!")
        return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
