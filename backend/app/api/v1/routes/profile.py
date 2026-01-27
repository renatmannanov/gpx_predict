"""
User Profile Routes (DEPRECATED)

DEPRECATED: These endpoints are deprecated in favor of /api/v1/profiles/...
New endpoints:
- GET  /api/v1/profiles/{telegram_id}/hiking      (was: /profile/{telegram_id})
- GET  /api/v1/profiles/{telegram_id}/trail-run   (was: /profile/{telegram_id}/run)
- POST /api/v1/profiles/{telegram_id}/hiking/calculate
- POST /api/v1/profiles/{telegram_id}/trail-run/calculate
- POST /api/v1/profiles/{telegram_id}/sync-splits

These legacy endpoints will be removed in a future version.
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
from app.models.user_run_profile import UserRunProfile
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

    # Legacy 3-category pace metrics (min/km)
    avg_flat_pace_min_km: Optional[float] = None
    avg_uphill_pace_min_km: Optional[float] = None
    avg_downhill_pace_min_km: Optional[float] = None

    # Extended 7-category pace metrics (min/km)
    avg_steep_downhill_pace_min_km: Optional[float] = None
    avg_moderate_downhill_pace_min_km: Optional[float] = None
    avg_gentle_downhill_pace_min_km: Optional[float] = None
    avg_gentle_uphill_pace_min_km: Optional[float] = None
    avg_moderate_uphill_pace_min_km: Optional[float] = None
    avg_steep_uphill_pace_min_km: Optional[float] = None

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
    has_extended_gradient_data: bool = False
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
        # Legacy 3-category
        avg_flat_pace_min_km=profile.avg_flat_pace_min_km,
        avg_uphill_pace_min_km=profile.avg_uphill_pace_min_km,
        avg_downhill_pace_min_km=profile.avg_downhill_pace_min_km,
        # Extended 7-category
        avg_steep_downhill_pace_min_km=profile.avg_steep_downhill_pace_min_km,
        avg_moderate_downhill_pace_min_km=profile.avg_moderate_downhill_pace_min_km,
        avg_gentle_downhill_pace_min_km=profile.avg_gentle_downhill_pace_min_km,
        avg_gentle_uphill_pace_min_km=profile.avg_gentle_uphill_pace_min_km,
        avg_moderate_uphill_pace_min_km=profile.avg_moderate_uphill_pace_min_km,
        avg_steep_uphill_pace_min_km=profile.avg_steep_uphill_pace_min_km,
        # Speeds
        flat_speed_kmh=profile.flat_speed_kmh,
        uphill_speed_kmh=60 / profile.avg_uphill_pace_min_km if profile.avg_uphill_pace_min_km else None,
        downhill_speed_kmh=60 / profile.avg_downhill_pace_min_km if profile.avg_downhill_pace_min_km else None,
        # Coefficients and stats
        vertical_ability=profile.vertical_ability,
        total_activities_analyzed=profile.total_activities_analyzed or 0,
        total_hike_activities=profile.total_hike_activities or 0,
        total_distance_km=profile.total_distance_km or 0.0,
        total_elevation_m=profile.total_elevation_m or 0.0,
        has_split_data=profile.has_split_data,
        has_extended_gradient_data=profile.has_extended_gradient_data,
        last_calculated_at=profile.last_calculated_at
    )


@router.get("/profile/{telegram_id}/run")
async def get_run_profile(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """
    Get user's running performance profile.

    Returns calculated metrics based on Strava Run/TrailRun activities.
    """
    # Find user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        return {"has_profile": False}

    # Get run profile
    profile = db.query(UserRunProfile).filter(
        UserRunProfile.user_id == user.id
    ).first()

    if not profile:
        return {"has_profile": False}

    # Return profile data using model's to_dict method
    result = profile.to_dict()
    result["has_profile"] = True
    return result


@router.post("/profile/{telegram_id}/run/calculate")
async def calculate_run_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Calculate or recalculate user's running performance profile.
    """
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
        profile = await UserProfileService.calculate_run_profile_with_splits(user.id, db)

        if not profile:
            return {
                "success": False,
                "message": "Insufficient data. Need at least 3 run activities with splits.",
                "profile": None
            }

        result_dict = profile.to_dict()
        result_dict["has_profile"] = True

        return {
            "success": True,
            "message": f"Profile calculated from {profile.total_activities} activities",
            "profile": result_dict
        }

    except Exception as e:
        logger.error(f"Failed to calculate run profile for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                # Legacy 3-category
                avg_flat_pace_min_km=profile.avg_flat_pace_min_km,
                avg_uphill_pace_min_km=profile.avg_uphill_pace_min_km,
                avg_downhill_pace_min_km=profile.avg_downhill_pace_min_km,
                # Extended 7-category
                avg_steep_downhill_pace_min_km=profile.avg_steep_downhill_pace_min_km,
                avg_moderate_downhill_pace_min_km=profile.avg_moderate_downhill_pace_min_km,
                avg_gentle_downhill_pace_min_km=profile.avg_gentle_downhill_pace_min_km,
                avg_gentle_uphill_pace_min_km=profile.avg_gentle_uphill_pace_min_km,
                avg_moderate_uphill_pace_min_km=profile.avg_moderate_uphill_pace_min_km,
                avg_steep_uphill_pace_min_km=profile.avg_steep_uphill_pace_min_km,
                # Speeds
                flat_speed_kmh=profile.flat_speed_kmh,
                uphill_speed_kmh=60 / profile.avg_uphill_pace_min_km if profile.avg_uphill_pace_min_km else None,
                downhill_speed_kmh=60 / profile.avg_downhill_pace_min_km if profile.avg_downhill_pace_min_km else None,
                # Coefficients and stats
                vertical_ability=profile.vertical_ability,
                total_activities_analyzed=profile.total_activities_analyzed or 0,
                total_hike_activities=profile.total_hike_activities or 0,
                total_distance_km=profile.total_distance_km or 0.0,
                total_elevation_m=profile.total_elevation_m or 0.0,
                has_split_data=profile.has_split_data,
                has_extended_gradient_data=profile.has_extended_gradient_data,
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
