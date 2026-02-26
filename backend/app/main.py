"""
GPX Predict API

FastAPI application for hiking/running time prediction.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings, PROJECT_ROOT
from app.db.session import init_db, AsyncSessionLocal
from app.api.v1.router import api_router
from app.features.strava.sync import background_sync


# === Logging Setup ===
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


# === Telegram Bot Setup ===
async def _setup_bot(app: FastAPI):
    """Initialize aiogram bot in webhook mode."""
    if not settings.telegram_bot_token or not settings.base_url:
        logger.info("Bot webhook skipped (TELEGRAM_BOT_TOKEN or BASE_URL not set)")
        return

    # Add bot/ to sys.path so handler imports work
    bot_dir = str(PROJECT_ROOT / "bot")
    if bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)

    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    from handlers import common, prediction, strava, onboarding, profile, trail_run, races

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(profile.router)
    dp.include_router(prediction.router)
    dp.include_router(trail_run.router)
    dp.include_router(races.router)
    dp.include_router(strava.router)

    webhook_url = f"{settings.base_url.rstrip('/')}/api/v1/telegram/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"Telegram webhook set: {webhook_url}")

    app.state.bot = bot
    app.state.bot_dp = dp


async def _shutdown_bot(app: FastAPI):
    """Cleanup bot on shutdown."""
    bot = getattr(app.state, "bot", None)
    if bot:
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Telegram webhook removed")


# === Lifespan ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting GPX Predict API...")
    init_db()
    logger.info("Database initialized")

    # Start background Strava sync
    if settings.strava_client_id and settings.strava_client_secret:
        await background_sync.start(AsyncSessionLocal)
        logger.info("Strava background sync started")

    # Start Telegram bot webhook
    await _setup_bot(app)

    yield

    # Shutdown
    await _shutdown_bot(app)
    if settings.strava_client_id and settings.strava_client_secret:
        await background_sync.stop()
        logger.info("Strava background sync stopped")
    logger.info("Shutting down...")


# === App Creation ===
app = FastAPI(
    title="GPX Predict API",
    description="Hiking and running time prediction with elevation awareness",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# === Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Routes ===
app.include_router(api_router, prefix="/api/v1")


# === Health Check ===
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


# === Static Files (Frontend SPA) ===
_frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
    logger.info(f"Serving frontend from {_frontend_dist}")
