"""Strava integration API client."""
import logging
from dataclasses import dataclass
from typing import Optional

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


@dataclass
class StravaStatus:
    """Strava connection status."""

    connected: bool
    athlete_id: Optional[int] = None
    scope: Optional[str] = None


@dataclass
class StravaStats:
    """Strava athlete statistics."""

    total_runs: int
    total_distance_km: float
    total_elevation_m: float
    ytd_runs: int
    ytd_distance_km: float
    recent_runs: int
    recent_distance_km: float


@dataclass
class StravaActivity:
    """Single Strava activity."""

    strava_id: int
    name: Optional[str]
    activity_type: str
    start_date: str
    distance_km: float
    moving_time_min: int
    elevation_gain_m: float
    pace_min_km: Optional[float]
    avg_heartrate: Optional[float]


@dataclass
class ActivitiesSyncStatus:
    """Sync status for activities."""

    last_sync: Optional[str]
    total_synced: int
    in_progress: bool


class StravaClient(BaseAPIClient):
    """Client for Strava integration endpoints."""

    def get_auth_url(self, telegram_id: int) -> str:
        """
        Get URL for Strava OAuth authorization.

        User should be redirected to this URL to connect Strava.
        """
        return f"{self.base_url}/api/v1/auth/strava?telegram_id={telegram_id}"

    async def get_status(self, telegram_id: int) -> StravaStatus:
        """
        Check if user has Strava connected.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            StravaStatus with connection info
        """
        try:
            data = await self._get(f"/api/v1/strava/status/{telegram_id}")
            return StravaStatus(
                connected=data.get("connected", False),
                athlete_id=data.get("athlete_id"),
                scope=data.get("scope"),
            )
        except Exception as e:
            logger.error(f"Strava status check failed: {e}")
            return StravaStatus(connected=False)

    async def get_stats(self, telegram_id: int) -> Optional[StravaStats]:
        """
        Get Strava athlete statistics.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            StravaStats or None if not connected
        """
        try:
            data = await self._get(f"/api/v1/strava/stats/{telegram_id}")
            return StravaStats(
                total_runs=data["total_runs"],
                total_distance_km=data["total_distance_km"],
                total_elevation_m=data["total_elevation_m"],
                ytd_runs=data["ytd_runs"],
                ytd_distance_km=data["ytd_distance_km"],
                recent_runs=data["recent_runs"],
                recent_distance_km=data["recent_distance_km"],
            )
        except Exception as e:
            logger.error(f"Strava stats fetch failed: {e}")
            return None

    async def disconnect(self, telegram_id: int) -> bool:
        """
        Disconnect Strava account.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            True if disconnected successfully
        """
        try:
            await self._post(f"/api/v1/strava/disconnect/{telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Strava disconnect failed: {e}")
            return False

    async def get_activities(
        self,
        telegram_id: int,
        activity_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[list[StravaActivity], int, ActivitiesSyncStatus]:
        """
        Get synced Strava activities.

        Args:
            telegram_id: User's Telegram ID
            activity_type: Filter by type (Run, Hike, Walk)
            limit: Max activities to return
            offset: Pagination offset

        Returns:
            Tuple of (activities list, total count, sync status)
        """
        params = {"limit": limit, "offset": offset}
        if activity_type:
            params["activity_type"] = activity_type

        try:
            data = await self._get(f"/api/v1/strava/activities/{telegram_id}", params=params)

            activities = [
                StravaActivity(
                    strava_id=a["strava_id"],
                    name=a.get("name"),
                    activity_type=a["activity_type"],
                    start_date=a["start_date"],
                    distance_km=a["distance_km"],
                    moving_time_min=a["moving_time_min"],
                    elevation_gain_m=a["elevation_gain_m"],
                    pace_min_km=a.get("pace_min_km"),
                    avg_heartrate=a.get("avg_heartrate"),
                )
                for a in data.get("activities", [])
            ]

            sync_status = ActivitiesSyncStatus(
                last_sync=data.get("sync_status", {}).get("last_sync"),
                total_synced=data.get("sync_status", {}).get("total_synced", 0),
                in_progress=data.get("sync_status", {}).get("in_progress", False),
            )

            return activities, data.get("total_count", 0), sync_status

        except Exception as e:
            logger.error(f"Strava activities fetch failed: {e}")
            return [], 0, ActivitiesSyncStatus(None, 0, False)

    async def trigger_sync(self, telegram_id: int, immediate: bool = True) -> bool:
        """
        Manually trigger Strava sync for a user.

        Args:
            telegram_id: User's Telegram ID
            immediate: If True, sync now. If False, add to queue.

        Returns True if sync completed/queued successfully.
        """
        params = {"immediate": "true" if immediate else "false"}

        try:
            await self._post(f"/api/v1/strava/sync/{telegram_id}", params=params)
            return True
        except Exception as e:
            logger.error(f"Strava sync trigger failed: {e}")
            return False
