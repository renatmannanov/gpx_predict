"""
Test script for Phase 3: Metrics Calculation

Run from backend directory:
    python -m tools.calibration.test_phase3
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from tools.calibration import RoutePredictions, SegmentPredictions
from tools.calibration.metrics import MetricsCalculator, GRADIENT_CATEGORIES


def test():
    print("Testing MetricsCalculator...")
    print("-" * 60)

    # Create mock predictions (simulating 3 trail run activities)
    predictions = [
        # Activity 1: 75 min actual, GAP methods ~5% under, hiking ~20% over
        RoutePredictions(
            activity_id=1,
            activity_name="Morning Trail Run",
            actual_time_s=4500,  # 75 min
            strava_gap=4275,     # 71.25 min (-5%)
            minetti_gap=4050,    # 67.5 min (-10%)
            strava_minetti_gap=4162,  # 69.4 min (-7.5%)
            personalized=4410,   # 73.5 min (-2%)
            tobler=5400,         # 90 min (+20%)
            naismith=5850,       # 97.5 min (+30%)
            segments=[
                SegmentPredictions(
                    segment_index=0, distance_m=1000, gradient_percent=8.0,
                    actual_time_s=450,
                    strava_gap=430, minetti_gap=410, strava_minetti_gap=420,
                    personalized=445, tobler=540, naismith=580,
                ),
                SegmentPredictions(
                    segment_index=1, distance_m=1000, gradient_percent=-5.0,
                    actual_time_s=320,
                    strava_gap=305, minetti_gap=290, strava_minetti_gap=298,
                    personalized=315, tobler=400, naismith=420,
                ),
            ],
        ),
        # Activity 2: 60 min actual
        RoutePredictions(
            activity_id=2,
            activity_name="Hill Repeats",
            actual_time_s=3600,  # 60 min
            strava_gap=3420,     # 57 min (-5%)
            minetti_gap=3240,    # 54 min (-10%)
            strava_minetti_gap=3330,  # 55.5 min (-7.5%)
            personalized=3528,   # 58.8 min (-2%)
            tobler=4320,         # 72 min (+20%)
            naismith=4680,       # 78 min (+30%)
            segments=[
                SegmentPredictions(
                    segment_index=0, distance_m=1000, gradient_percent=15.0,
                    actual_time_s=480,
                    strava_gap=456, minetti_gap=432, strava_minetti_gap=444,
                    personalized=470, tobler=576, naismith=624,
                ),
            ],
        ),
        # Activity 3: 120 min actual
        RoutePredictions(
            activity_id=3,
            activity_name="Long Mountain Run",
            actual_time_s=7200,  # 120 min
            strava_gap=6840,     # 114 min (-5%)
            minetti_gap=6480,    # 108 min (-10%)
            strava_minetti_gap=6660,  # 111 min (-7.5%)
            personalized=7056,   # 117.6 min (-2%)
            tobler=8640,         # 144 min (+20%)
            naismith=9360,       # 156 min (+30%)
            segments=[
                SegmentPredictions(
                    segment_index=0, distance_m=1000, gradient_percent=1.0,
                    actual_time_s=360,
                    strava_gap=342, minetti_gap=324, strava_minetti_gap=333,
                    personalized=353, tobler=432, naismith=468,
                ),
            ],
        ),
    ]

    calc = MetricsCalculator()

    # Test calculate_all_methods
    print("Method Metrics (across 3 activities):")
    print("-" * 60)
    print(f"{'Method':<20} | {'MAE':>8} | {'MAPE':>6} | {'Bias':>7} | {'N':>3}")
    print("-" * 60)

    metrics = calc.calculate_all_methods(predictions)

    for method, m in metrics.items():
        if m.n_samples > 0:
            bias_sign = "+" if m.bias_percent >= 0 else ""
            print(f"{method:<20} | {m.mae_minutes:>6.1f}m | {m.mape_percent:>5.1f}% | "
                  f"{bias_sign}{m.bias_percent:>5.1f}% | {m.n_samples:>3}")

    # Test gradient breakdown
    print()
    print("Gradient Breakdown:")
    print("-" * 60)

    gradient_metrics = calc.calculate_gradient_breakdown(predictions)

    for cat in ["steep_uphill", "moderate_uphill", "gentle_uphill", "flat",
                "gentle_downhill", "moderate_downhill", "steep_downhill"]:
        if cat in gradient_metrics:
            g = gradient_metrics[cat]
            strava_mape = g.method_mape.get("strava_gap", 0)
            print(f"{cat:<20} | {g.n_segments} segments | Strava MAPE: {strava_mape:.1f}%")

    # Verify expected values
    print()
    print("-" * 60)
    print("Verification:")

    strava_metrics = metrics["strava_gap"]
    print(f"  Strava GAP MAPE: {strava_metrics.mape_percent:.1f}% (expected ~5%)")
    print(f"  Strava GAP Bias: {strava_metrics.bias_percent:.1f}% (expected ~-5%)")

    tobler_metrics = metrics["tobler"]
    print(f"  Tobler MAPE: {tobler_metrics.mape_percent:.1f}% (expected ~20%)")
    print(f"  Tobler Bias: {tobler_metrics.bias_percent:.1f}% (expected ~+20%)")

    # Basic sanity checks
    assert 4 <= strava_metrics.mape_percent <= 6, f"Strava MAPE unexpected: {strava_metrics.mape_percent}"
    assert -6 <= strava_metrics.bias_percent <= -4, f"Strava Bias unexpected: {strava_metrics.bias_percent}"
    assert 19 <= tobler_metrics.mape_percent <= 21, f"Tobler MAPE unexpected: {tobler_metrics.mape_percent}"
    assert 19 <= tobler_metrics.bias_percent <= 21, f"Tobler Bias unexpected: {tobler_metrics.bias_percent}"

    print()
    print("-" * 60)
    print("Phase 3 test PASSED!")
    return True


if __name__ == "__main__":
    success = test()
    sys.exit(0 if success else 1)
