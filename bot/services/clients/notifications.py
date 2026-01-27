"""Notifications API client."""
import logging
from typing import Optional

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class NotificationsClient(BaseAPIClient):
    """Client for notification endpoints."""

    async def get(
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
        params = {"unread_only": str(unread_only).lower(), "limit": limit}

        try:
            data = await self._get(f"/api/v1/notifications/{telegram_id}", params=params)
            return data.get("notifications", [])
        except Exception as e:
            logger.error(f"Get notifications failed: {e}")
            return []

    async def mark_read(
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
        try:
            await self._post(
                f"/api/v1/notifications/{telegram_id}/read",
                json={"notification_ids": notification_ids}
            )
            return True
        except Exception as e:
            logger.error(f"Mark notifications read failed: {e}")
            return False
