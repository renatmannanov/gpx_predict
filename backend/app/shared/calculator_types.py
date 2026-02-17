"""
Base types for calculators.

This module contains only dataclasses and enums with NO external imports
to avoid circular dependencies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import math


class SegmentType(str, Enum):
    """Type of macro-segment."""
    ASCENT = "ascent"
    DESCENT = "descent"
    FLAT = "flat"


# Configurable percentiles for effort levels.
# Can be adjusted after calibration (e.g. race → 0.20 or 0.30)
# without changing logic in calculators.
EFFORT_PERCENTILES = {
    "fast": 0.25,       # P25 — top 25% of training paces (race/asphalt)
    "moderate": 0.50,   # P50 — typical training pace
    "easy": 0.75,       # P75 — relaxed/exploratory pace
}


class EffortLevel(str, Enum):
    """Effort level for personalized predictions."""
    FAST = "fast"           # Fast — race/asphalt effort
    MODERATE = "moderate"   # Normal — typical training (default)
    EASY = "easy"           # Conservative — easy/exploratory

    @property
    def percentile_key(self) -> str:
        """Map effort level to percentile key in JSON (p25/p50/p75)."""
        pct = EFFORT_PERCENTILES[self.value]
        return f'p{int(pct * 100)}'

    @property
    def percentile_value(self) -> float:
        """Get raw percentile value (0.0-1.0) for calculations."""
        return EFFORT_PERCENTILES[self.value]


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


class PaceCalculator(ABC):
    """
    Abstract base class for pace calculators.

    Each calculator implements a different algorithm for
    estimating hiking/running time based on distance and elevation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Calculator name for display."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the method."""
        pass

    @abstractmethod
    def calculate_segment(
        self,
        segment: MacroSegment,
        profile_multiplier: float = 1.0
    ) -> MethodResult:
        """
        Calculate time for a single macro-segment.

        Args:
            segment: The macro-segment to calculate
            profile_multiplier: Multiplier from hiker profile (experience, etc.)

        Returns:
            MethodResult with speed, time, and formula used
        """
        pass

    def calculate_route(
        self,
        segments: List[MacroSegment],
        profile_multiplier: float = 1.0
    ) -> tuple:
        """
        Calculate total time for a route.

        Args:
            segments: List of macro-segments
            profile_multiplier: Multiplier from hiker profile

        Returns:
            Tuple of (total_hours, list of segment results)
        """
        results = []
        total_hours = 0.0

        for segment in segments:
            result = self.calculate_segment(segment, profile_multiplier)
            results.append(result)
            total_hours += result.time_hours

        return total_hours, results
