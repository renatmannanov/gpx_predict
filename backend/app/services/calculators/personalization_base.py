"""
Base Personalization Service

Abstract base class for terrain-based pace personalization.
Shared logic for Hike and Run personalization services.

This module provides the foundation for applying user performance
profiles to route calculations, supporting both 3-category (legacy)
and 7-category (extended) gradient classification systems.
"""

import math
from abc import ABC, abstractmethod
from typing import List, Optional

from app.services.calculators.base import MacroSegment, MethodResult


# Gradient thresholds for terrain classification (7 categories)
# Based on Tobler's hiking function research
GRADIENT_THRESHOLDS = {
    'steep_downhill': (-100.0, -15.0),      # < -15%
    'moderate_downhill': (-15.0, -8.0),     # -15% to -8%
    'gentle_downhill': (-8.0, -3.0),        # -8% to -3%
    'flat': (-3.0, 3.0),                    # -3% to +3%
    'gentle_uphill': (3.0, 8.0),            # +3% to +8%
    'moderate_uphill': (8.0, 15.0),         # +8% to +15%
    'steep_uphill': (15.0, 100.0),          # > +15%
}

# Legacy thresholds (3 categories) - for backward compatibility
FLAT_GRADIENT_MIN = -3.0  # %
FLAT_GRADIENT_MAX = 3.0   # %

# Minimum activities required for reliable profile
MIN_ACTIVITIES_FOR_PROFILE = 1


