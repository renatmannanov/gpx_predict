# Фаза 5: Отчёты и CLI

**Статус:** Ожидает Фазу 4
**Зависимости:** Фаза 4 ✓
**Строк кода:** ~150

---

## Цель

1. Генерация красивых отчётов (console, JSON, CSV)
2. CLI интерфейс для запуска

---

## Что создаём

```
backend/tools/calibration/
├── ...
├── report.py     # NEW
└── cli.py        # NEW
```

---

## Код

### `backend/tools/calibration/report.py`

```python
"""
Report generators for backtesting results.

Formats results for console, JSON, and CSV output.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .service import BacktestReport


class ReportGenerator:
    """Generate reports in various formats."""

    def generate_console(self, report: BacktestReport) -> str:
        """Generate ASCII report for console output."""

        lines = [
            "",
            "═" * 66,
            "                    BACKTESTING REPORT",
            "═" * 66,
            "",
            f"User ID:        {report.user_id}",
            f"Run at:         {report.run_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Activities:     {report.n_activities} (skipped: {report.n_activities_skipped})",
            f"Total time:     {report.total_actual_time_hours:.1f} hours",
            "",
        ]

        # Profile info
        p = report.profile
        if p.available:
            lines.append(
                f"Profile:        ✓ Available ({p.categories_filled}/{p.categories_total} categories, "
                f"flat pace: {p.flat_pace_min_km:.2f} min/km)" if p.flat_pace_min_km else
                f"Profile:        ✓ Available ({p.categories_filled}/{p.categories_total} categories)"
            )
        else:
            lines.append("Profile:        ✗ Not available")

        # Filters
        f = report.filters
        lines.extend([
            "",
            f"Filters:        types={f.activity_types}, "
            f"min_dist={f.min_distance_km}km, min_elev={f.min_elevation_m}m",
        ])

        # Method metrics table
        lines.extend([
            "",
            "─" * 66,
            "                    OVERALL ACCURACY",
            "─" * 66,
            "",
            "Method               │ MAE (min) │  MAPE  │  Bias  │ Samples",
            "─────────────────────┼───────────┼────────┼────────┼────────",
        ])

        # Sort methods: run methods first, then hiking
        run_methods = ["strava_gap", "minetti_gap", "strava_minetti_gap", "personalized"]
        hiking_methods = ["tobler", "naismith"]

        for method in run_methods + hiking_methods:
            if method not in report.method_metrics:
                continue

            m = report.method_metrics[method]
            if m.n_samples == 0:
                continue

            # Format method name
            name = method.replace("_", " ").title()
            if method == "strava_minetti_gap":
                name = "Strava+Minetti"
            elif method == "personalized":
                name = "🎯 Personalized"

            bias_sign = "+" if m.bias_percent >= 0 else ""
            lines.append(
                f"{name:20} │ {m.mae_minutes:9.1f} │ {m.mape_percent:5.1f}% │ "
                f"{bias_sign}{m.bias_percent:5.1f}% │ {m.n_samples:7}"
            )

            # Separator before hiking methods
            if method == "personalized" and hiking_methods:
                lines.append("─────────────────────┼───────────┼────────┼────────┼────────")

        # Best method
        if report.best_method:
            lines.extend([
                "",
                f"🏆 Best method: {report.best_method} (MAPE {report.method_metrics[report.best_method].mape_percent:.1f}%)",
            ])

        # Gradient breakdown
        if report.gradient_breakdown:
            lines.extend([
                "",
                "─" * 66,
                "                GRADIENT BREAKDOWN (MAPE %)",
                "─" * 66,
                "",
                "Gradient         │ Strava │ Minetti │  S+M  │ Pers  │ Segments",
                "─────────────────┼────────┼─────────┼───────┼───────┼──────────",
            ])

            # Order categories from steep downhill to steep uphill
            category_order = [
                "steep_downhill", "moderate_downhill", "gentle_downhill",
                "flat",
                "gentle_uphill", "moderate_uphill", "steep_uphill",
            ]

            category_labels = {
                "steep_downhill": "Steep ↓ (<-15%)",
                "moderate_downhill": "Mod ↓ (-15/-8%)",
                "gentle_downhill": "Gentle ↓ (-8/-2%)",
                "flat": "Flat (-2/+2%)",
                "gentle_uphill": "Gentle ↑ (+2/+8%)",
                "moderate_uphill": "Mod ↑ (+8/+15%)",
                "steep_uphill": "Steep ↑ (>+15%)",
            }

            for cat in category_order:
                if cat not in report.gradient_breakdown:
                    continue

                g = report.gradient_breakdown[cat]
                label = category_labels.get(cat, cat)

                strava = g.method_mape.get("strava_gap", 0)
                minetti = g.method_mape.get("minetti_gap", 0)
                sm = g.method_mape.get("strava_minetti_gap", 0)
                pers = g.method_mape.get("personalized", 0)

                lines.append(
                    f"{label:16} │ {strava:5.1f}% │ {minetti:6.1f}% │ {sm:4.1f}% │ "
                    f"{pers:4.1f}% │ {g.n_segments:9}"
                )

        # Per-activity details (first 10)
        if report.activity_results:
            lines.extend([
                "",
                "─" * 66,
                "                  PER-ACTIVITY DETAILS (first 10)",
                "─" * 66,
                "",
                "#  │ Name                     │ Actual  │ Best Pred │ Error",
                "───┼──────────────────────────┼─────────┼───────────┼──────",
            ])

            best = report.best_method or "strava_gap"

            for i, act in enumerate(report.activity_results[:10], 1):
                name = act.activity_name[:24]
                actual_min = act.actual_time_s / 60
                pred_time = getattr(act, best, act.strava_gap)
                pred_min = pred_time / 60
                error_pct = ((pred_time - act.actual_time_s) / act.actual_time_s) * 100

                error_sign = "+" if error_pct >= 0 else ""

                lines.append(
                    f"{i:2} │ {name:24} │ {actual_min:6.0f}m │ {pred_min:8.0f}m │ "
                    f"{error_sign}{error_pct:4.1f}%"
                )

        lines.extend([
            "",
            "═" * 66,
        ])

        return "\n".join(lines)

    def generate_json(self, report: BacktestReport) -> dict:
        """Generate JSON-serializable dict."""
        return {
            "meta": {
                "user_id": report.user_id,
                "run_at": report.run_at.isoformat(),
                "filters": {
                    "activity_types": report.filters.activity_types,
                    "min_distance_km": report.filters.min_distance_km,
                    "min_elevation_m": report.filters.min_elevation_m,
                    "limit": report.filters.limit,
                },
            },
            "summary": {
                "n_activities": report.n_activities,
                "n_skipped": report.n_activities_skipped,
                "total_time_hours": round(report.total_actual_time_hours, 2),
            },
            "profile": {
                "available": report.profile.available,
                "categories_filled": report.profile.categories_filled,
                "flat_pace_min_km": report.profile.flat_pace_min_km,
            },
            "method_metrics": {
                method: {
                    "mae_minutes": m.mae_minutes,
                    "mape_percent": m.mape_percent,
                    "bias_percent": m.bias_percent,
                    "rmse_seconds": m.rmse_seconds,
                    "n_samples": m.n_samples,
                }
                for method, m in report.method_metrics.items()
                if m.n_samples > 0
            },
            "gradient_breakdown": {
                cat: {
                    "n_segments": g.n_segments,
                    "method_mape": g.method_mape,
                }
                for cat, g in report.gradient_breakdown.items()
            },
            "best_method": report.best_method,
            "activities": [
                {
                    "id": a.activity_id,
                    "name": a.activity_name,
                    "actual_time_s": a.actual_time_s,
                    "predictions": a.get_predictions_dict(),
                }
                for a in report.activity_results
            ],
        }

    def save_json(self, report: BacktestReport, path: Path) -> None:
        """Save report as JSON file."""
        data = self.generate_json(report)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_csv(self, report: BacktestReport, path: Path) -> None:
        """Save per-activity results as CSV."""
        import csv

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "activity_id", "name", "actual_time_s",
                "strava_gap", "minetti_gap", "strava_minetti_gap",
                "personalized", "tobler", "naismith",
            ])

            # Data
            for a in report.activity_results:
                writer.writerow([
                    a.activity_id,
                    a.activity_name,
                    a.actual_time_s,
                    round(a.strava_gap, 1),
                    round(a.minetti_gap, 1),
                    round(a.strava_minetti_gap, 1),
                    round(a.personalized, 1) if a.personalized else "",
                    round(a.tobler, 1),
                    round(a.naismith, 1),
                ])
```

