"""
Base types for calculators.

This module contains only dataclasses and enums with NO external imports
to avoid circular dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import math


class SegmentType(str, Enum):
    """Type of macro-segment."""
    ASCENT = "ascent"
    DESCENT = "descent"
    FLAT = "flat"


@dataclass
class MacroSegment:
    """
    A macro-segment of a route (major ascent or descent section).

    Unlike micro-segments (every 500m), these represent major
    directional changes in the route.
    """
    segment_number: int
    segment_type: SegmentType
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    start_elevation_m: float
    end_elevation_m: float

    @property
    def elevation_change_m(self) -> float:
        """Net elevation change (positive = up, negative = down)."""
        return self.elevation_gain_m - self.elevation_loss_m

    @property
    def gradient_percent(self) -> float:
        """Average gradient as percentage."""
        if self.distance_km <= 0:
            return 0.0
        return (self.elevation_change_m / (self.distance_km * 1000)) * 100

    @property
    def gradient_degrees(self) -> float:
        """Average gradient in degrees."""
        return math.degrees(math.atan(self.gradient_percent / 100))


@dataclass
class MethodResult:
    """Result from a single calculation method for a segment."""
    method_name: str
    speed_kmh: float
    time_hours: float
    formula_used: str  # Human-readable formula explanation


@dataclass
class SegmentCalculation:
    """Calculation results for one macro-segment."""
    segment: MacroSegment
    results: List[MethodResult] = field(default_factory=list)

    def get_result(self, method_name: str) -> Optional[MethodResult]:
        """Get result for a specific method."""
        for r in self.results:
            if r.method_name == method_name:
                return r
        return None


@dataclass
class CalculationResult:
    """Complete calculation result with all segments and methods."""
    segments: List[SegmentCalculation]

    # Totals by method
    totals: dict  # {"naismith": 8.2, "tobler": 5.7}

    # Route summary
    total_distance_km: float
    total_ascent_m: float
    total_descent_m: float

    def get_total(self, method_name: str) -> Optional[float]:
        """Get total time for a method."""
        return self.totals.get(method_name)
