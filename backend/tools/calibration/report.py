"""
Report generators for backtesting results.

Formats results for console, JSON, and CSV output.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .service import BacktestReport, CalibrationMode


class ReportGenerator:
    """Generate reports in various formats."""

    def generate_console(self, report: BacktestReport) -> str:
        """Generate ASCII report for console output."""

        mode_name = "Trail Running" if report.mode == CalibrationMode.TRAIL_RUN else "Hiking"

        lines = [
            "",
            "=" * 70,
            f"                BACKTESTING REPORT ({mode_name})",
            "=" * 70,
            "",
            f"User ID:        {report.user_id[:8]}...",
            f"Run at:         {report.run_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Mode:           {report.mode.value}",
            f"Activities:     {report.n_activities} (skipped: {report.n_activities_skipped})",
            f"Total distance: {report.total_distance_km:.1f} km",
            f"Total D+:       {report.total_elevation_m:.0f} m",
            f"Total time:     {report.total_actual_time_hours:.1f} hours",
            "",
        ]

        # Profile info
        p = report.profile
        if p.available:
            pace_str = f", flat pace: {p.flat_pace_min_km:.2f} min/km" if p.flat_pace_min_km else ""
            lines.append(
                f"Profile:        Available ({p.categories_filled}/{p.categories_total} categories{pace_str})"
            )
        else:
            lines.append("Profile:        Not available")

        # Filters
        f = report.filters
        lines.extend([
            "",
            f"Filters:        types={f.activity_types}, "
            f"min_dist={f.min_distance_km}km, min_elev={f.min_elevation_m}m",
        ])

        # Method metrics table - Primary methods
        lines.extend([
            "",
            "-" * 70,
            "                    PRIMARY METHODS",
            "-" * 70,
            "",
            "Method               | MAE (min) |  MAPE  |  Bias  | Samples",
            "---------------------|-----------|--------|--------|--------",
        ])

        for method in report.primary_methods:
            if method not in report.method_metrics:
                continue

            m = report.method_metrics[method]
            if m.n_samples == 0:
                continue

            name = self._format_method_name(method)
            bias_sign = "+" if m.bias_percent >= 0 else ""
            lines.append(
                f"{name:<20} | {m.mae_minutes:>9.1f} | {m.mape_percent:>5.1f}% | "
                f"{bias_sign}{m.bias_percent:>5.1f}% | {m.n_samples:>7}"
            )

        # Secondary methods (for comparison)
        if report.secondary_methods:
            lines.extend([
                "",
                "-" * 70,
                "                  SECONDARY METHODS (comparison)",
                "-" * 70,
                "",
            ])

            for method in report.secondary_methods:
                if method not in report.method_metrics:
                    continue

                m = report.method_metrics[method]
                if m.n_samples == 0:
                    continue

                name = self._format_method_name(method)
                bias_sign = "+" if m.bias_percent >= 0 else ""
                lines.append(
                    f"{name:<20} | {m.mae_minutes:>9.1f} | {m.mape_percent:>5.1f}% | "
                    f"{bias_sign}{m.bias_percent:>5.1f}% | {m.n_samples:>7}"
                )

        # Best method
        if report.best_method:
            best_m = report.method_metrics[report.best_method]
            lines.extend([
                "",
                f"Best method: {report.best_method} (MAPE {best_m.mape_percent:.1f}%)",
            ])

        # Gradient breakdown
        if report.gradient_breakdown and report.n_activities > 0:
            lines.extend([
                "",
                "-" * 70,
                "                GRADIENT BREAKDOWN (MAPE %)",
                "-" * 70,
                "",
            ])

            # Build header based on mode
            if report.mode == CalibrationMode.TRAIL_RUN:
                header_methods = ["Strava", "Minetti", "S+M", "P.Race", "P.Mod", "P.Easy"]
                method_keys = [
                    "strava_gap", "minetti_gap", "strava_minetti_gap",
                    "personalized_race", "personalized_moderate", "personalized_easy",
                ]
            else:
                header_methods = ["Tobler", "Naismith", "P.Race", "P.Mod", "P.Easy"]
                method_keys = [
                    "tobler", "naismith",
                    "personalized_race", "personalized_moderate", "personalized_easy",
                ]

            header = "Gradient         | " + " | ".join(f"{m:>7}" for m in header_methods) + " | Segments"
            lines.append(header)
            lines.append("-" * len(header))

            category_order = [
                "steep_downhill", "moderate_downhill", "gentle_downhill",
                "flat",
                "gentle_uphill", "moderate_uphill", "steep_uphill",
            ]

            category_labels = {
                "steep_downhill": "Steep down",
                "moderate_downhill": "Mod down",
                "gentle_downhill": "Gentle down",
                "flat": "Flat",
                "gentle_uphill": "Gentle up",
                "moderate_uphill": "Mod up",
                "steep_uphill": "Steep up",
            }

            for cat in category_order:
                if cat not in report.gradient_breakdown:
                    continue

                g = report.gradient_breakdown[cat]
                label = category_labels.get(cat, cat)

                values = []
                for key in method_keys:
                    mape = g.method_mape.get(key, 0)
                    values.append(f"{mape:>6.1f}%")

                lines.append(
                    f"{label:<16} | " + " | ".join(values) + f" | {g.n_segments:>8}"
                )

        # Per-activity details (first 10)
        if report.activity_results:
            lines.extend([
                "",
                "-" * 90,
                "                        PER-ACTIVITY DETAILS (first 10)",
                "-" * 90,
                "",
                "#  | Name                     | Actual | Race   | Moderate | Easy   |",
                "---|--------------------------|--------|--------|----------|--------|",
            ])

            for i, act in enumerate(report.activity_results[:10], 1):
                name = (act.activity_name or "Unnamed")[:24]
                actual_min = act.actual_time_s / 60

                def _fmt_effort(val):
                    if val is None:
                        return "   -   "
                    pred_min = val / 60
                    err = ((val - act.actual_time_s) / act.actual_time_s) * 100
                    sign = "+" if err >= 0 else ""
                    return f"{pred_min:>4.0f}m {sign}{err:>4.0f}%"

                lines.append(
                    f"{i:>2} | {name:<24} | {actual_min:>4.0f}m | "
                    f"{_fmt_effort(act.personalized_race)} | "
                    f"{_fmt_effort(act.personalized_moderate)} | "
                    f"{_fmt_effort(act.personalized_easy)} |"
                )

        lines.extend([
            "",
            "=" * 70,
        ])

        return "\n".join(lines)

    def _format_method_name(self, method: str) -> str:
        """Format method name for display."""
        names = {
            "strava_gap": "Strava GAP",
            "minetti_gap": "Minetti GAP",
            "strava_minetti_gap": "Strava+Minetti",
            "personalized_race": "Pers. Race",
            "personalized_moderate": "Pers. Moderate",
            "personalized_easy": "Pers. Easy",
            "tobler": "Tobler",
            "naismith": "Naismith",
        }
        return names.get(method, method)

    def generate_json(self, report: BacktestReport) -> dict:
        """Generate JSON-serializable dict."""
        return {
            "meta": {
                "user_id": report.user_id,
                "run_at": report.run_at.isoformat(),
                "mode": report.mode.value,
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
                "total_distance_km": report.total_distance_km,
                "total_elevation_m": report.total_elevation_m,
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
            "primary_methods": report.primary_methods,
            "secondary_methods": report.secondary_methods,
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
                "personalized_race", "personalized_moderate", "personalized_easy",
                "tobler", "naismith",
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
                    round(a.personalized_race, 1) if a.personalized_race else "",
                    round(a.personalized_moderate, 1) if a.personalized_moderate else "",
                    round(a.personalized_easy, 1) if a.personalized_easy else "",
                    round(a.tobler, 1),
                    round(a.naismith, 1),
                ])
