"""
Run Personalization Service

Applies user Run performance profile to trail running predictions.
Uses GAP calculator as fallback when profile data is missing or
when sample count is too low for reliable personalization.
"""

from typing import Optional

from app.features.trail_run.models import UserRunProfile
from app.features.hiking.calculators.personalization_base import (
    BasePersonalizationService,
    MIN_ACTIVITIES_FOR_PROFILE,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
)
from app.features.trail_run.calculators.gap import GAPCalculator, GAPMode
from app.shared.calculator_types import EffortLevel


# Default flat pace for runners (min/km)
DEFAULT_FLAT_PACE_MIN_KM = 6.0  # 10 km/h

# Minimum samples required per category to use personalized pace
# Below this threshold, fall back to GAP calculation
MIN_SAMPLES_FOR_CATEGORY = 5


class RunPersonalizationService(BasePersonalizationService):
    """
    Personalization service for Run/TrailRun activities.

    Uses GAP calculator (Strava mode) as fallback.
    Profile data from Strava Run/TrailRun activities.
    """

    def __init__(
        self,
        profile: UserRunProfile,
        use_extended_gradients: bool = True,  # Default True for running
        effort: EffortLevel = EffortLevel.MODERATE,
    ):
        super().__init__(use_extended_gradients)
        self.profile = profile
        self._effort = effort
        # Use 11-category system when JSON data is available
        self.use_11_categories = bool(
            profile and profile.gradient_paces
        )

        # GAP calculator for fallback
        flat_pace = profile.avg_flat_pace_min_km if profile else DEFAULT_FLAT_PACE_MIN_KM
        if flat_pace is None:
            flat_pace = DEFAULT_FLAT_PACE_MIN_KM
        self._gap_calculator = GAPCalculator(flat_pace, GAPMode.STRAVA)

    def _get_pace_legacy(self, gradient_percent: float) -> float:
        """
        Legacy mode not recommended for running.
        Falls back to extended mode.
        """
        return self._get_pace_extended(gradient_percent)

    def _get_pace_for_category(self, category: str) -> Optional[float]:
        """
        Get pace for a gradient category based on effort level.

        Uses percentile data (P25/P50/P75) when available,
        falls back to avg pace otherwise.
        Returns None (triggers GAP fallback) if insufficient data.
        """
        if not self.profile:
            return None

        # Check sample count (works for both 11-cat and 7-cat)
        sample_count = self.profile.get_sample_count_extended(category)
        if sample_count < MIN_SAMPLES_FOR_CATEGORY:
            return None  # Fall back to GAP

        # Try percentile first (based on effort level)
        percentile_key = self._effort.percentile_key  # e.g. "p25", "p50", "p75"
        pace = self.profile.get_percentile(category, percentile_key)
        if pace is not None:
            return pace

        # Fallback to avg (no percentiles available)
        return self.profile.get_pace_for_category(category)

    def _get_default_speed(self) -> float:
        """Default 10 km/h for runners."""
        return 60 / DEFAULT_FLAT_PACE_MIN_KM

    def _estimate_pace_for_gradient(self, gradient_percent: float) -> float:
        """Use GAP calculator (Strava mode) for estimation."""
        result = self._gap_calculator.calculate(gradient_percent)
        return result.adjusted_pace_min_km

    @staticmethod
    def is_profile_valid(profile: Optional[UserRunProfile]) -> bool:
        """Check if run profile has enough data."""
        if not profile:
            return False
        if not profile.avg_flat_pace_min_km:
            return False
        if profile.total_activities < MIN_ACTIVITIES_FOR_PROFILE:
            return False
        return True

    @staticmethod
    def get_profile_summary(
        profile: Optional[UserRunProfile],
        include_extended: bool = True
    ) -> dict:
        """Get summary for API response."""
        if not profile:
            return {}

        summary = {
            "activities_analyzed": profile.total_activities,
            "flat_pace_min_km": profile.avg_flat_pace_min_km,
            "walk_threshold_percent": profile.walk_threshold_percent,
            "has_profile_data": profile.has_profile_data,
            "has_extended_gradient_data": profile.has_extended_gradient_data,
        }

        if include_extended:
            summary["extended_gradients"] = {
                "steep_downhill_pace": profile.avg_steep_downhill_pace_min_km,
                "moderate_downhill_pace": profile.avg_moderate_downhill_pace_min_km,
                "gentle_downhill_pace": profile.avg_gentle_downhill_pace_min_km,
                "gentle_uphill_pace": profile.avg_gentle_uphill_pace_min_km,
                "moderate_uphill_pace": profile.avg_moderate_uphill_pace_min_km,
                "steep_uphill_pace": profile.avg_steep_uphill_pace_min_km,
            }

        return summary
