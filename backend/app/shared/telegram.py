"""
Telegram notification sender.

Sends messages via Telegram Bot API for push notifications.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Async Telegram message sender.

    Fails silently (logs errors) to avoid breaking
    sync operations if Telegram is unavailable.
    """

    API_URL = "https://api.telegram.org"

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or settings.telegram_bot_token
        self._enabled = bool(self.bot_token)

        if not self._enabled:
            logger.info("TelegramNotifier disabled: TELEGRAM_BOT_TOKEN not set")

    @property
    def enabled(self) -> bool:
        """Check if notifier is configured."""
        return self._enabled

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[dict] = None
    ) -> bool:
        """
        Send message to Telegram chat.

        Args:
            chat_id: Telegram chat/user ID
            text: Message text (HTML supported)
            parse_mode: Parse mode (HTML or Markdown)
            reply_markup: Optional inline keyboard markup

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            return False

        if not chat_id:
            logger.warning("Cannot send Telegram message: no chat_id")
            return False

        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.API_URL}/bot{self.bot_token}/sendMessage",
                    json=payload
                )

                if response.status_code == 200:
                    logger.debug(f"Telegram message sent to {chat_id}")
                    return True
                else:
                    logger.warning(
                        f"Telegram API error: {response.status_code} - {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.warning(f"Telegram timeout sending to {chat_id}")
            return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False


# Global instance (lazy initialization)
_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create global TelegramNotifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
