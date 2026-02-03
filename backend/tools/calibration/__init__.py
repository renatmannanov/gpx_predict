"""
Calibration tools for validating prediction accuracy.

Usage:
    python -m tools.calibration.cli backtest --user-id <user_id>
    python -m tools.calibration.cli backtest --user-id <user_id> --mode hiking
"""

from .virtual_route import VirtualRouteBuilder, VirtualRoute, VirtualSegment
from .calculators import CalculatorAdapter, RoutePredictions, SegmentPredictions
from .metrics import MetricsCalculator, MethodMetrics, GradientCategoryMetrics

__all__ = [
    "VirtualRouteBuilder",
    "VirtualRoute",
    "VirtualSegment",
    "CalculatorAdapter",
    "RoutePredictions",
    "SegmentPredictions",
    "MetricsCalculator",
    "MethodMetrics",
    "GradientCategoryMetrics",
]
