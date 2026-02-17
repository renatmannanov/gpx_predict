"""
Test script for Phase 4: BacktestingService

Run from backend directory:
    python -m tools.calibration.test_phase4
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

# Import all models first to register with SQLAlchemy
from app.features.gpx.models import GPXFile  # noqa
from app.features.users.models import User  # noqa
from app.features.strava.models import StravaActivity, StravaActivitySplit  # noqa
from app.models.prediction import Prediction  # noqa
from app.features.trail_run.models import UserRunProfile  # noqa

from app.db.session import AsyncSessionLocal
from tools.calibration import (
    BacktestingService,
    BacktestFilters,
    CalibrationMode,
)


def format_time(seconds: float) -> str:
    """Format seconds as Xh Ym."""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m:02d}m"
    else:
        m = int(seconds // 60)
        return f"{m}m"


async def test():
    print("Testing BacktestingService...")
    print("=" * 70)

    async with AsyncSessionLocal() as session:
        # First, find a user with activities
        result = await session.execute(
            select(StravaActivity.user_id)
            .where(StravaActivity.splits_synced == 1)
            .distinct()
            .limit(1)
        )
        user_row = result.first()

        if not user_row:
            print("ERROR: No users with synced activities found")
            return False

        user_id = user_row[0]
        print(f"User ID: {user_id}")
        print()

        # Test 1: Trail Run mode (default)
        print("-" * 70)
        print("TEST 1: Trail Run Mode")
        print("-" * 70)

        filters = BacktestFilters(
            mode=CalibrationMode.TRAIL_RUN,
            limit=10,  # Limit for testing
        )

        print(f"Filters: types={filters.activity_types}, "
              f"min_dist={filters.min_distance_km}km, "
              f"min_elev={filters.min_elevation_m}m")

        service = BacktestingService(session, user_id, filters)
        report = await service.run()

        print(f"Activities found: {report.n_activities} (skipped: {report.n_activities_skipped})")
        print(f"Total distance: {report.total_distance_km:.1f} km")
        print(f"Total elevation: {report.total_elevation_m:.0f} m")
        print(f"Profile available: {report.profile.available}")
        if report.profile.available:
            print(f"  Flat pace: {report.profile.flat_pace_min_km:.2f} min/km")
            print(f"  Categories: {report.profile.categories_filled}/7")
        print()

        if report.n_activities > 0:
            print("Primary methods (trail-run):")
            for method in report.primary_methods:
                if method in report.method_metrics:
                    m = report.method_metrics[method]
                    if m.n_samples > 0:
                        bias_sign = "+" if m.bias_percent >= 0 else ""
                        print(f"  {method:<20} | MAPE: {m.mape_percent:>5.1f}% | "
                              f"Bias: {bias_sign}{m.bias_percent:>5.1f}%")

            print()
            print(f"Best method: {report.best_method}")
        else:
            print("No trail run activities matching filters found.")
            print("(This is OK if user only has flat runs or no TrailRun activities)")

        # Test 2: Hiking mode
        print()
        print("-" * 70)
        print("TEST 2: Hiking Mode")
        print("-" * 70)

        filters_hiking = BacktestFilters(
            mode=CalibrationMode.HIKING,
            limit=10,
        )

        print(f"Filters: types={filters_hiking.activity_types}, "
              f"min_dist={filters_hiking.min_distance_km}km, "
              f"min_elev={filters_hiking.min_elevation_m}m")

        service_hiking = BacktestingService(session, user_id, filters_hiking)
        report_hiking = await service_hiking.run()

        print(f"Activities found: {report_hiking.n_activities} (skipped: {report_hiking.n_activities_skipped})")

        if report_hiking.n_activities > 0:
            print()
            print("Primary methods (hiking):")
            for method in report_hiking.primary_methods:
                if method in report_hiking.method_metrics:
                    m = report_hiking.method_metrics[method]
                    if m.n_samples > 0:
                        bias_sign = "+" if m.bias_percent >= 0 else ""
                        print(f"  {method:<20} | MAPE: {m.mape_percent:>5.1f}% | "
                              f"Bias: {bias_sign}{m.bias_percent:>5.1f}%")

            print()
            print(f"Best method: {report_hiking.best_method}")
        else:
            print("No hiking activities found (this is expected if user doesn't hike)")

        # Test 3: Check filter override
        print()
        print("-" * 70)
        print("TEST 3: Custom filter override")
        print("-" * 70)

        filters_custom = BacktestFilters(
            mode=CalibrationMode.TRAIL_RUN,
            min_elevation_m=50.0,  # Lower threshold
            min_distance_km=3.0,   # Lower threshold
            limit=5,
        )

        print(f"Filters: min_elev={filters_custom.min_elevation_m}m (overridden from 200m)")

        service_custom = BacktestingService(session, user_id, filters_custom)
        report_custom = await service_custom.run()

        print(f"Activities found: {report_custom.n_activities}")

        print()
        print("=" * 70)
        print("Phase 4 test PASSED!")
        return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
