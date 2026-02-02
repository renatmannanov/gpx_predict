"""
DEPRECATED: Use app.features.hiking.calculators or app.features.trail_run.calculators

This module re-exports for backward compatibility.
These will be removed in a future version.

Migration guide:
- from app.services.calculators import ToblerCalculator
  → from app.features.hiking.calculators import ToblerCalculator

- from app.services.calculators import GAPCalculator
  → from app.features.trail_run.calculators import GAPCalculator
"""
import warnings

warnings.warn(
    "app.services.calculators is deprecated. "
    "Use app.features.hiking.calculators or app.features.trail_run.calculators instead.",
    DeprecationWarning,
    stacklevel=2
)

# =============================================================================
# Base classes - stay here (shared between hiking and trail_run)
# =============================================================================
from app.services.calculators.base import (
    PaceCalculator,
    MacroSegment,
    SegmentType,
    MethodResult,
    CalculationResult,
    SegmentCalculation,
)

# =============================================================================
# Hiking calculators - re-export from features/hiking/calculators
# MUST come before comparison to avoid circular import
# =============================================================================
from app.features.hiking.calculators import (
    ToblerCalculator,
    NaismithCalculator,
    HikePersonalizationService,
    HikeFatigueService,
    FatigueConfig,
    # Backward compatibility aliases
    PersonalizationService,
    FatigueService,
    # Base classes and constants
    BasePersonalizationService,
    GRADIENT_THRESHOLDS,
    MIN_ACTIVITIES_FOR_PROFILE,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
)

# =============================================================================
# Trail run calculators - re-export from features/trail_run/calculators
# =============================================================================
from app.features.trail_run.calculators import (
    GAPCalculator,
    GAPMode,
    GAPResult,
    STRAVA_GAP_TABLE,
    compare_gap_modes,
    HikeRunThresholdService,
    HikeRunDecision,
    MovementMode,
    RunPersonalizationService,
    RunnerFatigueService,
    RunnerFatigueConfig,
    FATIGUE_THRESHOLD_HOURS,
    LINEAR_DEGRADATION,
    QUADRATIC_DEGRADATION,
    DOWNHILL_FATIGUE_MULTIPLIER,
)

# =============================================================================
# Segmenter
# =============================================================================
from app.features.gpx.segmenter import RouteSegmenter

# =============================================================================
# Comparison service - MUST come AFTER hiking/trail_run to avoid circular import
# (comparison.py imports from hiking/calculators)
# =============================================================================
from app.services.calculators.comparison import (
    ComparisonService,
    SegmentComparison,
    RouteComparison,
)

__all__ = [
    # Base classes (stay here)
    "PaceCalculator",
    "MacroSegment",
    "SegmentType",
    "MethodResult",
    "CalculationResult",
    "SegmentCalculation",

    # Segmenter (now in features/gpx)
    "RouteSegmenter",

    # Comparison (stays here)
    "ComparisonService",
    "SegmentComparison",
    "RouteComparison",

    # Hiking calculators (from features/hiking)
    "ToblerCalculator",
    "NaismithCalculator",
    "HikePersonalizationService",
    "HikeFatigueService",
    "FatigueConfig",
    "PersonalizationService",  # deprecated alias
    "FatigueService",  # deprecated alias
    "BasePersonalizationService",
    "GRADIENT_THRESHOLDS",
    "MIN_ACTIVITIES_FOR_PROFILE",
    "FLAT_GRADIENT_MIN",
    "FLAT_GRADIENT_MAX",

    # Trail run calculators (from features/trail_run)
    "GAPCalculator",
    "GAPMode",
    "GAPResult",
    "STRAVA_GAP_TABLE",
    "compare_gap_modes",
    "HikeRunThresholdService",
    "HikeRunDecision",
    "MovementMode",
    "RunPersonalizationService",
    "RunnerFatigueService",
    "RunnerFatigueConfig",
    "FATIGUE_THRESHOLD_HOURS",
    "LINEAR_DEGRADATION",
    "QUADRATIC_DEGRADATION",
    "DOWNHILL_FATIGUE_MULTIPLIER",
]
