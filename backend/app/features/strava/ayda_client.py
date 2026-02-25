"""
Client for getting Strava tokens via ayda_run API.

Used as fallback when gpx_predictor doesn't have a local Strava token
for a user (e.g. user authorized through ayda_run only).
"""

import logging
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton
_ayda_client: Optional["AydaRunClient"] = None


def get_ayda_client() -> Optional["AydaRunClient"]:
    """Get or create AydaRunClient singleton (None if not configured)."""
    global _ayda_client
    if _ayda_client is not None:
        return _ayda_client
    if settings.ayda_run_api_url and settings.cross_service_api_key:
        _ayda_client = AydaRunClient(
            api_url=settings.ayda_run_api_url,
            api_key=settings.cross_service_api_key,
        )
        logger.info("AydaRunClient initialized: %s", settings.ayda_run_api_url)
    return _ayda_client


class AydaRunClient:
    """
    Gets Strava tokens through ayda_run internal API.

    Features:
    - In-memory cache (30 min TTL) to avoid redundant HTTP calls during sync
    - API key authentication via X-API-Key header
    """

    CACHE_TTL = 30 * 60  # 30 minutes

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._token_cache: dict[int, tuple[dict, float]] = {}  # telegram_id → (token_data, expires_at)

    async def get_strava_token(self, telegram_id: int) -> Optional[dict]:
        """
        Get Strava access token for user via ayda_run.

        Returns:
            {"access_token": "...", "athlete_id": 123, "scope": "..."} or None
        """
        # Check cache
        cached = self._token_cache.get(telegram_id)
        if cached:
            token_data, expires_at = cached
            if time.monotonic() < expires_at:
                return token_data

        # Fetch from ayda_run
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/api/internal/strava/token",
                    params={"telegram_id": telegram_id},
                    headers={"X-API-Key": self.api_key},
                    timeout=10.0,
                )

            if response.status_code == 200:
                token_data = response.json()
                self._token_cache[telegram_id] = (
                    token_data,
                    time.monotonic() + self.CACHE_TTL,
                )
                return token_data

            if response.status_code == 404:
                # User not found or Strava not connected — don't cache
                return None

            logger.warning(
                "ayda_run token request failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return None

        except Exception as e:
            logger.warning("ayda_run token request error: %s", e)
            return None

    def invalidate_cache(self, telegram_id: int) -> None:
        """Remove cached token for user."""
        self._token_cache.pop(telegram_id, None)
