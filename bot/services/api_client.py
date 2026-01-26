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
    personalized: bool = False
    activities_used: int = 0


@dataclass
class UserProfile:
    """User performance profile from Strava data."""
    has_profile: bool
    avg_flat_pace_min_km: Optional[float] = None
    avg_uphill_pace_min_km: Optional[float] = None
    avg_downhill_pace_min_km: Optional[float] = None
    flat_speed_kmh: Optional[float] = None
    vertical_ability: Optional[float] = None
    total_activities_analyzed: int = 0
    has_split_data: bool = False


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
        telegram_id: Optional[str] = None,
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
            telegram_id: Optional Telegram ID for personalized prediction

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

        # Add telegram_id for personalization if provided
        if telegram_id:
            payload["telegram_id"] = telegram_id

        logger.info(f"Requesting prediction for GPX: {gpx_id}, personalized={telegram_id is not None}")

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
                personalized=data.get("personalized", False),
                activities_used=data.get("activities_used", 0),
            )

    async def compare_methods(
        self,
        gpx_id: str,
        experience: str = "regular",
        backpack: str = "light",
        group_size: int = 1,
        telegram_id: Optional[str] = None,
    ) -> dict:
        """
        Compare different prediction methods on a route.

        Args:
            gpx_id: ID of uploaded GPX file
            experience: Experience level
            backpack: Backpack weight
            group_size: Number of people
            telegram_id: Optional Telegram ID for personalized comparison

        Returns:
            RouteComparison with segment breakdown and totals.
            If telegram_id provided and user has profile, includes personalized methods.

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

        # Add telegram_id for personalization if provided
        if telegram_id:
            payload["telegram_id"] = telegram_id

        logger.info(f"Requesting comparison for GPX: {gpx_id}, personalized={telegram_id is not None}")

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

    # =========================================================================
    # User Profile (Personalization)
    # =========================================================================

    async def get_user_profile(self, telegram_id: str) -> Optional[UserProfile]:
        """
        Get user's performance profile.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            UserProfile or None if no profile exists
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/profile/{telegram_id}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                return UserProfile(
                    has_profile=data.get("has_profile", False),
                    avg_flat_pace_min_km=data.get("avg_flat_pace_min_km"),
                    avg_uphill_pace_min_km=data.get("avg_uphill_pace_min_km"),
                    avg_downhill_pace_min_km=data.get("avg_downhill_pace_min_km"),
                    flat_speed_kmh=data.get("flat_speed_kmh"),
                    vertical_ability=data.get("vertical_ability"),
                    total_activities_analyzed=data.get("total_activities_analyzed", 0),
                    has_split_data=data.get("has_split_data", False),
                )
        except Exception as e:
            logger.error(f"Get user profile failed: {e}")
            return None

    async def calculate_profile(self, telegram_id: str, use_splits: bool = True) -> Optional[UserProfile]:
        """
        Calculate or recalculate user's performance profile.

        Args:
            telegram_id: User's Telegram ID
            use_splits: If True, use detailed split data

        Returns:
            UserProfile or None if calculation failed
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/profile/{telegram_id}/calculate"
        params = {"use_splits": "true" if use_splits else "false"}

        try:
            async with session.post(url, params=params) as resp:
                data = await resp.json()

                if resp.status != 200:
                    logger.error(f"Profile calculation failed: {data.get('detail')}")
                    return None

                if not data.get("success"):
                    logger.warning(f"Profile calculation: {data.get('message')}")
                    return None

                profile_data = data.get("profile", {})
                return UserProfile(
                    has_profile=profile_data.get("has_profile", False),
                    avg_flat_pace_min_km=profile_data.get("avg_flat_pace_min_km"),
                    avg_uphill_pace_min_km=profile_data.get("avg_uphill_pace_min_km"),
                    avg_downhill_pace_min_km=profile_data.get("avg_downhill_pace_min_km"),
                    flat_speed_kmh=profile_data.get("flat_speed_kmh"),
                    vertical_ability=profile_data.get("vertical_ability"),
                    total_activities_analyzed=profile_data.get("total_activities_analyzed", 0),
                    has_split_data=profile_data.get("has_split_data", False),
                )
        except Exception as e:
            logger.error(f"Calculate profile failed: {e}")
            return None

    async def sync_splits(self, telegram_id: str, max_activities: int = 20) -> dict:
        """
        Sync splits data from Strava activities.

        Args:
            telegram_id: User's Telegram ID
            max_activities: Maximum activities to sync splits for

        Returns:
            Dict with sync results
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/strava/sync-splits/{telegram_id}"
        params = {"max_activities": max_activities}

        try:
            async with session.post(url, params=params) as resp:
                data = await resp.json()

                if resp.status != 200:
                    return {
                        "success": False,
                        "message": data.get("detail", "Unknown error")
                    }

                return {
                    "success": data.get("success", False),
                    "activities_processed": data.get("activities_processed", 0),
                    "total_splits_saved": data.get("total_splits_saved", 0),
                    "message": data.get("message", "")
                }
        except Exception as e:
            logger.error(f"Sync splits failed: {e}")
            return {"success": False, "message": str(e)}

    # =========================================================================
    # User Info & Onboarding
    # =========================================================================

    async def get_user_info(self, telegram_id: str) -> Optional[dict]:
        """
        Get user info including onboarding status.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            Dict with user info or None if user doesn't exist
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/users/{telegram_id}"

        try:
            async with session.get(url) as resp:
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Get user info failed: {e}")
            return None

    async def complete_onboarding(self, telegram_id: str, activity_type: str) -> bool:
        """
        Complete user onboarding.

        Args:
            telegram_id: User's Telegram ID
            activity_type: Preferred activity type ("hiking" or "running")

        Returns:
            True if successful
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/users/{telegram_id}/onboarding"

        try:
            async with session.post(url, json={"activity_type": activity_type}) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Complete onboarding failed: {e}")
            return False

    async def update_preferences(self, telegram_id: str, activity_type: str) -> bool:
        """
        Update user preferences.

        Args:
            telegram_id: User's Telegram ID
            activity_type: Preferred activity type

        Returns:
            True if successful
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/users/{telegram_id}/preferences"

        try:
            async with session.put(url, json={"preferred_activity_type": activity_type}) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Update preferences failed: {e}")
            return False

    async def create_user(self, telegram_id: str) -> Optional[dict]:
        """
        Create user or get existing one.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            User info dict or None on error
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/users/{telegram_id}/create"

        try:
            async with session.post(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Create user failed: {e}")
            return None

    # =========================================================================
    # Profiles (Hiking & Running)
    # =========================================================================

    async def get_hike_profile(self, telegram_id: str) -> Optional[dict]:
        """
        Get user's hiking (performance) profile.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            Profile dict or None
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/profile/{telegram_id}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Get hike profile failed: {e}")
            return None

    async def get_run_profile(self, telegram_id: str) -> Optional[dict]:
        """
        Get user's running profile.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            Profile dict or None
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/profile/{telegram_id}/run"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Get run profile failed: {e}")
            return None

    async def recalculate_profile(self, telegram_id: str, profile_type: str = "hiking") -> bool:
        """
        Recalculate user's profile.

        Args:
            telegram_id: User's Telegram ID
            profile_type: "hiking" or "running"

        Returns:
            True if successful
        """
        session = await self._get_session()

        if profile_type == "running":
            url = f"{self.base_url}/api/v1/profile/{telegram_id}/run/calculate"
        else:
            url = f"{self.base_url}/api/v1/profile/{telegram_id}/calculate"

        try:
            async with session.post(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Recalculate profile failed: {e}")
            return False

    # =========================================================================
    # Notifications
    # =========================================================================

    async def get_notifications(
        self,
        telegram_id: str,
        unread_only: bool = True,
        limit: int = 10
    ) -> list[dict]:
        """
        Get user notifications.

        Args:
            telegram_id: User's Telegram ID
            unread_only: Only return unread notifications
            limit: Maximum notifications to return

        Returns:
            List of notification dicts
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/notifications/{telegram_id}"
        params = {"unread_only": str(unread_only).lower(), "limit": limit}

        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("notifications", [])
        except Exception as e:
            logger.error(f"Get notifications failed: {e}")
            return []

    async def mark_notifications_read(
        self,
        telegram_id: str,
        notification_ids: Optional[list[int]] = None
    ) -> bool:
        """
        Mark notifications as read.

        Args:
            telegram_id: User's Telegram ID
            notification_ids: Specific IDs to mark, or None for all

        Returns:
            True if successful
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/notifications/{telegram_id}/read"

        try:
            payload = {"notification_ids": notification_ids}
            async with session.post(url, json=payload) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Mark notifications read failed: {e}")
            return False

    # =========================================================================
    # Trail Run Prediction
    # =========================================================================

    async def predict_trail_run(
        self,
        gpx_id: str,
        telegram_id: Optional[str] = None,
        gap_mode: str = "strava_gap",
        flat_pace_min_km: Optional[float] = None,
        apply_fatigue: bool = False,
        walk_threshold_override: Optional[float] = None,
    ) -> Optional[dict]:
        """
        Get trail run prediction.

        Args:
            gpx_id: ID of uploaded GPX file
            telegram_id: User's Telegram ID for personalization
            gap_mode: GAP calculation mode ("strava_gap" or "minetti_gap")
            flat_pace_min_km: Base flat pace (uses profile if not set)
            apply_fatigue: Whether to apply fatigue model
            walk_threshold_override: Override walk threshold %

        Returns:
            Prediction dict or None on error
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/predict/trail-run/compare"

        payload = {
            "gpx_id": gpx_id,
            "gap_mode": gap_mode,
            "apply_fatigue": apply_fatigue,
            "use_extended_gradients": True,
        }

        if telegram_id:
            payload["telegram_id"] = telegram_id
        if flat_pace_min_km:
            payload["flat_pace_min_km"] = flat_pace_min_km
        if walk_threshold_override:
            payload["walk_threshold_override"] = walk_threshold_override

        logger.info(f"Requesting trail run prediction for GPX: {gpx_id}")

        try:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()

                if resp.status != 200:
                    detail = data.get("detail", "Unknown error")
                    logger.error(f"Trail run prediction failed: {resp.status} - {detail}")
                    return None

                return data
        except Exception as e:
            logger.error(f"Trail run prediction failed: {e}")
            return None


# Global client instance
api_client = APIClient()
