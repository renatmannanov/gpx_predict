"""
Backend API Client

Backwards-compatible wrapper around the new modular clients.
"""
from config import settings
from .clients import (
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

# Global client instance
api_client = APIClient(settings.backend_url)

# Re-export for backwards compatibility
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
]
