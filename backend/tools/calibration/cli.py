"""
CLI interface for calibration tools.

Usage:
    python -m tools.calibration.cli backtest --user-id <user_id>
    python -m tools.calibration.cli backtest --user-id <user_id> --mode hiking
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

import click

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Import all models first to register with SQLAlchemy
from app.features.gpx.models import GPXFile  # noqa
from app.features.users.models import User  # noqa
from app.features.strava.models import StravaActivity, StravaActivitySplit  # noqa
from app.models.prediction import Prediction  # noqa
from app.features.trail_run.models import UserRunProfile  # noqa
from app.models.profile_snapshot import ProfileSnapshot  # noqa

from app.db.session import AsyncSessionLocal
from app.services.user_profile import UserProfileService
from .service import BacktestingService, BacktestFilters, CalibrationMode
from .report import ReportGenerator


@click.group()
def cli():
    """Calibration tools for GPX Predict."""
    pass


@cli.command()
@click.option("--user-id", required=True, help="User ID to analyze")
@click.option(
    "--mode",
    default="trail-run",
    type=click.Choice(["trail-run", "hiking"]),
    help="Calibration mode: trail-run (Run/TrailRun with D+>200m) or hiking (Hike only)"
)
@click.option("--min-distance", default=None, type=float, help="Override min distance in km")
@click.option("--min-elevation", default=None, type=float, help="Override min elevation gain in m")
@click.option("--limit", default=None, type=int, help="Limit number of activities")
@click.option(
    "--output",
    default="console",
    type=click.Choice(["console", "json", "csv", "all"]),
    help="Output format"
)
@click.option("--output-dir", default="./reports", help="Output directory for files")
@click.option(
    "--effort",
    default=None,
    type=click.Choice(["fast", "moderate", "easy"]),
    help="Focus on specific effort level in per-activity details (default: show all 3)"
)
def backtest(user_id, mode, min_distance, min_elevation, limit, output, output_dir, effort):
    """
    Run backtesting for a user.

    Analyzes prediction accuracy across synced activities.

    Modes:
      - trail-run: TrailRun + Run activities with D+ > 200m (default)
      - hiking: Hike activities with D+ > 100m
    """
    asyncio.run(_run_backtest(
        user_id, mode, min_distance, min_elevation, limit, output, output_dir, effort
    ))


async def _run_backtest(
    user_id: str,
    mode: str,
    min_distance: float,
    min_elevation: float,
    limit: int,
    output: str,
    output_dir: str,
    effort: str | None = None,
):
    """Async implementation of backtest command."""

    cal_mode = CalibrationMode.TRAIL_RUN if mode == "trail-run" else CalibrationMode.HIKING

    click.echo(f"Running backtesting for user: {user_id[:8]}...")
    click.echo(f"Mode: {mode}")
    if effort:
        click.echo(f"Effort focus: {effort}")

    filters = BacktestFilters(
        mode=cal_mode,
        min_distance_km=min_distance,
        min_elevation_m=min_elevation,
        limit=limit,
    )

    click.echo(f"Filters: types={filters.activity_types}, "
               f"min_dist={filters.min_distance_km}km, "
               f"min_elev={filters.min_elevation_m}m")
    if limit:
        click.echo(f"Limit: {limit} activities")
    click.echo()

    async with AsyncSessionLocal() as session:
        service = BacktestingService(session, user_id, filters)
        report = await service.run()

    if report.n_activities == 0:
        click.echo("No activities found matching filters.")
        click.echo()
        click.echo("Tips:")
        click.echo("  - Try lowering --min-elevation (e.g., --min-elevation 50)")
        click.echo("  - Try lowering --min-distance (e.g., --min-distance 3)")
        click.echo("  - Check if user has the right activity types synced")
        return

    generator = ReportGenerator()

    # Console output
    if output in ["console", "all"]:
        click.echo(generator.generate_console(report))

    # JSON output
    if output in ["json", "all"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = Path(output_dir) / f"backtest_{user_id[:8]}_{mode}_{timestamp}.json"
        generator.save_json(report, json_path)
        click.echo(f"JSON saved: {json_path}")

    # CSV output
    if output in ["csv", "all"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = Path(output_dir) / f"backtest_{user_id[:8]}_{mode}_{timestamp}.csv"
        generator.save_csv(report, csv_path)
        click.echo(f"CSV saved: {csv_path}")


@cli.command("list-activities")
@click.option("--user-id", required=True, help="User ID")
@click.option("--limit", default=20, type=int, help="Number of activities to show")
def list_activities(user_id, limit):
    """List available activities for a user."""
    asyncio.run(_list_activities(user_id, limit))


async def _list_activities(user_id: str, limit: int):
    """List activities with splits."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                StravaActivity.id,
                StravaActivity.strava_id,
                StravaActivity.name,
                StravaActivity.activity_type,
                StravaActivity.start_date,
                StravaActivity.distance_m,
                StravaActivity.elevation_gain_m,
                StravaActivity.splits_synced,
            )
            .where(StravaActivity.user_id == user_id)
            .order_by(StravaActivity.start_date.desc())
            .limit(limit)
        )

        activities = result.all()

        if not activities:
            click.echo("No activities found for this user.")
            return

        click.echo(f"Recent activities for user {user_id[:8]}...:")
        click.echo("-" * 85)
        click.echo(f"{'ID':>6} | {'Date':10} | {'Type':10} | {'Dist':>7} | {'D+':>6} | {'Splits':>6} | Name")
        click.echo("-" * 85)

        for a in activities:
            dist_km = (a.distance_m or 0) / 1000
            splits = "Yes" if a.splits_synced else "No"
            name = (a.name or "")[:30]
            date = a.start_date.strftime("%Y-%m-%d") if a.start_date else ""

            click.echo(
                f"{a.id:>6} | {date:10} | {a.activity_type:10} | "
                f"{dist_km:>6.1f}km | {a.elevation_gain_m or 0:>5.0f}m | {splits:>6} | {name}"
            )


