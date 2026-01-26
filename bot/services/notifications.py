"""
Notification Service

Handles checking and displaying notifications to users.
Uses polling approach - checks notifications when user interacts with bot.
"""

import logging
from typing import Optional
from aiogram.types import Message

from services.api_client import api_client

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for checking and formatting user notifications."""

    @staticmethod
    async def check_and_show_notifications(
        message: Message,
        telegram_id: str,
        max_notifications: int = 3
    ) -> bool:
        """
        Check for unread notifications and show them to user.

        Args:
            message: Aiogram Message to reply to
            telegram_id: User's Telegram ID
            max_notifications: Max notifications to show at once

        Returns:
            True if any notifications were shown
        """
        try:
            notifications = await api_client.get_notifications(
                telegram_id,
                unread_only=True,
                limit=max_notifications
            )

            if not notifications:
                return False

            # Format and show notifications
            for notification in notifications:
                text = NotificationService.format_notification(notification)
                if text:
                    await message.answer(text, parse_mode="HTML")

            # Mark as read
            notification_ids = [n["id"] for n in notifications]
            await api_client.mark_notifications_read(telegram_id, notification_ids)

            return True

        except Exception as e:
            logger.error(f"Error checking notifications: {e}")
            return False

    @staticmethod
    def format_notification(notification: dict) -> Optional[str]:
        """
        Format a notification for display.

        Args:
            notification: Notification dict from API

        Returns:
            Formatted text or None if unknown type
        """
        ntype = notification.get("type")
        data = notification.get("data") or {}

        if ntype == "profile_updated":
            return NotificationService._format_profile_updated(data)
        elif ntype == "sync_complete":
            return NotificationService._format_sync_complete(data)
        elif ntype == "sync_progress":
            return NotificationService._format_sync_progress(data)
        elif ntype == "profile_complete":
            return NotificationService._format_profile_complete(data)
        elif ntype == "profile_incomplete":
            return NotificationService._format_profile_incomplete(data)
        elif ntype == "strava_connected":
            return NotificationService._format_strava_connected(data)
        else:
            logger.warning(f"Unknown notification type: {ntype}")
            return None

    @staticmethod
    def _format_profile_updated(data: dict) -> str:
        """Format profile_updated notification."""
        profile_type = data.get("profile_type", "hiking")
        activities = data.get("activities_count", 0)
        splits = data.get("splits_count", 0)

        type_label = "бегуна" if profile_type == "running" else "хайкера"

        return f"""
📊 <b>Профиль обновлён!</b>

Загружено: {activities} активностей
Проанализировано: {splits} сплитов

Твой профиль {type_label} пересчитан!
Используй /profile чтобы посмотреть.
"""

    @staticmethod
    def _format_sync_complete(data: dict) -> str:
        """Format sync_complete notification."""
        activities = data.get("activities_synced", 0)
        with_splits = data.get("activities_with_splits", 0)

        return f"""
✅ <b>Синхронизация завершена!</b>

Синхронизировано: {activities} активностей
С детальными данными: {with_splits}

Теперь прогнозы будут персонализированы!
"""

    @staticmethod
    def _format_sync_progress(data: dict) -> str:
        """Format sync_progress notification."""
        progress = data.get("progress_percent", 0)
        synced = data.get("activities_synced", 0)
        total = data.get("total_estimated", 0)

        return f"""
🔄 <b>Прогресс синхронизации</b>

Загружено: {synced} из ~{total} активностей ({progress}%)

Синхронизация продолжается в фоне...
"""

    @staticmethod
    def _format_profile_complete(data: dict) -> str:
        """Format profile_complete notification."""
        return """
🎉 <b>Профиль полный!</b>

Все 7 категорий градиента заполнены.
Теперь прогнозы будут максимально точными!

Используй /profile чтобы посмотреть.
"""

    @staticmethod
    def _format_profile_incomplete(data: dict) -> str:
        """Format profile_incomplete notification."""
        missing = data.get("missing_categories", [])

        if missing:
            missing_text = ", ".join(missing)
            return f"""
⚠️ <b>Профиль неполный</b>

Не хватает данных для категорий: {missing_text}

Для более точных прогнозов нужно больше активностей с разным рельефом.
"""
        return ""

    @staticmethod
    def _format_strava_connected(data: dict) -> str:
        """Format strava_connected notification."""
        athlete_name = data.get("athlete_name", "Пользователь")
        return f"""
✅ <b>Strava подключён!</b>

{athlete_name}, теперь я смогу анализировать твои активности и делать персональные прогнозы.

Синхронизация активностей начнётся в фоне. Когда профиль будет готов — я сообщу!
"""


# Global instance
notification_service = NotificationService()
