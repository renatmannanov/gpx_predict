"""
Database Session Management

Provides database engine and session factory.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import Generator, AsyncGenerator

from app.config import settings


# =============================================================================
# Synchronous Engine (for existing code)
# =============================================================================

engine = create_engine(settings.database_url)


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# Async Engine (for new async code)
# =============================================================================

def _get_async_url(url: str) -> str:
    """Convert sync PostgreSQL URL to async (asyncpg) version."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


_async_url = _get_async_url(settings.database_url)

async_engine = create_async_engine(
    _async_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,  # 30 minutes
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# Initialization
# =============================================================================

def init_db() -> None:
    """Initialize database tables."""
    from app.models.base import Base
    # Import all models to register them
    from app.features.users.models import User, Notification  # noqa
    from app.features.gpx.models import GPXFile  # noqa
    from app.features.strava.models import (  # noqa
        StravaToken, StravaActivity, StravaActivitySplit, StravaSyncStatus
    )
    from app.models.prediction import Prediction  # noqa
    from app.models.user_profile import UserPerformanceProfile  # noqa
    from app.models.user_run_profile import UserRunProfile  # noqa
    from app.features.races.db_models import (  # noqa
        Race, RaceEdition, RaceDistance, RaceResultDB, UserRaceResult
    )

    Base.metadata.create_all(bind=engine)
