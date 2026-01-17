"""
User Profile Routes

Endpoints for user performance profile management.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_async_db
from app.models.user import User
from app.models.user_profile import UserPerformanceProfile
from app.services.user_profile import UserProfileService
from app.services.strava_sync import StravaSyncService

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class ProfileResponse(BaseModel):
    """User performance profile response."""
    has_profile: bool

    # Pace metrics (min/km)
    avg_flat_pace_min_km: Optional[float] = None
    avg_uphill_pace_min_km: Optional[float] = None
    avg_downhill_pace_min_km: Optional[float] = None

    # Derived speeds (km/h)
    flat_speed_kmh: Optional[float] = None
    uphill_speed_kmh: Optional[float] = None
    downhill_speed_kmh: Optional[float] = None

    # Coefficients
    vertical_ability: Optional[float] = None

    # Statistics
    total_activities_analyzed: int = 0
    total_hike_activities: int = 0
    total_distance_km: float = 0.0
    total_elevation_m: float = 0.0

    # Metadata
    has_split_data: bool = False
    last_calculated_at: Optional[datetime] = None


class ProfileCalculateResponse(BaseModel):
    """Response for profile calculation."""
    success: bool
    message: str
    profile: Optional[ProfileResponse] = None


class SyncSplitsResponse(BaseModel):
    """Response for splits sync."""
    success: bool
    activities_processed: int
    total_splits_saved: int
    errors: list = []
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/profile/{telegram_id}", response_model=ProfileResponse)
async def get_profile(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """
    Get user's performance profile.

    Returns calculated metrics based on Strava activity history.
    """
    # Find user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        return ProfileResponse(has_profile=False)

    # Get profile
    profile = db.query(UserPerformanceProfile).filter(
        UserPerformanceProfile.user_id == user.id
    ).first()

    if not profile:
        return ProfileResponse(has_profile=False)

    return ProfileResponse(
        has_profile=True,
        avg_flat_pace_min_km=profile.avg_flat_pace_min_km,
        avg_uphill_pace_min_km=profile.avg_uphill_pace_min_km,
        avg_downhill_pace_min_km=profile.avg_downhill_pace_min_km,
        flat_speed_kmh=profile.flat_speed_kmh,
        uphill_speed_kmh=60 / profile.avg_uphill_pace_min_km if profile.avg_uphill_pace_min_km else None,
        downhill_speed_kmh=60 / profile.avg_downhill_pace_min_km if profile.avg_downhill_pace_min_km else None,
        vertical_ability=profile.vertical_ability,
        total_activities_analyzed=profile.total_activities_analyzed or 0,
        total_hike_activities=profile.total_hike_activities or 0,
        total_distance_km=profile.total_distance_km or 0.0,
        total_elevation_m=profile.total_elevation_m or 0.0,
        has_split_data=profile.has_split_data,
        last_calculated_at=profile.last_calculated_at
    )


@router.post("/profile/{telegram_id}/calculate", response_model=ProfileCalculateResponse)
async def calculate_profile(
    telegram_id: str,
    use_splits: bool = True,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Calculate or recalculate user's performance profile.

    Args:
        telegram_id: Telegram user ID
        use_splits: If True, use detailed split data for better accuracy

    Returns profile with calculated metrics.
    """
    # Find user
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.strava_connected:
        raise HTTPException(status_code=400, detail="Strava not connected")

    try:
        if use_splits:
            profile = await UserProfileService.calculate_profile_with_splits(user.id, db)
        else:
            profile = await UserProfileService.calculate_profile(user.id, db)

        if not profile:
            return ProfileCalculateResponse(
                success=False,
                message="Insufficient data. Need at least 3 hiking activities.",
                profile=None
            )

        return ProfileCalculateResponse(
            success=True,
            message=f"Profile calculated from {profile.total_activities_analyzed} activities",
            profile=ProfileResponse(
                has_profile=True,
                avg_flat_pace_min_km=profile.avg_flat_pace_min_km,
                avg_uphill_pace_min_km=profile.avg_uphill_pace_min_km,
                avg_downhill_pace_min_km=profile.avg_downhill_pace_min_km,
                flat_speed_kmh=profile.flat_speed_kmh,
                uphill_speed_kmh=60 / profile.avg_uphill_pace_min_km if profile.avg_uphill_pace_min_km else None,
                downhill_speed_kmh=60 / profile.avg_downhill_pace_min_km if profile.avg_downhill_pace_min_km else None,
                vertical_ability=profile.vertical_ability,
                total_activities_analyzed=profile.total_activities_analyzed or 0,
                total_hike_activities=profile.total_hike_activities or 0,
                total_distance_km=profile.total_distance_km or 0.0,
                total_elevation_m=profile.total_elevation_m or 0.0,
                has_split_data=profile.has_split_data,
                last_calculated_at=profile.last_calculated_at
            )
        )

    except Exception as e:
        logger.error(f"Failed to calculate profile for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strava/sync-splits/{telegram_id}", response_model=SyncSplitsResponse)
async def sync_splits(
    telegram_id: str,
    max_activities: int = 20,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Sync splits (per-km data) for user's activities.

    This fetches detailed split data from Strava for activities
    that don't have splits yet. Splits are used for more accurate
    profile calculation.

    Args:
        telegram_id: Telegram user ID
        max_activities: Maximum number of activities to sync splits for
    """
    # Find user
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.strava_connected:
        raise HTTPException(status_code=400, detail="Strava not connected")

    try:
        service = StravaSyncService(db)
        result = await service.sync_splits_for_user(
            user_id=user.id,
            max_activities=max_activities,
            activity_types=["Hike", "Walk"]
        )

        return SyncSplitsResponse(
            success=result["status"] == "success",
            activities_processed=result.get("activities_processed", 0),
            total_splits_saved=result.get("total_splits_saved", 0),
            errors=result.get("errors", []),
            message=f"Synced {result.get('total_splits_saved', 0)} splits from {result.get('activities_processed', 0)} activities"
        )

    except Exception as e:
        logger.error(f"Failed to sync splits for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
