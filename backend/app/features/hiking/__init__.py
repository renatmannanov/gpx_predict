"""
Hiking prediction module.

Usage:
    from app.features.hiking import UserHikingProfile, HikingPredictionService
    from app.features.hiking.calculators import ToblerCalculator

Available components:
- UserHikingProfile: SQLAlchemy model for user's hiking profile
- HikingPredictionService: Main prediction service
- ToblerCalculator, NaismithCalculator: Time calculators
- HikePersonalizationService: Personalization based on Strava
"""
from .models import UserHikingProfile
from .schemas import HikePredictRequest, HikePrediction, MethodComparison
from .service import HikingPredictionService
from .repository import HikingProfileRepository

# Backward compatibility
UserPerformanceProfile = UserHikingProfile

__all__ = [
    "UserHikingProfile",
    "UserPerformanceProfile",  # deprecated
    "HikePredictRequest",
    "HikePrediction",
    "MethodComparison",
    "HikingPredictionService",
    # Repository
    "HikingProfileRepository",
]
