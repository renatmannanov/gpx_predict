"""
Pace Calculators

Different algorithms for calculating hiking/running time.

Includes:
- Base classes (PaceCalculator, MacroSegment, etc.)
- Hiking calculators (Tobler, Naismith)
- Trail running calculators (GAP)
- Personalization services (Hike, with Run coming in Part 2)
- Fatigue modeling
- Comparison/orchestration services
"""

# Base classes
from app.services.calculators.base import (
    PaceCalculator,
    MacroSegment,
    SegmentType,
    MethodResult,
    CalculationResult
)

# Core calculators
from app.services.calculators.naismith import NaismithCalculator
from app.services.calculators.tobler import ToblerCalculator
from app.services.calculators.segmenter import RouteSegmenter

# Comparison service
from app.services.calculators.comparison import (
    ComparisonService,
    SegmentComparison,
    RouteComparison
)

# Personalization
from app.services.calculators.personalization_base import (
    BasePersonalizationService,
    GRADIENT_THRESHOLDS,
    MIN_ACTIVITIES_FOR_PROFILE,
)
from app.services.calculators.personalization import (
    PersonalizationService,  # Backward compatibility alias
    HikePersonalizationService,
)

# Fatigue
from app.services.calculators.fatigue import FatigueService, FatigueConfig

# Trail running
from app.services.calculators.trail_run import (
    GAPCalculator,
    GAPMode,
    GAPResult,
    STRAVA_GAP_TABLE,
    compare_gap_modes,
)

__all__ = [
    # Base
    "PaceCalculator",
    "MacroSegment",
    "SegmentType",
    "MethodResult",
    "CalculationResult",

    # Calculators
    "NaismithCalculator",
    "ToblerCalculator",
    "RouteSegmenter",

    # Comparison
    "ComparisonService",
    "SegmentComparison",
    "RouteComparison",

    # Personalization base
    "BasePersonalizationService",
    "GRADIENT_THRESHOLDS",
    "MIN_ACTIVITIES_FOR_PROFILE",

    # Hike personalization
    "PersonalizationService",      # Backward compatibility
    "HikePersonalizationService",

    # Fatigue
    "FatigueService",
    "FatigueConfig",

    # Trail running (GAP)
    "GAPCalculator",
    "GAPMode",
    "GAPResult",
    "STRAVA_GAP_TABLE",
    "compare_gap_modes",
]
