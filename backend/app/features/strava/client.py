"""
Strava API client.

Provides methods for interacting with Strava API.
Handles rate limiting, authentication, and error handling.

Strava API Limits:
- 200 requests per 15 minutes
- 2,000 requests per day
- After Developer Program approval: 30,000/day

Data Policy:
- Raw activity data can be cached for max 7 days
- Aggregated metrics can be stored indefinitely
- GPS coordinates and maps should NOT be stored
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from .models import StravaToken
from .oauth import StravaOAuth

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================

class StravaError(Exception):
    """Base Strava error."""
    pass


class StravaAPIError(StravaError):
    """Strava API error."""
    pass


class StravaAuthError(StravaError):
    """Authentication/authorization error."""
    pass


class StravaRateLimitError(StravaError):
    """Rate limit exceeded."""
    pass


# =============================================================================
# Rate Limiter
# =============================================================================

class StravaRateLimiter:
    """
    In-memory rate limiter for Strava API.

    Limits:
    - 200 requests per 15 minutes (short-term)
    - 2000 requests per day (daily)
    """

    def __init__(
        self,
        short_limit: int = 200,
        short_window_minutes: int = 15,
        daily_limit: int = 2000
    ):
        self.short_limit = short_limit
        self.short_window = timedelta(minutes=short_window_minutes)
        self.daily_limit = daily_limit

        self.short_counts: dict[str, list[datetime]] = defaultdict(list)
        self.daily_counts: dict[str, int] = defaultdict(int)
        self.daily_date: datetime.date = datetime.now().date()
        self._lock = asyncio.Lock()

    async def check_and_increment(self, key: str = "global") -> bool:
        """
        Check if request is allowed and increment counters.

        Returns True if request is allowed, False if rate limited.
        """
        async with self._lock:
            now = datetime.now()

            # Reset daily counter if new day
            if now.date() != self.daily_date:
                self.daily_counts.clear()
                self.daily_date = now.date()
                logger.info("Daily rate limit counters reset")

            # Clean old timestamps (>15 min)
            cutoff = now - self.short_window
            self.short_counts[key] = [
                ts for ts in self.short_counts[key]
                if ts > cutoff
            ]

            # Check limits
            short_count = len(self.short_counts[key])
            daily_count = self.daily_counts[key]

            if short_count >= self.short_limit:
                logger.warning(
                    f"Strava rate limit hit: {short_count}/{self.short_limit} "
                    f"requests in 15 min for {key}"
                )
                return False

            if daily_count >= self.daily_limit:
                logger.warning(
                    f"Strava daily limit hit: {daily_count}/{self.daily_limit} "
                    f"for {key}"
                )
                return False

            # Increment counters
            self.short_counts[key].append(now)
            self.daily_counts[key] += 1

            return True

    def get_usage(self, key: str = "global") -> dict:
        """Get current rate limit usage."""
        now = datetime.now()
        cutoff = now - self.short_window
        short_count = len([ts for ts in self.short_counts[key] if ts > cutoff])

        return {
            "short_term": {
                "used": short_count,
                "limit": self.short_limit,
                "window_minutes": 15
            },
            "daily": {
                "used": self.daily_counts[key],
                "limit": self.daily_limit
            }
        }


# Global rate limiter instance
rate_limiter = StravaRateLimiter()


# =============================================================================
# Strava Client
# =============================================================================

class StravaClient:
    """
    Async client for Strava API.

    Features:
    - OAuth 2.0 flow (via StravaOAuth)
    - Automatic token refresh
    - Rate limiting
    - Error handling

    Usage:
        client = StravaClient(db)
        token = await client.get_valid_token(user_id)
        athlete = await client.get_athlete(token)
        activities = await client.get_activities(token)
    """

    BASE_URL = "https://www.strava.com"
    API_URL = "https://www.strava.com/api/v3"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client_id = settings.strava_client_id
        self.client_secret = settings.strava_client_secret
        self._oauth = StravaOAuth()

    # -------------------------------------------------------------------------
    # OAuth Flow (delegated to StravaOAuth)
    # -------------------------------------------------------------------------

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        scope: str = "activity:read"
    ) -> str:
        """Generate Strava OAuth authorization URL."""
        return self._oauth.get_authorization_url(redirect_uri, state, scope)

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        return await self._oauth.exchange_code(code)

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        return await self._oauth.refresh_token(refresh_token)

    async def deauthorize(self, access_token: str) -> bool:
        """Revoke Strava access (user disconnect)."""
        return await self._oauth.deauthorize(access_token)

    # -------------------------------------------------------------------------
    # Token Management
    # -------------------------------------------------------------------------

    async def get_valid_token(self, user_id: str) -> Optional[str]:
        """
        Get a valid access token for user, refreshing if needed.

        Returns None if user has no Strava token.
        """
        result = await self.db.execute(
            select(StravaToken).where(StravaToken.user_id == user_id)
        )
        token = result.scalar_one_or_none()

        if not token:
            return None

        # Check if expired (with 5 min buffer)
        if token.expires_at < datetime.utcnow().timestamp() + 300:
            logger.info(f"Refreshing Strava token for user {user_id}")
            new_tokens = await self.refresh_token(token.refresh_token)

            token.access_token = new_tokens["access_token"]
            token.refresh_token = new_tokens["refresh_token"]
            token.expires_at = new_tokens["expires_at"]
            token.updated_at = datetime.utcnow()

            await self.db.commit()

        return token.access_token

    async def save_tokens(
        self,
        user_id: str,
        token_data: dict,
        scope: Optional[str] = None
    ) -> StravaToken:
        """
        Save or update Strava tokens for a user.

        Args:
            user_id: User ID
            token_data: Token response from Strava OAuth
            scope: OAuth scope granted

        Returns:
            StravaToken instance
        """
        from app.features.users import User

        athlete_id = str(token_data["athlete"]["id"])

        # Check if token already exists
        result = await self.db.execute(
            select(StravaToken).where(StravaToken.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.access_token = token_data["access_token"]
            existing.refresh_token = token_data["refresh_token"]
            existing.expires_at = token_data["expires_at"]
            existing.scope = scope
            existing.updated_at = datetime.utcnow()
            token = existing
        else:
            token = StravaToken(
                user_id=user_id,
                strava_athlete_id=athlete_id,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=token_data["expires_at"],
                scope=scope
            )
            self.db.add(token)

        # Update user's strava fields
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.strava_athlete_id = athlete_id
            user.strava_connected = True

        await self.db.commit()
        return token

    async def delete_tokens(self, user_id: str) -> bool:
        """
        Delete Strava tokens (disconnect).

        Returns True if tokens were deleted.
        """
        from app.features.users import User

        result = await self.db.execute(
            select(StravaToken).where(StravaToken.user_id == user_id)
        )
        token = result.scalar_one_or_none()

        if token:
            await self.db.delete(token)

            # Update user
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.strava_connected = False

            await self.db.commit()
            return True

        return False

    # -------------------------------------------------------------------------
    # API Calls
    # -------------------------------------------------------------------------

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make an authenticated API request with rate limiting.

        Raises:
            StravaRateLimitError: If rate limit exceeded
            StravaAuthError: If authentication fails
            StravaAPIError: If API returns error
        """
        # Check rate limit
        if not await rate_limiter.check_and_increment():
            raise StravaRateLimitError("Rate limit exceeded")

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.API_URL}{endpoint}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params
            )

            # Log rate limit headers from Strava
            if "X-RateLimit-Limit" in response.headers:
                logger.debug(
                    f"Strava rate limit: {response.headers.get('X-RateLimit-Usage')} "
                    f"/ {response.headers.get('X-RateLimit-Limit')}"
                )

            if response.status_code == 401:
                raise StravaAuthError("Invalid or expired token")
            elif response.status_code == 429:
                raise StravaRateLimitError("Strava rate limit exceeded")
            elif response.status_code != 200:
                raise StravaAPIError(
                    f"API error: {response.status_code} - {response.text}"
                )

            return response.json()

    async def get_athlete(self, access_token: str) -> dict:
        """Get authenticated athlete profile."""
        return await self._api_request("GET", "/athlete", access_token)

    async def get_athlete_stats(
        self,
        access_token: str,
        athlete_id: int
    ) -> dict:
        """
        Get athlete stats including best efforts.

        Returns totals and best efforts for running.
        """
        return await self._api_request(
            "GET",
            f"/athletes/{athlete_id}/stats",
            access_token
        )

    async def get_activities(
        self,
        access_token: str,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 30
    ) -> list[dict]:
        """
        Get athlete activities.

        Args:
            access_token: Valid access token
            after: Only activities after this time
            before: Only activities before this time
            page: Page number (default 1)
            per_page: Results per page (max 200)

        Note: Does NOT include GPS data in list response.
        """
        params = {"page": page, "per_page": min(per_page, 200)}

        if after:
            params["after"] = int(after.timestamp())
        if before:
            params["before"] = int(before.timestamp())

        return await self._api_request(
            "GET",
            "/athlete/activities",
            access_token,
            params
        )

    async def get_activity(
        self,
        access_token: str,
        activity_id: int,
        include_all_efforts: bool = False
    ) -> dict:
        """
        Get detailed activity info.

        WARNING: This returns GPS data - do NOT cache for >7 days!
        """
        params = {"include_all_efforts": str(include_all_efforts).lower()}
        return await self._api_request(
            "GET",
            f"/activities/{activity_id}",
            access_token,
            params
        )

    async def get_activity_with_splits(
        self,
        access_token: str,
        activity_id: int
    ) -> dict:
        """
        Get detailed activity info including splits_metric.

        Splits contain per-kilometer aggregated data:
        - distance, elapsed_time, moving_time
        - elevation_difference (key for terrain analysis!)
        - average_speed, average_heartrate
        - pace_zone

        Note: splits_metric is aggregated data (not GPS), safe to store long-term.
        """
        return await self._api_request(
            "GET",
            f"/activities/{activity_id}",
            access_token,
            params={"include_all_efforts": "false"}
        )

    def extract_splits(self, activity_data: dict) -> list[dict]:
        """
        Extract splits_metric from activity data.

        Args:
            activity_data: Full activity response from Strava API

        Returns:
            List of split dictionaries, empty if no splits available
        """
        return activity_data.get("splits_metric", [])


