"""
Strava integration module.

Usage:
    from app.features.strava import StravaOAuth, StravaClient
    from app.features.strava.sync import StravaSyncService

Components:
- StravaOAuth: OAuth flow (auth URL, token exchange, refresh)
- StravaClient: API client (get athlete, activities, splits)
- StravaSyncService: Background synchronization

Models:
- StravaToken: OAuth tokens storage
- StravaActivity: Synced activity data
- StravaActivitySplit: Per-kilometer split data
- StravaSyncStatus: Sync progress tracking
"""

from .models import (
    StravaToken,
    StravaActivity,
    StravaActivitySplit,
    StravaSyncStatus,
)
from .oauth import (
    StravaOAuth,
    StravaOAuthError,
    exchange_authorization_code,
    refresh_access_token,
    revoke_access,
)
from .client import (
    StravaClient,
    StravaError,
    StravaAPIError,
    StravaAuthError,
    StravaRateLimitError,
    StravaRateLimiter,
    rate_limiter,
    fetch_athlete_stats,
    extract_best_efforts,
    aggregate_activities,
)
from .repository import (
    StravaTokenRepository,
    StravaActivityRepository,
    StravaActivitySplitRepository,
    SyncStatusRepository,
)

__all__ = [
    # Models
    "StravaToken",
    "StravaActivity",
    "StravaActivitySplit",
    "StravaSyncStatus",
    # OAuth
    "StravaOAuth",
    "StravaOAuthError",
    "exchange_authorization_code",
    "refresh_access_token",
    "revoke_access",
    # Client
    "StravaClient",
    "StravaError",
    "StravaAPIError",
    "StravaAuthError",
    "StravaRateLimitError",
    "StravaRateLimiter",
    "rate_limiter",
    "fetch_athlete_stats",
    "extract_best_efforts",
    "aggregate_activities",
    # Repositories
    "StravaTokenRepository",
    "StravaActivityRepository",
    "StravaActivitySplitRepository",
    "SyncStatusRepository",
]