### `backend/tools/calibration/cli.py`

```python
"""
CLI interface for calibration tools.

Usage:
    python -m tools.calibration.cli backtest --user-id <user_id>
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

import click

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.database import async_session
from .service import BacktestingService, BacktestFilters
from .report import ReportGenerator


@click.group()
def cli():
    """Calibration tools for GPX Predictor."""
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
def backtest(user_id, mode, min_distance, min_elevation, limit, output, output_dir):
    """
    Run backtesting for a user.

    Analyzes prediction accuracy across synced activities.

    Modes:
      - trail-run: TrailRun + Run activities with D+ > 200m (default)
      - hiking: Hike activities with D+ > 100m
    """
    asyncio.run(_run_backtest(
        user_id, mode, min_distance, min_elevation, limit, output, output_dir
    ))


async def _run_backtest(
    user_id: str,
    min_distance: float,
    min_elevation: float,
    limit: int,
    output: str,
    output_dir: str,
):
    """Async implementation of backtest command."""

    click.echo(f"Running backtesting for user: {user_id}")
    click.echo(f"Filters: min_distance={min_distance}km, min_elevation={min_elevation}m")
    if limit:
        click.echo(f"Limit: {limit} activities")
    click.echo()

    filters = BacktestFilters(
        activity_types=["Run", "TrailRun"],
        min_distance_km=min_distance,
        min_elevation_m=min_elevation,
        limit=limit,
    )

    async with async_session() as session:
        service = BacktestingService(session, user_id, filters)
        report = await service.run()

    if report.n_activities == 0:
        click.echo("No activities found matching filters.")
        return

    generator = ReportGenerator()

    # Console output
    if output in ["console", "all"]:
        click.echo(generator.generate_console(report))

    # JSON output
    if output in ["json", "all"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = Path(output_dir) / f"backtest_{user_id[:8]}_{timestamp}.json"
        generator.save_json(report, json_path)
        click.echo(f"JSON saved: {json_path}")

    # CSV output
    if output in ["csv", "all"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = Path(output_dir) / f"backtest_{user_id[:8]}_{timestamp}.csv"
        generator.save_csv(report, csv_path)
        click.echo(f"CSV saved: {csv_path}")


@cli.command()
@click.option("--user-id", required=True, help="User ID")
def list_activities(user_id):
    """List available activities for a user."""
    asyncio.run(_list_activities(user_id))


async def _list_activities(user_id: str):
    """List activities with splits."""
    from sqlalchemy import select, func
    from app.features.strava.models import StravaActivity

    async with async_session() as session:
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
            .limit(20)
        )

        activities = result.all()

        if not activities:
            click.echo("No activities found for this user.")
            return

        click.echo(f"Recent activities for user {user_id[:8]}...:")
        click.echo("-" * 80)
        click.echo(f"{'ID':>6} │ {'Date':10} │ {'Type':10} │ {'Dist':>7} │ {'D+':>6} │ {'Splits':>6} │ Name")
        click.echo("-" * 80)

        for a in activities:
            dist_km = (a.distance_m or 0) / 1000
            splits = "✓" if a.splits_synced else "✗"
            name = (a.name or "")[:30]
            date = a.start_date.strftime("%Y-%m-%d") if a.start_date else ""

            click.echo(
                f"{a.id:>6} │ {date:10} │ {a.activity_type:10} │ "
                f"{dist_km:>6.1f}km │ {a.elevation_gain_m or 0:>5.0f}m │ {splits:>6} │ {name}"
            )


if __name__ == "__main__":
    cli()
```

