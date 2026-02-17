"""Users API client."""
import logging
from typing import Optional

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class UsersClient(BaseAPIClient):
    """Client for user endpoints."""

    async def get_info(self, telegram_id: str) -> Optional[dict]:
        """
        Get user info including onboarding status.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            Dict with user info or None if user doesn't exist
        """
        return await self._get_optional(f"/api/v1/users/{telegram_id}")

    async def create(self, telegram_id: str) -> Optional[dict]:
        """
        Create user or get existing one.

        Args:
            telegram_id: User's Telegram ID

        Returns:
            User info dict or None on error
        """
        return await self._post_optional(f"/api/v1/users/{telegram_id}/create")

    async def complete_onboarding(self, telegram_id: str, activity_type: str) -> bool:
        """
        Complete user onboarding.

        Args:
            telegram_id: User's Telegram ID
            activity_type: Preferred activity type ("hiking" or "running")

        Returns:
            True if successful
        """
        try:
            await self._post(
                f"/api/v1/users/{telegram_id}/onboarding",
                json={"activity_type": activity_type}
            )
            return True
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
        try:
            await self._put(
                f"/api/v1/users/{telegram_id}/preferences",
                json={"preferred_activity_type": activity_type}
            )
            return True
        except Exception as e:
            logger.error(f"Update preferences failed: {e}")
            return False
