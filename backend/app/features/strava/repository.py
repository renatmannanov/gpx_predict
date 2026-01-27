"""
Strava repositories.

Data access layer for Strava-related models.
"""

from datetime import datetime
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.repository import BaseRepository
from .models import StravaToken, StravaActivity, StravaActivitySplit, StravaSyncStatus


class StravaTokenRepository(BaseRepository[StravaToken]):
    """Repository for Strava OAuth tokens."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaToken)

    async def get_by_user_id(self, user_id: str) -> StravaToken | None:
        """
        Get token for user.

        Args:
            user_id: User's ID

        Returns:
            StravaToken if found, None otherwise
        """
        return await self.get_by(user_id=user_id)

    async def get_by_athlete_id(self, athlete_id: str) -> StravaToken | None:
        """
        Get token by Strava athlete ID.

        Args:
            athlete_id: Strava athlete ID

        Returns:
            StravaToken if found, None otherwise
        """
        return await self.get_by(strava_athlete_id=athlete_id)

    async def update_tokens(
        self,
        token: StravaToken,
        access_token: str,
        refresh_token: str,
        expires_at: int
    ) -> StravaToken:
        """
        Update OAuth tokens after refresh.

        Args:
            token: Existing token entity
            access_token: New access token
            refresh_token: New refresh token
            expires_at: Token expiration timestamp

        Returns:
            Updated token
        """
        return await self.update(
            token,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            updated_at=datetime.utcnow()
        )


class StravaActivityRepository(BaseRepository[StravaActivity]):
    """Repository for Strava activities."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaActivity)

    async def get_by_strava_id(self, strava_id: int) -> StravaActivity | None:
        """
        Get activity by Strava activity ID.

        Args:
            strava_id: Strava's activity ID

        Returns:
            StravaActivity if found, None otherwise
        """
        return await self.get_by(strava_id=strava_id)

    async def get_user_activities(
        self,
        user_id: str,
        activity_type: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[StravaActivity]:
        """
        Get user activities with pagination.

        Args:
            user_id: User's ID
            activity_type: Filter by activity type (Run, Hike, Walk, etc.)
            limit: Maximum activities to return
            offset: Pagination offset

        Returns:
            List of activities ordered by date (newest first)
        """
        query = (
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .order_by(desc(StravaActivity.start_date))
            .offset(offset)
            .limit(limit)
        )
        if activity_type:
            query = query.where(StravaActivity.activity_type == activity_type)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_user_activities(
        self,
        user_id: str,
        activity_type: str | None = None
    ) -> int:
        """
        Count user activities.

        Args:
            user_id: User's ID
            activity_type: Filter by activity type

        Returns:
            Number of activities
        """
        query = (
            select(func.count())
            .select_from(StravaActivity)
            .where(StravaActivity.user_id == user_id)
        )
        if activity_type:
            query = query.where(StravaActivity.activity_type == activity_type)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_with_splits(self, activity_id: int) -> StravaActivity | None:
        """
        Get activity with splits eagerly loaded.

        Args:
            activity_id: Activity ID

        Returns:
            Activity with splits loaded, None if not found
        """
        result = await self.db.execute(
            select(StravaActivity)
            .where(StravaActivity.id == activity_id)
            .options(selectinload(StravaActivity.splits))
        )
        return result.scalar_one_or_none()

    async def get_activities_for_profile(
        self,
        user_id: str,
        activity_types: list[str],
        with_splits: bool = True,
        limit: int = 100
    ) -> list[StravaActivity]:
        """
        Get activities suitable for profile calculation.

        Args:
            user_id: User's ID
            activity_types: List of activity types to include
            with_splits: Only include activities with synced splits
            limit: Maximum activities to return

        Returns:
            List of activities for profile calculation
        """
        query = (
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(activity_types))
            .order_by(desc(StravaActivity.start_date))
            .limit(limit)
        )
        if with_splits:
            query = query.where(StravaActivity.splits_synced == 1)
            query = query.options(selectinload(StravaActivity.splits))

        result = await self.db.execute(query)
        return list(result.scalars().all())


class StravaActivitySplitRepository(BaseRepository[StravaActivitySplit]):
    """Repository for Strava activity splits."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaActivitySplit)

    async def get_for_activity(self, activity_id: int) -> list[StravaActivitySplit]:
        """
        Get all splits for an activity.

        Args:
            activity_id: Activity ID

        Returns:
            List of splits ordered by split number
        """
        result = await self.db.execute(
            select(StravaActivitySplit)
            .where(StravaActivitySplit.activity_id == activity_id)
            .order_by(StravaActivitySplit.split_number)
        )
        return list(result.scalars().all())

    async def delete_for_activity(self, activity_id: int) -> int:
        """
        Delete all splits for an activity.

        Args:
            activity_id: Activity ID

        Returns:
            Number of splits deleted
        """
        from sqlalchemy import delete
        result = await self.db.execute(
            delete(StravaActivitySplit)
            .where(StravaActivitySplit.activity_id == activity_id)
        )
        await self.db.flush()
        return result.rowcount


class SyncStatusRepository(BaseRepository[StravaSyncStatus]):
    """Repository for Strava sync status."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, StravaSyncStatus)

    async def get_by_user_id(self, user_id: str) -> StravaSyncStatus | None:
        """
        Get sync status for user.

        Args:
            user_id: User's ID

        Returns:
            StravaSyncStatus if found, None otherwise
        """
        return await self.get_by(user_id=user_id)

    async def get_or_create(self, user_id: str) -> StravaSyncStatus:
        """
        Get existing or create new sync status.

        Args:
            user_id: User's ID

        Returns:
            Sync status for user
        """
        status = await self.get_by_user_id(user_id)
        if not status:
            status = await self.create(user_id=user_id)
        return status

    async def update_sync_progress(
        self,
        status: StravaSyncStatus,
        total_synced: int,
        last_sync_at: datetime | None = None,
        in_progress: bool = False
    ) -> StravaSyncStatus:
        """
        Update sync progress.

        Args:
            status: Sync status entity
            total_synced: Total activities synced
            last_sync_at: Last sync timestamp
            in_progress: Whether sync is in progress

        Returns:
            Updated sync status
        """
        update_data = {
            "total_activities_synced": total_synced,
            "sync_in_progress": 1 if in_progress else 0,
        }
        if last_sync_at:
            update_data["last_sync_at"] = last_sync_at
        return await self.update(status, **update_data)

    async def mark_sync_complete(
        self,
        status: StravaSyncStatus,
        total_synced: int
    ) -> StravaSyncStatus:
        """
        Mark sync as complete.

        Args:
            status: Sync status entity
            total_synced: Total activities synced

        Returns:
            Updated sync status
        """
        return await self.update(
            status,
            total_activities_synced=total_synced,
            last_sync_at=datetime.utcnow(),
            sync_in_progress=0,
            initial_sync_complete=1
        )
