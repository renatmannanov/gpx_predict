"""
Personalization Service

Applies user performance profile to route segments for personalized time estimation.
Uses real segment data instead of guessing terrain distribution.
"""

from typing import List, Optional

from app.services.calculators.base import MacroSegment, MethodResult, SegmentType
from app.models.user_profile import UserPerformanceProfile


# Gradient thresholds for terrain classification (match UserProfileService)
FLAT_GRADIENT_MIN = -3.0  # %
FLAT_GRADIENT_MAX = 3.0   # %

# Fallback speeds when profile data is missing (km/h)
DEFAULT_FLAT_SPEED_KMH = 5.0
DEFAULT_UPHILL_SPEED_KMH = 3.3   # ~18 min/km
DEFAULT_DOWNHILL_SPEED_KMH = 6.0  # ~10 min/km

# Minimum activities required for reliable profile
MIN_ACTIVITIES_FOR_PROFILE = 1


class PersonalizationService:
    """
    Service for applying user performance profiles to route calculations.

    Works with MacroSegment data to apply personalized pace based on:
    - Flat terrain pace (gradient -3% to +3%)
    - Uphill pace (gradient > +3%)
    - Downhill pace (gradient < -3%)

    This service does NOT duplicate calculators. Instead, it provides
    an alternative time calculation using user's actual pace data.
    """

    def __init__(self, profile: UserPerformanceProfile):
        """
        Initialize with user's performance profile.

        Args:
            profile: UserPerformanceProfile with pace data from Strava
        """
        self.profile = profile

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
            base_method: Base method name for result naming (e.g., "tobler" → "tobler_personalized")

        Returns:
            MethodResult with personalized speed and time
        """
        # Get pace based on segment gradient
        pace_min_km = self._get_pace_for_gradient(segment.gradient_percent)
        speed_kmh = 60 / pace_min_km if pace_min_km > 0 else DEFAULT_FLAT_SPEED_KMH

        # Calculate time
        time_hours = segment.distance_km / speed_kmh if speed_kmh > 0 else 0.0

        # Build formula explanation
        terrain_type = self._classify_terrain(segment.gradient_percent)
        formula = (
            f"Personal {terrain_type} pace: {pace_min_km:.1f} min/km = {speed_kmh:.1f} km/h, "
            f"{segment.distance_km:.2f}km / {speed_kmh:.1f}km/h = {time_hours:.3f}h"
        )

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

        Falls back to estimated pace if profile data is missing.

        Args:
            gradient_percent: Segment gradient as percentage

        Returns:
            Pace in minutes per kilometer
        """
        if gradient_percent > FLAT_GRADIENT_MAX:
            # Uphill
            return self.profile.avg_uphill_pace_min_km or self._estimate_uphill_pace()
        elif gradient_percent < FLAT_GRADIENT_MIN:
            # Downhill
            return self.profile.avg_downhill_pace_min_km or self._estimate_downhill_pace()
        else:
            # Flat
            return self.profile.avg_flat_pace_min_km or (60 / DEFAULT_FLAT_SPEED_KMH)

    def _estimate_uphill_pace(self) -> float:
        """
        Estimate uphill pace from flat pace.

        Uses Naismith-like assumption: ~50% slower on uphills.

        Returns:
            Estimated uphill pace in min/km
        """
        if self.profile.avg_flat_pace_min_km:
            return self.profile.avg_flat_pace_min_km * 1.5
        return 60 / DEFAULT_UPHILL_SPEED_KMH

    def _estimate_downhill_pace(self) -> float:
        """
        Estimate downhill pace from flat pace.

        Assumes ~20% faster on moderate descents.

        Returns:
            Estimated downhill pace in min/km
        """
        if self.profile.avg_flat_pace_min_km:
            return self.profile.avg_flat_pace_min_km * 0.83
        return 60 / DEFAULT_DOWNHILL_SPEED_KMH

    def _classify_terrain(self, gradient_percent: float) -> str:
        """
        Classify terrain type for formula display.

        Args:
            gradient_percent: Segment gradient

        Returns:
            Terrain type string: "uphill", "downhill", or "flat"
        """
        if gradient_percent > FLAT_GRADIENT_MAX:
            return "uphill"
        elif gradient_percent < FLAT_GRADIENT_MIN:
            return "downhill"
        return "flat"

    @staticmethod
    def is_profile_valid(profile: Optional[UserPerformanceProfile]) -> bool:
        """
        Check if profile has enough data for personalization.

        Requirements:
        - Profile exists
        - Has flat pace data
        - Has analyzed at least MIN_ACTIVITIES_FOR_PROFILE activities

        Args:
            profile: UserPerformanceProfile or None

        Returns:
            True if profile is valid for personalization
        """
        if not profile:
            return False
        if not profile.avg_flat_pace_min_km:
            return False
        if profile.total_activities_analyzed < MIN_ACTIVITIES_FOR_PROFILE:
            return False
        return True

    @staticmethod
    def get_profile_summary(profile: Optional[UserPerformanceProfile]) -> dict:
        """
        Get summary of profile data for display.

        Args:
            profile: UserPerformanceProfile or None

        Returns:
            Dict with profile summary or empty dict if no profile
        """
        if not profile:
            return {}

        return {
            "activities_analyzed": profile.total_activities_analyzed,
            "flat_pace_min_km": profile.avg_flat_pace_min_km,
            "uphill_pace_min_km": profile.avg_uphill_pace_min_km,
            "downhill_pace_min_km": profile.avg_downhill_pace_min_km,
            "has_split_data": profile.has_split_data if hasattr(profile, 'has_split_data') else False,
        }
