"""Bot services."""

from services.api_client import (
    api_client,
    APIClient,
    APIError,
    GPXInfo,
    HikePrediction,
    TimeBreakdown,
    StravaStatus,
    StravaStats,
    StravaActivity,
    ActivitiesSyncStatus,
    UserProfile,
)
from services.notifications import notification_service

__all__ = [
    "api_client",
    "APIClient",
    "APIError",
    "GPXInfo",
    "HikePrediction",
    "TimeBreakdown",
    "StravaStatus",
    "StravaStats",
    "StravaActivity",
    "ActivitiesSyncStatus",
    "UserProfile",
    "notification_service",
]
