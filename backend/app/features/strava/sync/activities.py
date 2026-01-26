"""
Activity synchronization.

Handles fetching and saving activities from Strava API.
"""

import logging
from datetime import datetime
from typing import Optional, Union

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from ..models import StravaActivity, StravaToken

logger = logging.getLogger(__name__)


class ActivitySyncService:
    """
    Service for syncing activities from Strava.

    Handles:
    - Fetching activities list from Strava API
    - Saving new activities to database
    - Token refresh during sync
    """

    def __init__(self, db: Union[Session, AsyncSession]):
        self.db = db
        self._is_async = isinstance(db, AsyncSession)

    async def fetch_activities(
        self,
        access_token: str,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        per_page: int = 30
    ) -> list[dict]:
        """
        Fetch activities from Strava API.

        Args:
            access_token: Valid Strava access token
            after: Only activities after this time
            before: Only activities before this time
            per_page: Results per page (max 200)

        Returns:
            List of activity data dicts
        """
        params = {"per_page": per_page}

        if after:
            params["after"] = int(after.timestamp())
        if before:
            params["before"] = int(before.timestamp())

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params
            )
            response.raise_for_status()
            return response.json()

    def save_activity(
        self,
        user_id: str,
        data: dict
    ) -> Optional[StravaActivity]:
        """
        Save a single activity to database.

        Args:
            user_id: User ID
            data: Activity data from Strava API

        Returns:
            StravaActivity if saved (new), None if already exists
        """
        strava_id = data["id"]

        # Check if already exists
        existing = self.db.query(StravaActivity).filter(
            StravaActivity.strava_id == strava_id
        ).first()

        if existing:
            return None

        # Parse start date
        start_date = datetime.fromisoformat(
            data["start_date"].replace("Z", "+00:00")
        )

        activity = StravaActivity(
            user_id=user_id,
            strava_id=strava_id,
            name=data.get("name"),
            activity_type=data.get("type", "Unknown"),
            start_date=start_date,
            distance_m=data.get("distance"),
            moving_time_s=data.get("moving_time"),
            elapsed_time_s=data.get("elapsed_time"),
            elevation_gain_m=data.get("total_elevation_gain"),
            elevation_loss_m=data.get("elev_low"),  # Note: API returns elev_high/low
            avg_speed_mps=data.get("average_speed"),
            max_speed_mps=data.get("max_speed"),
            avg_heartrate=data.get("average_heartrate"),
            max_heartrate=data.get("max_heartrate"),
            avg_cadence=data.get("average_cadence"),
            suffer_score=data.get("suffer_score"),
        )

        self.db.add(activity)
        self.db.flush()  # Get the ID assigned
        return activity

    async def get_valid_token(self, token: StravaToken) -> str:
        """
        Get valid access token, refreshing if needed.

        Args:
            token: StravaToken instance

        Returns:
            Valid access token string
        """
        if token.expires_at < datetime.utcnow().timestamp() + 300:
            logger.info(f"Refreshing token for user {token.user_id}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://www.strava.com/oauth/token",
                    data={
                        "client_id": settings.strava_client_id,
                        "client_secret": settings.strava_client_secret,
                        "refresh_token": token.refresh_token,
                        "grant_type": "refresh_token"
                    }
                )
                response.raise_for_status()
                new_tokens = response.json()

            token.access_token = new_tokens["access_token"]
            token.refresh_token = new_tokens["refresh_token"]
            token.expires_at = new_tokens["expires_at"]
            token.updated_at = datetime.utcnow()

            if self._is_async:
                await self.db.commit()
            else:
                self.db.commit()

        return token.access_token
