"""
Hiking prediction module.

Usage:
    from app.features.hiking import UserHikingProfile, HikingProfileRepository
    from app.features.hiking.calculators import ToblerCalculator

For predictions, use app.services.prediction.PredictionService
which orchestrates both hiking and trail_run calculations.

Available components:
- UserHikingProfile: SQLAlchemy model for user's hiking profile
- HikingProfileRepository: Repository for profile data access
- ToblerCalculator, NaismithCalculator: Time calculators
- HikePersonalizationService: Personalization based on Strava
"""
from .models import UserHikingProfile
from .schemas import HikePredictRequest, HikePrediction, MethodComparison
from .repository import HikingProfileRepository

# Backward compatibility
UserPerformanceProfile = UserHikingProfile

__all__ = [
    "UserHikingProfile",
    "UserPerformanceProfile",  # deprecated alias
    "HikePredictRequest",
    "HikePrediction",
    "MethodComparison",
    # Repository
    "HikingProfileRepository",
]
