"""
Splits synchronization.

Handles fetching and saving per-kilometer split data from Strava activities.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import StravaActivity, StravaActivitySplit, StravaToken
from .activities import ActivitySyncService

logger = logging.getLogger(__name__)


class SplitsSyncService:
    """
    Service for syncing activity splits from Strava.

    Handles:
    - Fetching detailed activity with splits
    - Saving splits to database
    - Marking activities as synced
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._activity_service = ActivitySyncService(db)

    async def fetch_activity_detail(
        self,
        access_token: str,
        activity_id: int
    ) -> dict:
        """
        Fetch detailed activity from Strava API.

        Args:
            access_token: Valid Strava access token
            activity_id: Strava activity ID

        Returns:
            Activity data dict with splits_metric
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"include_all_efforts": "false"}
            )
            response.raise_for_status()
            return response.json()

    async def sync_activity_splits(
        self,
        user_id: str,
        activity_id: int,
        strava_activity_id: int
    ) -> dict:
        """
        Sync splits for a specific activity.

        Args:
            user_id: User ID
            activity_id: Local database activity ID
            strava_activity_id: Strava's activity ID

        Returns:
            dict with sync results: {"status": "success/error", ...}
        """
        # Get token
        result = await self.db.execute(
            select(StravaToken).where(StravaToken.user_id == user_id)
        )
        token = result.scalar_one_or_none()

        if not token:
            return {"status": "error", "reason": "no_token"}

        try:
            access_token = await self._activity_service.get_valid_token(token)

            # Fetch detailed activity with splits
            activity_data = await self.fetch_activity_detail(
                access_token,
                strava_activity_id
            )

            splits_data = activity_data.get("splits_metric", [])
            if not splits_data:
                return {"status": "success", "splits_saved": 0, "reason": "no_splits"}

            # Save splits
            saved_count = 0
            for split_data in splits_data:
                split = StravaActivitySplit(
                    activity_id=activity_id,
                    split_number=split_data.get("split"),
                    distance_m=split_data.get("distance"),
                    moving_time_s=split_data.get("moving_time"),
                    elapsed_time_s=split_data.get("elapsed_time"),
                    elevation_diff_m=split_data.get("elevation_difference"),
                    average_speed_mps=split_data.get("average_speed"),
                    average_heartrate=split_data.get("average_heartrate"),
                    pace_zone=split_data.get("pace_zone")
                )
                self.db.add(split)
                saved_count += 1

            # Mark activity as splits_synced
            result = await self.db.execute(
                select(StravaActivity).where(StravaActivity.id == activity_id)
            )
            activity = result.scalar_one_or_none()

            if activity:
                activity.splits_synced = 1

            await self.db.commit()

            logger.info(f"Synced {saved_count} splits for activity {strava_activity_id}")

            return {
                "status": "success",
                "splits_saved": saved_count
            }

        except Exception as e:
            logger.error(f"Failed to sync splits for activity {strava_activity_id}: {e}")
            return {"status": "error", "error": str(e)}