@cli.command("recalculate-profile")
@click.option("--user-id", required=True, help="User ID")
@click.option("--reason", default="manual_recalc", help="Reason for recalculation (stored in snapshot)")
def recalculate_profile(user_id, reason):
    """
    Recalculate run profile from all synced activities.

    Saves before/after snapshots for comparison.
    """
    asyncio.run(_recalculate_profile(user_id, reason))


async def _recalculate_profile(user_id: str, reason: str):
    """Async implementation of recalculate-profile command."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Load current profile (before)
        profile_before = await UserProfileService.get_run_profile(user_id, session)

        before_data = None
        if profile_before:
            before_data = profile_before.to_dict()
            click.echo(f"Current profile: {profile_before.total_activities} activities, "
                       f"flat_pace={profile_before.avg_flat_pace_min_km}")

            # Save "before" snapshot
            snapshot_before = ProfileSnapshot(
                user_id=user_id,
                profile_type="run",
                reason=f"{reason}_before",
                profile_data=before_data,
                activities_count=profile_before.total_activities,
            )
            session.add(snapshot_before)
            await session.flush()
            click.echo(f"Snapshot saved: {reason}_before")
        else:
            click.echo("No existing run profile found. Will create new.")

        # Recalculate
        click.echo("\nRecalculating profile...")
        profile_after = await UserProfileService.calculate_run_profile_with_splits(
            user_id, session
        )

        if not profile_after:
            click.echo("ERROR: Could not calculate profile (not enough data)")
            return

        after_data = profile_after.to_dict()

        # Save "after" snapshot
        snapshot_after = ProfileSnapshot(
            user_id=user_id,
            profile_type="run",
            reason=f"{reason}_after",
            profile_data=after_data,
            activities_count=profile_after.total_activities,
        )
        session.add(snapshot_after)
        await session.commit()
        click.echo(f"Snapshot saved: {reason}_after")

        # Display diff
        click.echo(f"\nProfile recalculated for user {user_id[:8]}...")
        click.echo(f"Activities used: {profile_after.total_activities}"
                   + (f" (was {profile_before.total_activities})" if profile_before else ""))
        click.echo()

        categories = [
            ("flat", "avg_flat_pace_min_km"),
            ("gentle_uphill", "avg_gentle_uphill_pace_min_km"),
            ("moderate_uphill", "avg_moderate_uphill_pace_min_km"),
            ("steep_uphill", "avg_steep_uphill_pace_min_km"),
            ("gentle_downhill", "avg_gentle_downhill_pace_min_km"),
            ("moderate_downhill", "avg_moderate_downhill_pace_min_km"),
            ("steep_downhill", "avg_steep_downhill_pace_min_km"),
        ]

        click.echo(f"{'Category':<20} {'Before':>10} {'After':>10} {'Diff':>10}")
        click.echo("-" * 55)

        for name, field in categories:
            before_val = before_data.get(field) if before_data else None
            after_val = after_data.get(field)

            before_str = f"{before_val:.2f}" if before_val else "  -"
            after_str = f"{after_val:.2f}" if after_val else "  -"

            if before_val and after_val:
                diff = after_val - before_val
                diff_str = f"{diff:+.2f}"
                if abs(diff) > 2.0:
                    diff_str += " !"
            else:
                diff_str = ""

            click.echo(f"{name:<20} {before_str:>10} {after_str:>10} {diff_str:>10}")


if __name__ == "__main__":
    cli()
