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
api_client = APIClient(
    settings.backend_url,
    ayda_run_api_url=settings.ayda_run_api_url,
    cross_service_api_key=settings.cross_service_api_key,
)

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
