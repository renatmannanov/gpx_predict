"""
DEPRECATED: Use app.features.strava

Re-exports for backward compatibility.
"""

from app.features.strava import (
    StravaOAuth,
    StravaClient,
    StravaError,
    StravaAPIError,
    StravaAuthError,
    StravaRateLimitError,
    StravaRateLimiter,
    rate_limiter,
    exchange_authorization_code,
    refresh_access_token,
    revoke_access,
    fetch_athlete_stats,
    extract_best_efforts,
    aggregate_activities,
)
from app.features.strava.models import StravaToken

# Legacy class name alias
StravaService = StravaClient

__all__ = [
    "StravaOAuth",
    "StravaClient",
    "StravaService",  # Legacy alias
    "StravaError",
    "StravaAPIError",
    "StravaAuthError",
    "StravaRateLimitError",
    "StravaRateLimiter",
    "rate_limiter",
    "StravaToken",
    "exchange_authorization_code",
    "refresh_access_token",
    "revoke_access",
    "fetch_athlete_stats",
    "extract_best_efforts",
    "aggregate_activities",
]