---

## Обновить `__init__.py`

```python
"""Calibration tools for validating prediction accuracy."""

from .virtual_route import VirtualRouteBuilder, VirtualRoute, VirtualSegment
from .calculators import CalculatorAdapter, RoutePredictions, SegmentPredictions
from .metrics import MetricsCalculator, MethodMetrics, GradientCategoryMetrics
from .service import BacktestingService, BacktestFilters, BacktestReport
from .report import ReportGenerator

__all__ = [
    # Virtual route
    "VirtualRouteBuilder",
    "VirtualRoute",
    "VirtualSegment",
    # Calculators
    "CalculatorAdapter",
    "RoutePredictions",
    "SegmentPredictions",
    # Metrics
    "MetricsCalculator",
    "MethodMetrics",
    "GradientCategoryMetrics",
    # Service
    "BacktestingService",
    "BacktestFilters",
    "BacktestReport",
    # Report
    "ReportGenerator",
]
```

---

## Использование

```bash
# Из директории backend/
cd backend

# Trail running калибровка (по умолчанию)
python -m tools.calibration.cli backtest --user-id abc-123-def

# Явно указать режим trail-run
python -m tools.calibration.cli backtest --user-id abc-123-def --mode trail-run

# Hiking калибровка
python -m tools.calibration.cli backtest --user-id abc-123-def --mode hiking

# С переопределением фильтров
python -m tools.calibration.cli backtest \
    --user-id abc-123-def \
    --mode trail-run \
    --min-elevation 300 \
    --limit 15

# Экспорт в JSON
python -m tools.calibration.cli backtest \
    --user-id abc-123-def \
    --mode trail-run \
    --output json \
    --output-dir ./reports

# Экспорт всё (console + json + csv)
python -m tools.calibration.cli backtest \
    --user-id abc-123-def \
    --output all

# Список активностей
python -m tools.calibration.cli list-activities --user-id abc-123-def
```

---

## Проверка

1. Запустить `backtest` — должен вывести отчёт в консоль
2. Запустить с `--output json` — должен создать JSON файл
3. Запустить с `--output csv` — должен создать CSV файл
4. Проверить `list-activities` — должен показать список

---

## Чеклист

- [ ] `report.py` создан
- [ ] `cli.py` создан
- [ ] `__init__.py` финально обновлён
- [ ] `backtest` команда работает
- [ ] Console report выглядит хорошо
- [ ] JSON export работает
- [ ] CSV export работает
- [ ] `list-activities` работает
