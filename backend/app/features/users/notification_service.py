"""
Notification Service.

Creates notifications in DB and sends push to Telegram.
Single point of notification creation for the entire app.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Notification
from app.shared.telegram import get_telegram_notifier
from app.shared.notification_formatter import format_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Unified notification service.

    Creates notification in database and sends push to Telegram.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_and_send(
        self,
        user_id: str,
        notification_type: str,
        data: Optional[dict] = None
    ) -> Notification:
        """
        Create notification in DB and send push to Telegram.

        Args:
            user_id: User UUID
            notification_type: Type of notification
            data: Optional JSON data

        Returns:
            Created Notification object
        """
        # 1. Create notification in DB
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            data=data
        )
        self.db.add(notification)
        await self.db.flush()

        logger.debug(f"Created notification {notification_type} for user {user_id}")

        # 2. Send push to Telegram (non-blocking, errors are logged)
        await self._send_push(user_id, notification_type, data)

        return notification

    async def _send_push(
        self,
        user_id: str,
        notification_type: str,
        data: Optional[dict]
    ):
        """Send push notification to Telegram."""
        try:
            # Get user's telegram_id
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.telegram_id:
                logger.debug(f"No telegram_id for user {user_id}, skipping push")
                return

            # Format message
            text = format_notification(notification_type, data)
            if not text:
                logger.debug(f"No formatter for notification type: {notification_type}")
                return

            # Send via Telegram
            notifier = get_telegram_notifier()
            await notifier.send_message(chat_id=user.telegram_id, text=text)

        except Exception as e:
            # Don't fail the main operation if push fails
            logger.warning(f"Failed to send push notification: {e}")
