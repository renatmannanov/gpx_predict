"""User profiles API client."""
import logging
from dataclasses import dataclass
from typing import Optional

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


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


class ProfilesClient(BaseAPIClient):
    """Client for user profile endpoints."""

    async def get_hiking(self, telegram_id: int) -> Optional[dict]:
        """
        Get user's hiking (performance) profile.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            Profile dict or None
        """
        return await self._get_optional(f"/api/v1/profiles/{telegram_id}/hiking")

    async def get_trail_run(self, telegram_id: int) -> Optional[dict]:
        """
        Get user's running profile.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            Profile dict or None
        """
        return await self._get_optional(f"/api/v1/profiles/{telegram_id}/trail-run")

    async def calculate_hiking(self, telegram_id: int, use_splits: bool = True) -> Optional[UserProfile]:
        """
        Calculate or recalculate user's hiking performance profile.

        Args:
            telegram_id: User's Telegram ID
            use_splits: If True, use detailed split data

        Returns:
            UserProfile or None if calculation failed
        """
        params = {"use_splits": "true" if use_splits else "false"}

        try:
            data = await self._post(
                f"/api/v1/profiles/{telegram_id}/hiking/calculate",
                params=params
            )

            if not data.get("success"):
                logger.warning(f"Profile calculation: {data.get('message')}")
                return None

            profile_data = data.get("profile", {})
            return UserProfile(
                has_profile=True,
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

    async def recalculate(self, telegram_id: int, profile_type: str = "hiking") -> bool:
        """
        Recalculate user's profile.

        Args:
            telegram_id: User's Telegram ID
            profile_type: "hiking" or "running"

        Returns:
            True if successful
        """
        if profile_type == "running":
            path = f"/api/v1/profiles/{telegram_id}/trail-run/calculate"
        else:
            path = f"/api/v1/profiles/{telegram_id}/hiking/calculate"

        try:
            await self._post(path)
            return True
        except Exception as e:
            logger.error(f"Recalculate profile failed: {e}")
            return False

    async def sync_splits(
        self,
        telegram_id: int,
        max_activities: int = 20,
        activity_types: str = "hike,walk"
    ) -> dict:
        """
        Sync splits data from Strava activities.

        Args:
            telegram_id: User's Telegram ID
            max_activities: Maximum activities to sync splits for
            activity_types: Comma-separated activity types

        Returns:
            Dict with sync results
        """
        params = {"max_activities": max_activities, "activity_types": activity_types}

        try:
            data = await self._post(
                f"/api/v1/profiles/{telegram_id}/sync-splits",
                params=params
            )

            return {
                "success": data.get("success", False),
                "activities_processed": data.get("activities_processed", 0),
                "total_splits_saved": data.get("total_splits_saved", 0),
                "message": data.get("message", "")
            }
        except Exception as e:
            logger.error(f"Sync splits failed: {e}")
            return {"success": False, "message": str(e)}
