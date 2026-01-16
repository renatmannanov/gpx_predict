"""
Pace Calculators

Different algorithms for calculating hiking/running time.
"""

from app.services.calculators.base import (
    PaceCalculator,
    MacroSegment,
    SegmentType,
    MethodResult,
    CalculationResult
)
from app.services.calculators.naismith import NaismithCalculator
from app.services.calculators.tobler import ToblerCalculator
from app.services.calculators.segmenter import RouteSegmenter
from app.services.calculators.comparison import (
    ComparisonService,
    SegmentComparison,
    RouteComparison
)

__all__ = [
    "PaceCalculator",
    "MacroSegment",
    "SegmentType",
    "MethodResult",
    "CalculationResult",
    "NaismithCalculator",
    "ToblerCalculator",
    "RouteSegmenter",
    "ComparisonService",
    "SegmentComparison",
    "RouteComparison",
]
