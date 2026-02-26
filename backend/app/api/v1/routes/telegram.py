"""
Telegram Webhook Endpoint

Receives updates from Telegram and feeds them to the aiogram dispatcher.
"""

import logging

from aiogram.types import Update
from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Process incoming Telegram update via webhook."""
    bot = getattr(request.app.state, "bot", None)
    bot_dp = getattr(request.app.state, "bot_dp", None)

    if not bot or not bot_dp:
        logger.warning("Telegram webhook called but bot is not initialized")
        return Response(status_code=503)

    try:
        update = Update.model_validate(await request.json(), context={"bot": bot})
        await bot_dp.feed_update(bot=bot, update=update)
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")

    return Response(status_code=200)
