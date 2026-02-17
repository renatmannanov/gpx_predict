"""
GPX Predictor Telegram Bot

Entry point for the bot.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from handlers import common, prediction, strava, onboarding, profile, trail_run
from services.api_client import api_client


# === Logging Setup ===
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Startup hook."""
    logger.info("Starting GPX Predictor Bot...")

    # Check backend health
    healthy = await api_client.health_check()
    if healthy:
        logger.info("Backend is healthy")
    else:
        logger.warning("Backend health check failed - bot will start anyway")

    # Get bot info
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username}")


async def on_shutdown(bot: Bot):
    """Shutdown hook."""
    logger.info("Shutting down...")
    await api_client.close()


async def main():
    """Main entry point."""
    # Create bot
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Create dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(profile.router)
    dp.include_router(prediction.router)
    dp.include_router(trail_run.router)
    dp.include_router(strava.router)

    # Register startup/shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start polling
    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
