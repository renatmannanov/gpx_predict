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
    bot = request.app.state.bot
    bot_dp = request.app.state.bot_dp

    if not bot or not bot_dp:
        return Response(status_code=503)

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await bot_dp.feed_update(bot=bot, update=update)

    return Response(status_code=200)