# =============================================================================
# Standalone API Functions (no db dependency)
# =============================================================================

async def fetch_athlete_stats(access_token: str, athlete_id: int) -> dict:
    """
    Fetch athlete stats from Strava API.

    Standalone function for use from routes.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code == 401:
            raise StravaAuthError("Invalid or expired token")
        elif response.status_code != 200:
            raise StravaAPIError(f"API error: {response.status_code}")

        return response.json()


# =============================================================================
# Helper Functions
# =============================================================================

def extract_best_efforts(stats: dict) -> dict:
    """
    Extract best efforts from athlete stats.

    These are aggregated metrics that CAN be stored indefinitely.
    """
    return {
        "total_runs": stats.get("all_run_totals", {}).get("count", 0),
        "total_distance_km": round(
            stats.get("all_run_totals", {}).get("distance", 0) / 1000, 1
        ),
        "total_elevation_m": round(
            stats.get("all_run_totals", {}).get("elevation_gain", 0), 0
        ),
        "ytd_runs": stats.get("ytd_run_totals", {}).get("count", 0),
        "ytd_distance_km": round(
            stats.get("ytd_run_totals", {}).get("distance", 0) / 1000, 1
        ),
        "recent_runs": stats.get("recent_run_totals", {}).get("count", 0),
        "recent_distance_km": round(
            stats.get("recent_run_totals", {}).get("distance", 0) / 1000, 1
        )
    }


def aggregate_activities(activities: list[dict]) -> dict:
    """
    Aggregate activity data into metrics.

    These aggregated metrics CAN be stored indefinitely.
    Does NOT store GPS data or detailed routes.
    """
    runs = [a for a in activities if a.get("type") == "Run"]
    hikes = [a for a in activities if a.get("type") == "Hike"]

    def _aggregate(activity_list: list) -> dict:
        if not activity_list:
            return {"count": 0}

        total_distance = sum(a.get("distance", 0) for a in activity_list)
        total_time = sum(a.get("moving_time", 0) for a in activity_list)
        total_elevation = sum(a.get("total_elevation_gain", 0) for a in activity_list)

        return {
            "count": len(activity_list),
            "total_distance_km": round(total_distance / 1000, 1),
            "total_time_hours": round(total_time / 3600, 1),
            "total_elevation_m": round(total_elevation, 0),
            "avg_pace_min_km": round(total_time / 60 / (total_distance / 1000), 2)
            if total_distance > 0 else None
        }

    return {
        "runs": _aggregate(runs),
        "hikes": _aggregate(hikes),
        "period_days": 180  # 6 months
    }