class BasePersonalizationService(ABC):
    """
    Abstract base class for personalization services.

    Provides common logic:
    - 7-category gradient classification
    - Segment time calculation
    - Fallback to base calculator estimation
    - Profile validation pattern

    Subclasses must implement:
    - _get_pace_legacy(): Legacy 3-category pace lookup
    - _get_pace_for_category(): 7-category pace lookup
    - _get_default_speed(): Default speed when no data
    - _estimate_pace_for_gradient(): Fallback estimation (Tobler/GAP)
    - is_profile_valid(): Static profile validation
    """

    def __init__(self, use_extended_gradients: bool = False):
        """
        Initialize base personalization service.

        Args:
            use_extended_gradients: If True, use 7-category gradient system.
                                   If False, use legacy 3-category system.
        """
        self.use_extended_gradients = use_extended_gradients

    def calculate_segment(
        self,
        segment: MacroSegment,
        base_method: str = "personalized"
    ) -> MethodResult:
        """
        Calculate personalized time for a single segment.

        Uses user's actual pace data for the terrain type based on gradient.

        Args:
            segment: MacroSegment with distance and gradient data
            base_method: Base method name for result naming
                        (e.g., "tobler" -> "tobler_personalized")

        Returns:
            MethodResult with personalized speed and time
        """
        # Get pace based on segment gradient
        pace_min_km = self._get_pace_for_gradient(segment.gradient_percent)
        speed_kmh = 60 / pace_min_km if pace_min_km > 0 else self._get_default_speed()

        # Calculate time
        time_hours = segment.distance_km / speed_kmh if speed_kmh > 0 else 0.0

        # Build formula explanation
        terrain_type = self._classify_terrain(segment.gradient_percent)
        formula = self._build_formula(segment, pace_min_km, speed_kmh, time_hours, terrain_type)

        # Method name includes base method for comparison context
        method_name = f"{base_method}_personalized" if base_method != "personalized" else "personalized"

        return MethodResult(
            method_name=method_name,
            speed_kmh=round(speed_kmh, 2),
            time_hours=round(time_hours, 4),
            formula_used=formula
        )

    def calculate_route(
        self,
        segments: List[MacroSegment],
        base_method: str = "personalized"
    ) -> tuple[float, List[MethodResult]]:
        """
        Calculate total personalized time for a route.

        Args:
            segments: List of MacroSegment objects
            base_method: Base method name for result naming

        Returns:
            Tuple of (total_hours, list of segment results)
        """
        results = []
        total_hours = 0.0

        for segment in segments:
            result = self.calculate_segment(segment, base_method)
            results.append(result)
            total_hours += result.time_hours

        return total_hours, results

    def _get_pace_for_gradient(self, gradient_percent: float) -> float:
        """
        Get user's pace (min/km) for given gradient.

        Uses extended 7-category or legacy 3-category based on settings.
        Falls back to estimated pace if profile data is missing.

        Args:
            gradient_percent: Segment gradient as percentage

        Returns:
            Pace in minutes per kilometer
        """
        if self.use_extended_gradients:
            return self._get_pace_extended(gradient_percent)
        else:
            return self._get_pace_legacy(gradient_percent)

    def _get_pace_extended(self, gradient_percent: float) -> float:
        """
        Get pace using extended 7-category system.

        Falls back to estimation if profile data is missing for the category.

        Args:
            gradient_percent: Segment gradient as percentage

        Returns:
            Pace in minutes per kilometer
        """
        category = self._classify_gradient_extended(gradient_percent)
        pace = self._get_pace_for_category(category)

        if pace is not None:
            return pace

        # Fallback to base calculator estimation
        return self._estimate_pace_for_gradient(gradient_percent)

    def _classify_gradient_extended(self, gradient_percent: float) -> str:
        """
        Classify gradient into one of 7 categories.

        Args:
            gradient_percent: Gradient as percentage

        Returns:
            Category name (e.g., 'steep_uphill', 'gentle_downhill')
        """
        for category, (min_grad, max_grad) in GRADIENT_THRESHOLDS.items():
            if min_grad <= gradient_percent < max_grad:
                return category

        # Edge cases
        if gradient_percent >= 15.0:
            return 'steep_uphill'
        if gradient_percent <= -15.0:
            return 'steep_downhill'
        return 'flat'

    def _classify_terrain(self, gradient_percent: float) -> str:
        """
        Classify terrain type for formula display.

        Uses extended or legacy classification based on settings.

        Args:
            gradient_percent: Segment gradient

        Returns:
            Terrain type string for display
        """
        if self.use_extended_gradients:
            return self._classify_gradient_extended(gradient_percent)
        else:
            if gradient_percent > FLAT_GRADIENT_MAX:
                return "uphill"
            elif gradient_percent < FLAT_GRADIENT_MIN:
                return "downhill"
            return "flat"

    def _build_formula(
        self,
        segment: MacroSegment,
        pace: float,
        speed: float,
        time: float,
        terrain: str
    ) -> str:
        """
        Build formula string for result display.

        Args:
            segment: The segment being calculated
            pace: Pace in min/km
            speed: Speed in km/h
            time: Time in hours
            terrain: Terrain type string

        Returns:
            Human-readable formula explanation
        """
        return (
            f"Personal {terrain} pace: {pace:.1f} min/km = {speed:.1f} km/h, "
            f"{segment.distance_km:.2f}km / {speed:.1f}km/h = {time:.3f}h"
        )

    # === ABSTRACT METHODS (must be implemented by subclasses) ===

    @abstractmethod
    def _get_pace_legacy(self, gradient_percent: float) -> float:
        """
        Get pace using legacy 3-category system (flat, uphill, downhill).

        Args:
            gradient_percent: Segment gradient as percentage

        Returns:
            Pace in minutes per kilometer
        """
        pass

    @abstractmethod
    def _get_pace_for_category(self, category: str) -> Optional[float]:
        """
        Get pace from profile for extended gradient category.

        Args:
            category: One of the 7 gradient categories

        Returns:
            Pace in min/km, or None if not available in profile
        """
        pass

    @abstractmethod
    def _get_default_speed(self) -> float:
        """
        Get default speed when no pace data available.

        Returns:
            Default speed in km/h
        """
        pass

    @abstractmethod
    def _estimate_pace_for_gradient(self, gradient_percent: float) -> float:
        """
        Estimate pace using base calculator (Tobler for hike, GAP for run).

        Called when profile data is missing for a gradient category.

        Args:
            gradient_percent: Gradient as percentage

        Returns:
            Estimated pace in min/km
        """
        pass

    @staticmethod
    @abstractmethod
    def is_profile_valid(profile) -> bool:
        """
        Check if profile has enough data for personalization.

        Args:
            profile: User profile object

        Returns:
            True if profile is valid for personalization
        """
        pass
