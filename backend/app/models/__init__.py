"""
Database Models

Import all models here to ensure they are registered with SQLAlchemy.

Note: Feature models are imported lazily to avoid circular imports.
Use direct imports from features/ modules when possible.
"""

from app.models.base import Base
from app.models.prediction import Prediction
from app.models.user_profile import UserPerformanceProfile
from app.models.user_run_profile import UserRunProfile
from app.models.profile_snapshot import ProfileSnapshot


# Lazy import functions to avoid circular imports
def _get_user_models():
    """Lazy import of User models."""
    from app.features.users.models import User, Notification
    return User, Notification


def _get_gpx_models():
    """Lazy import of GPX models."""
    from app.features.gpx.models import GPXFile
    return GPXFile


def _get_strava_models():
    """Lazy import of Strava models."""
    from app.features.strava.models import (
        StravaToken,
        StravaActivity,
        StravaActivitySplit,
        StravaSyncStatus,
    )
    return StravaToken, StravaActivity, StravaActivitySplit, StravaSyncStatus


# Expose as module-level attributes for backward compatibility
def __getattr__(name):
    # User models
    if name == "User":
        return _get_user_models()[0]
    if name == "Notification":
        return _get_user_models()[1]

    # GPX models
    if name == "GPXFile":
        return _get_gpx_models()

    # Strava models
    if name in ("StravaToken", "StravaActivity", "StravaActivitySplit", "StravaSyncStatus"):
        models = _get_strava_models()
        model_map = {
            "StravaToken": models[0],
            "StravaActivity": models[1],
            "StravaActivitySplit": models[2],
            "StravaSyncStatus": models[3],
        }
        return model_map[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    "ProfileSnapshot",
    "Notification",
]
