"""API clients for backend communication."""
from .base import BaseAPIClient, APIError
from .gpx import GPXClient, GPXInfo
from .hiking import HikingClient, HikePrediction, TimeBreakdown
from .trail_run import TrailRunClient
from .strava import StravaClient, StravaStatus, StravaStats, StravaActivity, ActivitiesSyncStatus
from .users import UsersClient
from .profiles import ProfilesClient, UserProfile
from .health import HealthClient
from .notifications import NotificationsClient
from .races import RacesClient


class APIClient:
    """Unified API client with all sub-clients."""

    def __init__(self, base_url: str, ayda_run_api_url: str | None = None, cross_service_api_key: str | None = None):
        self.base_url = base_url
        self.gpx = GPXClient(base_url)
        self.hiking = HikingClient(base_url)
        self.trail_run = TrailRunClient(base_url)
        self.strava = StravaClient(base_url, ayda_run_api_url, cross_service_api_key)
        self.users = UsersClient(base_url)
        self.profiles = ProfilesClient(base_url)
        self.health = HealthClient(base_url)
        self.notifications = NotificationsClient(base_url)
        self.races = RacesClient(base_url)

    async def close(self):
        """Close all client sessions."""
        await self.gpx.close()
        await self.hiking.close()
        await self.trail_run.close()
        await self.strava.close()
        await self.users.close()
        await self.profiles.close()
        await self.health.close()
        await self.notifications.close()
        await self.races.close()

    # =========================================================================
    # Backwards compatibility methods (delegate to sub-clients)
    # =========================================================================

    # GPX
    async def upload_gpx(self, filename: str, content: bytes) -> GPXInfo:
        return await self.gpx.upload(filename, content)

    # Hiking
    async def predict_hike(self, *args, **kwargs) -> HikePrediction:
        return await self.hiking.predict(*args, **kwargs)

    async def compare_methods(self, *args, **kwargs) -> dict:
        return await self.hiking.compare_methods(*args, **kwargs)

    # Trail Run
    async def predict_trail_run(self, *args, **kwargs):
        return await self.trail_run.predict(*args, **kwargs)

    # Strava
    async def get_strava_auth_url(self, telegram_id: int) -> str:
        return await self.strava.get_auth_url(telegram_id)

    async def get_strava_status(self, telegram_id: int) -> StravaStatus:
        return await self.strava.get_status(telegram_id)

    async def get_strava_stats(self, telegram_id: int) -> StravaStats | None:
        return await self.strava.get_stats(telegram_id)

    async def disconnect_strava(self, telegram_id: int) -> bool:
        return await self.strava.disconnect(telegram_id)

    async def get_strava_activities(self, *args, **kwargs):
        return await self.strava.get_activities(*args, **kwargs)

    async def trigger_strava_sync(self, telegram_id: int, immediate: bool = True) -> bool:
        return await self.strava.trigger_sync(telegram_id, immediate)

    # Users
    async def get_user_info(self, telegram_id: int):
        return await self.users.get_info(telegram_id)

    async def create_user(self, telegram_id: int):
        return await self.users.create(telegram_id)

    async def complete_onboarding(self, telegram_id: int, activity_type: str) -> bool:
        return await self.users.complete_onboarding(telegram_id, activity_type)

    async def update_preferences(self, telegram_id: int, activity_type: str) -> bool:
        return await self.users.update_preferences(telegram_id, activity_type)

    # Profiles
    async def get_user_profile(self, telegram_id: int) -> UserProfile | None:
        data = await self.profiles.get_hiking(telegram_id)
        if not data:
            return None
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

    async def get_hike_profile(self, telegram_id: int):
        return await self.profiles.get_hiking(telegram_id)

    async def get_run_profile(self, telegram_id: int):
        return await self.profiles.get_trail_run(telegram_id)

    async def calculate_profile(self, telegram_id: int, use_splits: bool = True) -> UserProfile | None:
        return await self.profiles.calculate_hiking(telegram_id, use_splits)

    async def recalculate_profile(self, telegram_id: int, profile_type: str = "hiking") -> bool:
        return await self.profiles.recalculate(telegram_id, profile_type)

    async def sync_splits(self, *args, **kwargs) -> dict:
        return await self.profiles.sync_splits(*args, **kwargs)

    # Health
    async def health_check(self) -> bool:
        return await self.health.check()

    # Notifications
    async def get_notifications(self, *args, **kwargs):
        return await self.notifications.get(*args, **kwargs)

    async def mark_notifications_read(self, *args, **kwargs) -> bool:
        return await self.notifications.mark_read(*args, **kwargs)


__all__ = [
    "APIClient",
    "APIError",
    "GPXClient",
    "GPXInfo",
    "HikingClient",
    "HikePrediction",
    "TimeBreakdown",
    "TrailRunClient",
    "StravaClient",
    "StravaStatus",
    "StravaStats",
    "StravaActivity",
    "ActivitiesSyncStatus",
    "UsersClient",
    "ProfilesClient",
    "UserProfile",
    "HealthClient",
    "NotificationsClient",
    "RacesClient",
]
