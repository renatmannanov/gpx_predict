"""
Hike Personalization Service

Applies user Hike/Walk performance profile to route segments
for personalized hiking time estimation.

Inherits from BasePersonalizationService and uses Tobler's hiking
function as the fallback calculator when profile data is missing.

Activity types: Hike, Walk
"""

from typing import Optional

from app.shared.formulas import tobler_hiking_speed
from app.shared.calculator_types import EffortLevel

from app.features.hiking.models import UserHikingProfile
from app.features.hiking.calculators.personalization_base import (
    BasePersonalizationService,
    MIN_ACTIVITIES_FOR_PROFILE,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
)


# Fallback speeds for hiking (km/h) - based on Tobler's hiking function
DEFAULT_FLAT_SPEED_KMH = 5.0      # Tobler flat speed
DEFAULT_UPHILL_SPEED_KMH = 3.3   # ~18 min/km
DEFAULT_DOWNHILL_SPEED_KMH = 6.0  # ~10 min/km (optimal descent)

# Minimum samples in a gradient category for personalization
MIN_SAMPLES_FOR_CATEGORY = 5


class HikePersonalizationService(BasePersonalizationService):
    """
    Personalization service for Hike/Walk activities.

    Uses user's Strava Hike/Walk performance profile to calculate
    personalized hiking times. Falls back to Tobler's hiking function
    when profile data is missing.

    Supports both 3-category (legacy) and 7-category (extended)
    gradient classification systems.
    """

    def __init__(
        self,
        profile: UserHikingProfile,
        use_extended_gradients: bool = False,
        effort: EffortLevel = EffortLevel.MODERATE,
    ):
        """
        Initialize with user's hiking performance profile.

        Args:
            profile: UserHikingProfile with pace data from Strava Hike/Walk
            use_extended_gradients: If True, use 7-category gradient system.
                                   If False, use legacy 3-category system.
            effort: Effort level for percentile-based pace selection
        """
        super().__init__(use_extended_gradients)
        self.profile = profile
        self._effort = effort
        self.use_11_categories = bool(
            profile and getattr(profile, 'gradient_paces', None)
        )

    def _get_pace_legacy(self, gradient_percent: float) -> float:
        """
        Get pace using legacy 3-category system: flat, uphill, downhill.

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

    def _get_pace_for_category(self, category: str) -> Optional[float]:
        """
        Get pace for gradient category using percentiles (effort-based).

        Checks sample count first, then tries percentile based on effort level,
        falls back to avg pace. Supports both 11-cat (JSON) and 7-cat (legacy).

        Args:
            category: Gradient category (11-cat or 7-cat name)

        Returns:
            Pace in min/km from profile, or None to fall back to Tobler
        """
        # Check sample count — not enough data means fall back to Tobler
        sample_count = self.profile.get_sample_count_extended(category)
        if sample_count < MIN_SAMPLES_FOR_CATEGORY:
            return None

        # Try percentile first (based on effort level)
        percentile_key = self._effort.percentile_key  # "p25", "p50", "p75"
        pace = self.profile.get_percentile(category, percentile_key)
        if pace is not None:
            return pace

        # Fallback to avg (no percentiles available)
        return self.profile.get_pace_for_category(category)

    def _get_default_speed(self) -> float:
        """Default flat speed for hiking: 5 km/h (Tobler)."""
        return DEFAULT_FLAT_SPEED_KMH

    def _estimate_pace_for_gradient(self, gradient_percent: float) -> float:
        """
        Estimate pace using Tobler's hiking function, scaled by user's flat pace.

        Uses Tobler as theoretical base, then scales proportionally
        to the user's actual flat pace if available.

        Args:
            gradient_percent: Gradient as percentage

        Returns:
            Estimated pace in min/km
        """
        # Get user's flat pace as baseline
        flat_pace = self.profile.avg_flat_pace_min_km
        if flat_pace:
            flat_speed = 60 / flat_pace
        else:
            flat_speed = DEFAULT_FLAT_SPEED_KMH

        # Calculate speed using Tobler's function
        tobler_speed = tobler_hiking_speed(gradient_percent / 100)

        # Scale factor: user's flat vs Tobler's flat (5 km/h)
        scale_factor = flat_speed / 5.0

        estimated_speed = tobler_speed * scale_factor

        # Convert to pace
        return 60 / estimated_speed if estimated_speed > 0 else 60 / DEFAULT_FLAT_SPEED_KMH

    def _estimate_uphill_pace(self) -> float:
        """
        Estimate uphill pace from flat pace (legacy fallback).

        Uses Naismith-like assumption: ~50% slower on uphills.

        Returns:
            Estimated uphill pace in min/km
        """
        if self.profile.avg_flat_pace_min_km:
            return self.profile.avg_flat_pace_min_km * 1.5
        return 60 / DEFAULT_UPHILL_SPEED_KMH

    def _estimate_downhill_pace(self) -> float:
        """
        Estimate downhill pace from flat pace (legacy fallback).

        Assumes ~20% faster on moderate descents.

        Returns:
            Estimated downhill pace in min/km
        """
        if self.profile.avg_flat_pace_min_km:
            return self.profile.avg_flat_pace_min_km * 0.83
        return 60 / DEFAULT_DOWNHILL_SPEED_KMH

    @staticmethod
    def is_profile_valid(profile: Optional[UserHikingProfile]) -> bool:
        """
        Check if hiking profile has enough data for personalization.

        Requirements:
        - Profile exists
        - Has flat pace data
        - Has analyzed at least MIN_ACTIVITIES_FOR_PROFILE activities

        Args:
            profile: UserHikingProfile or None

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
    def get_profile_summary(
        profile: Optional[UserHikingProfile],
        include_extended: bool = False
    ) -> dict:
        """
        Get summary of profile data for API response.

        Args:
            profile: UserHikingProfile or None
            include_extended: Include extended 7-category data

        Returns:
            Dict with profile summary or empty dict if no profile
        """
        if not profile:
            return {}

        summary = {
            "activities_analyzed": profile.total_activities_analyzed,
            "flat_pace_min_km": profile.avg_flat_pace_min_km,
            "uphill_pace_min_km": profile.avg_uphill_pace_min_km,
            "downhill_pace_min_km": profile.avg_downhill_pace_min_km,
            "has_split_data": getattr(profile, 'has_split_data', False),
            "has_extended_gradient_data": getattr(profile, 'has_extended_gradient_data', False),
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


# =============================================================================
# Backward compatibility alias
# =============================================================================
# Existing code uses: from personalization import PersonalizationService
# This alias ensures backward compatibility without changes to imports

PersonalizationService = HikePersonalizationService
