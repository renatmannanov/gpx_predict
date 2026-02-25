"""
Internal API routes for cross-service communication.

Protected by X-API-Key header (shared secret between services).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_async_db
from app.features.users.models import User
from app.features.strava.sync import trigger_user_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])


# =============================================================================
# API Key Dependency
# =============================================================================

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify cross-service API key."""
    if not settings.cross_service_api_key:
        raise HTTPException(status_code=503, detail="Internal API not configured")
    if x_api_key != settings.cross_service_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# =============================================================================
# Schemas
# =============================================================================

class StravaConnectedRequest(BaseModel):
    telegram_id: int
    athlete_id: int


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/strava/connected", dependencies=[Depends(verify_api_key)])
async def strava_connected(
    request: StravaConnectedRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Webhook: user connected Strava via ayda_run.

    Creates or updates user and triggers background sync.
    """
    # Find or create user by telegram_id
    result = await db.execute(
        select(User).where(User.telegram_id == request.telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=request.telegram_id)
        db.add(user)
        await db.flush()
        logger.info("Created user for telegram_id=%s", request.telegram_id)

    # Update Strava fields
    user.strava_athlete_id = request.athlete_id
    user.strava_connected = True
    await db.commit()

    # Trigger background sync (will use ayda_run token via fallback)
    await trigger_user_sync(user.id, priority=True)

    logger.info(
        "Strava connected webhook: telegram_id=%s, athlete_id=%s, user_id=%s",
        request.telegram_id, request.athlete_id, user.id,
    )

    return {"status": "sync_triggered", "user_id": str(user.id)}
