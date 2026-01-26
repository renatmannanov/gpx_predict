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

# Create engine based on database URL
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False}
    )
else:
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
    """Convert sync database URL to async version."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


# Create async engine
_async_url = _get_async_url(settings.database_url)

if _async_url.startswith("sqlite"):
    async_engine = create_async_engine(
        _async_url,
        connect_args={"check_same_thread": False}
    )
elif _async_url.startswith("postgresql"):
    # PostgreSQL with connection pool settings
    async_engine = create_async_engine(
        _async_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # 30 minutes
    )
else:
    async_engine = create_async_engine(_async_url)

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
    from app.models import user, prediction, gpx  # noqa

    Base.metadata.create_all(bind=engine)
