"""
GPX Predictor API

FastAPI application for hiking/running time prediction.
"""

from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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


# === Lifespan ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting GPX Predictor API...")
    init_db()
    logger.info("Database initialized")

    # Start background Strava sync
    if settings.strava_client_id and settings.strava_client_secret:
        await background_sync.start(AsyncSessionLocal)
        logger.info("Strava background sync started")

    yield

    # Shutdown
    if settings.strava_client_id and settings.strava_client_secret:
        await background_sync.stop()
        logger.info("Strava background sync stopped")
    logger.info("Shutting down...")


# === App Creation ===
app = FastAPI(
    title="GPX Predictor API",
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
