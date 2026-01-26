"""
Trail running calculators.

Components:
- GAPCalculator: Grade Adjusted Pace (Strava/Minetti)
- HikeRunThresholdService: Detect when to hike vs run
- RunPersonalizationService: User-specific adjustments
- RunnerFatigueService: Fatigue modeling for runners
"""

from .gap import GAPCalculator, GAPMode, GAPResult, STRAVA_GAP_TABLE, compare_gap_modes
from .threshold import HikeRunThresholdService, HikeRunDecision, MovementMode
from .personalization import RunPersonalizationService
from .fatigue import (
    RunnerFatigueService,
    RunnerFatigueConfig,
    FATIGUE_THRESHOLD_HOURS,
    LINEAR_DEGRADATION,
    QUADRATIC_DEGRADATION,
    DOWNHILL_FATIGUE_MULTIPLIER,
)

__all__ = [
    # GAP Calculator
    "GAPCalculator",
    "GAPMode",
    "GAPResult",
    "STRAVA_GAP_TABLE",
    "compare_gap_modes",
    # Threshold
    "HikeRunThresholdService",
    "HikeRunDecision",
    "MovementMode",
    # Personalization
    "RunPersonalizationService",
    # Fatigue
    "RunnerFatigueService",
    "RunnerFatigueConfig",
    "FATIGUE_THRESHOLD_HOURS",
    "LINEAR_DEGRADATION",
    "QUADRATIC_DEGRADATION",
    "DOWNHILL_FATIGUE_MULTIPLIER",
]
