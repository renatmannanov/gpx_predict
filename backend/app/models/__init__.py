"""
Database Models

Import all models here to ensure they are registered with SQLAlchemy.
"""

from app.models.base import Base
from app.models.user import User
from app.models.gpx import GPXFile
from app.models.prediction import Prediction
from app.models.strava_token import StravaToken
from app.models.strava_activity import StravaActivity, StravaActivitySplit, StravaSyncStatus
from app.models.user_profile import UserPerformanceProfile
from app.models.user_run_profile import UserRunProfile
from app.models.notification import Notification

__all__ = [
    "Base",
    "User",
    "GPXFile",
    "Prediction",
    "StravaToken",
    "StravaActivity",
    "StravaActivitySplit",
    "StravaSyncStatus",
    "UserPerformanceProfile",
    "UserRunProfile",
    "Notification",
]
