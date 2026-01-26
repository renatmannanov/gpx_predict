"""
Database Models

Import all models here to ensure they are registered with SQLAlchemy.

Note: Strava models are imported lazily to avoid circular imports.
Use `from app.features.strava.models import ...` for direct imports.
"""

from app.models.base import Base
from app.models.user import User
from app.models.gpx import GPXFile
from app.models.prediction import Prediction
from app.models.user_profile import UserPerformanceProfile
from app.models.user_run_profile import UserRunProfile
from app.models.notification import Notification


def _get_strava_models():
    """Lazy import of Strava models to avoid circular imports."""
    from app.features.strava.models import (
        StravaToken,
        StravaActivity,
        StravaActivitySplit,
        StravaSyncStatus,
    )
    return StravaToken, StravaActivity, StravaActivitySplit, StravaSyncStatus


# Expose as module-level attributes for backward compatibility
def __getattr__(name):
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
    "Notification",
]
