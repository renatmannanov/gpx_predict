"""
DEPRECATED: Use app.features.strava.models

Re-exports for backward compatibility.
"""

from app.features.strava.models import (
    StravaActivity,
    StravaActivitySplit,
    StravaSyncStatus,
)

__all__ = ["StravaActivity", "StravaActivitySplit", "StravaSyncStatus"]
