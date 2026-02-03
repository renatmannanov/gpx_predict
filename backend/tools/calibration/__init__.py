"""
Calibration tools for validating prediction accuracy.

Usage:
    python -m tools.calibration.cli backtest --user-id <user_id>
    python -m tools.calibration.cli backtest --user-id <user_id> --mode hiking
"""

from .virtual_route import VirtualRouteBuilder, VirtualRoute, VirtualSegment
from .calculators import CalculatorAdapter, RoutePredictions, SegmentPredictions
from .metrics import MetricsCalculator, MethodMetrics, GradientCategoryMetrics
from .service import (
    BacktestingService,
    BacktestFilters,
    BacktestReport,
    CalibrationMode,
    MODE_PRESETS,
)
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
    "CalibrationMode",
    "MODE_PRESETS",
    # Report
    "ReportGenerator",
]
