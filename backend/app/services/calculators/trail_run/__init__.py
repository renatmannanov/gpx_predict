"""
DEPRECATED: Use app.features.trail_run

Re-exports for backward compatibility.
These will be removed in a future version.
"""

# Import from local files (old location) for backward compatibility
# This avoids circular import issues during the transition period
from .gap_calculator import (
    GAPCalculator,
    GAPMode,
    GAPResult,
    STRAVA_GAP_TABLE,
    compare_gap_modes,
)

from .hike_run_threshold import (
    HikeRunThresholdService,
    HikeRunDecision,
    MovementMode,
)

from .runner_fatigue import (
    RunnerFatigueService,
    RunnerFatigueConfig,
    FATIGUE_THRESHOLD_HOURS,
    LINEAR_DEGRADATION,
    QUADRATIC_DEGRADATION,
    DOWNHILL_FATIGUE_MULTIPLIER,
)

from .trail_run_service import (
    TrailRunService,
    TrailRunResult,
    TrailRunSummary,
    SegmentResult,
)

__all__ = [
    # Service
    "TrailRunService",
    "TrailRunResult",
    "TrailRunSummary",
    "SegmentResult",
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
    # Fatigue
    "RunnerFatigueService",
    "RunnerFatigueConfig",
    "FATIGUE_THRESHOLD_HOURS",
    "LINEAR_DEGRADATION",
    "QUADRATIC_DEGRADATION",
    "DOWNHILL_FATIGUE_MULTIPLIER",
]
