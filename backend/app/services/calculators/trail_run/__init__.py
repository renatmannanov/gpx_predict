"""
Trail Running calculators package.

Contains specialized calculators for trail running predictions:

Part 1:
- GAPCalculator: Grade Adjusted Pace for trail running

Part 2:
- HikeRunThresholdService: Determines run vs walk segments
- RunnerFatigueService: Fatigue model for runners

Part 3:
- TrailRunService: Orchestrator for all trail running components
"""

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
    # GAP Calculator (Part 1)
    'GAPCalculator',
    'GAPMode',
    'GAPResult',
    'STRAVA_GAP_TABLE',
    'compare_gap_modes',

    # Hike/Run Threshold (Part 2)
    'HikeRunThresholdService',
    'HikeRunDecision',
    'MovementMode',

    # Runner Fatigue (Part 2)
    'RunnerFatigueService',
    'RunnerFatigueConfig',
    'FATIGUE_THRESHOLD_HOURS',
    'LINEAR_DEGRADATION',
    'QUADRATIC_DEGRADATION',
    'DOWNHILL_FATIGUE_MULTIPLIER',

    # Trail Run Service (Part 3)
    'TrailRunService',
    'TrailRunResult',
    'TrailRunSummary',
    'SegmentResult',
]
