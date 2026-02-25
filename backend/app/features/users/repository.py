"""
User repositories.

Data access layer for User and Notification models.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.repository import BaseRepository
from .models import User, Notification


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            User if found, None otherwise
        """
        return await self.get_by(telegram_id=telegram_id)

    async def get_with_profiles(self, telegram_id: int) -> User | None:
        """
        Get user with hiking and run profiles eagerly loaded.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            User with profiles loaded, None if not found
        """
        result = await self.db.execute(
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(
                selectinload(User.hiking_profile),
                selectinload(User.run_profile)
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, telegram_id: int, **kwargs) -> tuple[User, bool]:
        """
        Get existing user or create new one.

        Args:
            telegram_id: User's Telegram ID
            **kwargs: Additional fields for new user

        Returns:
            Tuple of (user, created) where created is True if new user was made
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        user = await self.create(telegram_id=telegram_id, **kwargs)
        return user, True

    async def update_strava_connection(
        self,
        user: User,
        connected: bool,
        athlete_id: int | None = None
    ) -> User:
        """
        Update user's Strava connection status.

        Args:
            user: User to update
            connected: Whether Strava is connected
            athlete_id: Strava athlete ID (optional)

        Returns:
            Updated user
        """
        update_data = {"strava_connected": connected}
        if athlete_id is not None:
            update_data["strava_athlete_id"] = athlete_id
        return await self.update(user, **update_data)

    async def complete_onboarding(
        self,
        user: User,
        activity_type: str
    ) -> User:
        """
        Mark user onboarding as complete.

        Args:
            user: User to update
            activity_type: Preferred activity type ("hiking" or "running")

        Returns:
            Updated user
        """
        return await self.update(
            user,
            onboarding_complete=True,
            preferred_activity_type=activity_type
        )


class NotificationRepository(BaseRepository[Notification]):
    """Repository for Notification operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Notification)

    async def get_for_user(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> list[Notification]:
        """
        Get notifications for user.

        Args:
            user_id: User's ID
            unread_only: If True, only return unread notifications
            limit: Maximum notifications to return

        Returns:
            List of notifications ordered by creation time (newest first)
        """
        query = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            query = query.where(Notification.read == False)  # noqa: E712
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_as_read(self, notification_ids: list[int]) -> int:
        """
        Mark notifications as read.

        Args:
            notification_ids: List of notification IDs to mark as read

        Returns:
            Number of notifications updated
        """
        if not notification_ids:
            return 0
        result = await self.db.execute(
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def mark_all_read_for_user(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            user_id: User's ID

        Returns:
            Number of notifications updated
        """
        result = await self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.read == False)  # noqa: E712
            .values(read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def create_notification(
        self,
        user_id: str,
        notification_type: str,
        data: dict | None = None
    ) -> Notification:
        """
        Create a new notification.

        Args:
            user_id: User's ID
            notification_type: Type of notification
            data: Additional notification data

        Returns:
            Created notification
        """
        return await self.create(
            user_id=user_id,
            type=notification_type,
            data=data
        )
