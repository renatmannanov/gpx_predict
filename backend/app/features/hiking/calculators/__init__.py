"""
Hiking time calculators.

Available calculators:
- ToblerCalculator: Tobler's Hiking Function (1993)
- NaismithCalculator: Naismith's Rule + Langmuir corrections

Personalization:
- HikePersonalizationService: Adjusts times based on Strava profile
- HikeFatigueService: Fatigue modeling for long routes
"""
from .tobler import ToblerCalculator
from .naismith import NaismithCalculator
from .personalization import HikePersonalizationService, DEFAULT_FLAT_SPEED_KMH
from .fatigue import HikeFatigueService, FatigueConfig

# Backward compatibility
from .personalization import PersonalizationService
from .fatigue import FatigueService
from .personalization_base import (
    BasePersonalizationService,
    GRADIENT_THRESHOLDS,
    MIN_ACTIVITIES_FOR_PROFILE,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
)

__all__ = [
    "ToblerCalculator",
    "NaismithCalculator",
    "HikePersonalizationService",
    "HikeFatigueService",
    "FatigueConfig",
    # Backward compatibility aliases
    "PersonalizationService",
    "FatigueService",
    # Base classes and constants
    "BasePersonalizationService",
    "GRADIENT_THRESHOLDS",
    "MIN_ACTIVITIES_FOR_PROFILE",
    "FLAT_GRADIENT_MIN",
    "FLAT_GRADIENT_MAX",
    "DEFAULT_FLAT_SPEED_KMH",
]
