"""
Base Pace Calculator

Abstract base class for all pace calculation methods.
Types are defined in types.py to avoid circular imports.
"""

from abc import ABC, abstractmethod
from typing import List

# Re-export types from shared for backward compatibility
from app.shared.calculator_types import (
    SegmentType,
    MacroSegment,
    MethodResult,
    SegmentCalculation,
    CalculationResult,
)


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
    ) -> tuple[float, List[MethodResult]]:
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
