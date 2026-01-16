"""
Backend API Client

HTTP client for communicating with the backend API.
"""

import logging
from typing import Optional
from dataclasses import dataclass

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class StravaStatus:
    """Strava connection status."""
    connected: bool
    athlete_id: Optional[str] = None
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


@dataclass
class GPXInfo:
    """GPX file information."""
    gpx_id: str
    filename: str
    name: Optional[str]
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_elevation_m: float
    min_elevation_m: float
    is_loop: bool = False


@dataclass
class TimeBreakdown:
    """Breakdown of estimated time."""
    moving_time_hours: float
    rest_time_hours: float
    lunch_time_hours: float


@dataclass
class HikePrediction:
    """Hike prediction result."""
    estimated_time_hours: float
    safe_time_hours: float
    recommended_start: str
    recommended_turnaround: Optional[str]
    warnings: list
    experience_multiplier: float
    backpack_multiplier: float
    group_multiplier: float
    total_multiplier: float
    time_breakdown: Optional[TimeBreakdown] = None


class APIError(Exception):
    """API error."""
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"API error {status}: {detail}")


class APIClient:
    """Client for backend API."""

    def __init__(self):
        self.base_url = settings.backend_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def upload_gpx(self, filename: str, content: bytes) -> GPXInfo:
        """
        Upload a GPX file to the backend.

        Args:
            filename: Original filename
            content: File content as bytes

        Returns:
            GPXInfo with file metadata

        Raises:
            APIError: If upload fails
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/gpx/upload"

        form = aiohttp.FormData()
        form.add_field(
            "file",
            content,
            filename=filename,
            content_type="application/gpx+xml"
        )

        logger.info(f"Uploading GPX: {filename}")

        async with session.post(url, data=form) as resp:
            data = await resp.json()

            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                logger.error(f"Upload failed: {resp.status} - {detail}")
                raise APIError(resp.status, detail)

            info = data["info"]
            return GPXInfo(
                gpx_id=data["gpx_id"],
                filename=info["filename"],
                name=info.get("name"),
                distance_km=info["distance_km"],
                elevation_gain_m=info["elevation_gain_m"],
                elevation_loss_m=info["elevation_loss_m"],
                max_elevation_m=info["max_elevation_m"],
                min_elevation_m=info["min_elevation_m"],
                is_loop=info.get("is_loop", False),
            )

    async def predict_hike(
        self,
        gpx_id: str,
        experience: str = "casual",
        backpack: str = "medium",
        group_size: int = 1,
        has_children: bool = False,
        has_elderly: bool = False,
        is_round_trip: bool = False,
    ) -> HikePrediction:
        """
        Get hike prediction from backend.

        Args:
            gpx_id: ID of uploaded GPX file
            experience: Experience level
            backpack: Backpack weight
            group_size: Number of people
            has_children: Has children in group
            has_elderly: Has elderly in group
            is_round_trip: If route is out-and-back

        Returns:
            HikePrediction with time estimates

        Raises:
            APIError: If prediction fails
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/predict/hike"

        payload = {
            "gpx_id": gpx_id,
            "experience": experience,
            "backpack": backpack,
            "group_size": group_size,
            "has_children": has_children,
            "has_elderly": has_elderly,
            "is_round_trip": is_round_trip,
        }

        logger.info(f"Requesting prediction for GPX: {gpx_id}")

        async with session.post(url, json=payload) as resp:
            data = await resp.json()

            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                logger.error(f"Prediction failed: {resp.status} - {detail}")
                raise APIError(resp.status, detail)

            # Parse time breakdown
            time_breakdown = None
            if data.get("time_breakdown"):
                tb = data["time_breakdown"]
                time_breakdown = TimeBreakdown(
                    moving_time_hours=tb["moving_time_hours"],
                    rest_time_hours=tb["rest_time_hours"],
                    lunch_time_hours=tb["lunch_time_hours"],
                )

            return HikePrediction(
                estimated_time_hours=data["estimated_time_hours"],
                safe_time_hours=data["safe_time_hours"],
                recommended_start=data["recommended_start"],
                recommended_turnaround=data.get("recommended_turnaround"),
                warnings=data.get("warnings", []),
                experience_multiplier=data.get("experience_multiplier", 1.0),
                backpack_multiplier=data.get("backpack_multiplier", 1.0),
                group_multiplier=data.get("group_multiplier", 1.0),
                total_multiplier=data.get("total_multiplier", 1.0),
                time_breakdown=time_breakdown,
            )

    async def compare_methods(
        self,
        gpx_id: str,
        experience: str = "regular",
        backpack: str = "light",
        group_size: int = 1,
    ) -> dict:
        """
        Compare different prediction methods on a route.

        Args:
            gpx_id: ID of uploaded GPX file
            experience: Experience level
            backpack: Backpack weight
            group_size: Number of people

        Returns:
            RouteComparison with segment breakdown and totals

        Raises:
            APIError: If comparison fails
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/predict/compare"

        payload = {
            "gpx_id": gpx_id,
            "experience": experience,
            "backpack": backpack,
            "group_size": group_size,
        }

        logger.info(f"Requesting comparison for GPX: {gpx_id}")

        async with session.post(url, json=payload) as resp:
            data = await resp.json()

            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                logger.error(f"Comparison failed: {resp.status} - {detail}")
                raise APIError(resp.status, detail)

            return data

    async def health_check(self) -> bool:
        """Check if backend is healthy."""
        session = await self._get_session()
        url = f"{self.base_url}/health"

        try:
            async with session.get(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    # =========================================================================
    # Strava Integration
    # =========================================================================

    def get_strava_auth_url(self, telegram_id: str) -> str:
        """
        Get URL for Strava OAuth authorization.

        User should be redirected to this URL to connect Strava.
        """
        return f"{self.base_url}/api/v1/auth/strava?telegram_id={telegram_id}"

    async def get_strava_status(self, telegram_id: str) -> StravaStatus:
        """
        Check if user has Strava connected.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            StravaStatus with connection info
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/strava/status/{telegram_id}"

        try:
            async with session.get(url) as resp:
                data = await resp.json()

                if resp.status != 200:
                    return StravaStatus(connected=False)

                return StravaStatus(
                    connected=data.get("connected", False),
                    athlete_id=data.get("athlete_id"),
                    scope=data.get("scope"),
                )
        except Exception as e:
            logger.error(f"Strava status check failed: {e}")
            return StravaStatus(connected=False)

    async def get_strava_stats(self, telegram_id: str) -> Optional[StravaStats]:
        """
        Get Strava athlete statistics.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            StravaStats or None if not connected
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/strava/stats/{telegram_id}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
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

    async def disconnect_strava(self, telegram_id: str) -> bool:
        """
        Disconnect Strava account.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            True if disconnected successfully
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/strava/disconnect/{telegram_id}"

        try:
            async with session.post(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Strava disconnect failed: {e}")
            return False

    async def get_strava_activities(
        self,
        telegram_id: str,
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
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/strava/activities/{telegram_id}"

        params = {"limit": limit, "offset": offset}
        if activity_type:
            params["activity_type"] = activity_type

        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return [], 0, ActivitiesSyncStatus(None, 0, False)

                data = await resp.json()

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

    async def trigger_strava_sync(self, telegram_id: str, immediate: bool = True) -> bool:
        """
        Manually trigger Strava sync for a user.

        Args:
            telegram_id: User's Telegram ID
            immediate: If True, sync now. If False, add to queue.

        Returns True if sync completed/queued successfully.
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/strava/sync/{telegram_id}"
        params = {"immediate": "true" if immediate else "false"}

        try:
            async with session.post(url, params=params) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Strava sync trigger failed: {e}")
            return False


# Global client instance
api_client = APIClient()
