"""
Profile management endpoints.

Unified endpoints for hiking and trail run profiles.
Uses async repositories and thin route pattern.

Endpoints:
- GET  /profiles/{telegram_id}/hiking      - Get hiking profile
- GET  /profiles/{telegram_id}/trail-run   - Get trail run profile
- POST /profiles/{telegram_id}/hiking/calculate     - Recalculate hiking profile
- POST /profiles/{telegram_id}/trail-run/calculate  - Recalculate trail run profile
- POST /profiles/{telegram_id}/sync-splits          - Sync Strava splits
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.features.users import UserRepository
from app.features.hiking import HikingProfileRepository
from app.features.trail_run import TrailRunProfileRepository
from app.services.user_profile import UserProfileService
from app.features.strava.sync import StravaSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


# =============================================================================
# Schemas
# =============================================================================

class HikingProfileResponse(BaseModel):
    """Hiking profile response."""
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


class TrailRunProfileResponse(BaseModel):
    """Trail run profile response."""
    has_profile: bool

    # Pace metrics (min/km)
    avg_flat_pace_min_km: Optional[float] = None
    avg_gentle_uphill_pace_min_km: Optional[float] = None
    avg_moderate_uphill_pace_min_km: Optional[float] = None
    avg_steep_uphill_pace_min_km: Optional[float] = None
    avg_gentle_downhill_pace_min_km: Optional[float] = None
    avg_moderate_downhill_pace_min_km: Optional[float] = None
    avg_steep_downhill_pace_min_km: Optional[float] = None

    # Walk threshold
    walk_threshold_percent: Optional[float] = None

    # Derived
    flat_speed_kmh: Optional[float] = None

    # Statistics
    total_activities: int = 0
    total_distance_km: float = 0.0
    total_elevation_m: float = 0.0

    # Metadata
    has_profile_data: bool = False
    has_extended_gradient_data: bool = False
    last_calculated_at: Optional[datetime] = None


class ProfileCalculateResponse(BaseModel):
    """Response for profile calculation."""
    success: bool
    message: str
    profile: Optional[dict] = None


class SyncSplitsResponse(BaseModel):
    """Response for splits sync."""
    success: bool
    activities_processed: int
    total_splits_saved: int
    errors: list = []
    message: str


# =============================================================================
# Hiking Profile Endpoints
# =============================================================================

@router.get("/{telegram_id}/hiking", response_model=HikingProfileResponse)
async def get_hiking_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get user's hiking performance profile.

    Returns calculated metrics based on Strava Hike/Walk activities.
    """
    user_repo = UserRepository(db)
    profile_repo = HikingProfileRepository(db)

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        return HikingProfileResponse(has_profile=False)

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return HikingProfileResponse(has_profile=False)

    return HikingProfileResponse(
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
        # Speeds and coefficients
        flat_speed_kmh=profile.flat_speed_kmh,
        vertical_ability=profile.vertical_ability,
        # Statistics
        total_activities_analyzed=profile.total_activities_analyzed or 0,
        total_hike_activities=profile.total_hike_activities or 0,
        total_distance_km=profile.total_distance_km or 0.0,
        total_elevation_m=profile.total_elevation_m or 0.0,
        # Metadata
        has_split_data=profile.has_split_data,
        has_extended_gradient_data=profile.has_extended_gradient_data,
        last_calculated_at=profile.last_calculated_at
    )


@router.post("/{telegram_id}/hiking/calculate", response_model=ProfileCalculateResponse)
async def calculate_hiking_profile(
    telegram_id: str,
    use_splits: bool = Query(True, description="Use detailed split data for better accuracy"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Calculate or recalculate user's hiking performance profile.

    Analyzes Strava Hike/Walk activities to determine personal pace
    on different terrain gradients.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(telegram_id)

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
            profile=profile.to_dict()
        )

    except Exception as e:
        logger.error(f"Failed to calculate hiking profile for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Trail Run Profile Endpoints
# =============================================================================

@router.get("/{telegram_id}/trail-run", response_model=TrailRunProfileResponse)
async def get_trail_run_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get user's trail running performance profile.

    Returns calculated metrics based on Strava Run/TrailRun activities.
    """
    user_repo = UserRepository(db)
    profile_repo = TrailRunProfileRepository(db)

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        return TrailRunProfileResponse(has_profile=False)

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return TrailRunProfileResponse(has_profile=False)

    return TrailRunProfileResponse(
        has_profile=True,
        # Paces
        avg_flat_pace_min_km=profile.avg_flat_pace_min_km,
        avg_gentle_uphill_pace_min_km=profile.avg_gentle_uphill_pace_min_km,
        avg_moderate_uphill_pace_min_km=profile.avg_moderate_uphill_pace_min_km,
        avg_steep_uphill_pace_min_km=profile.avg_steep_uphill_pace_min_km,
        avg_gentle_downhill_pace_min_km=profile.avg_gentle_downhill_pace_min_km,
        avg_moderate_downhill_pace_min_km=profile.avg_moderate_downhill_pace_min_km,
        avg_steep_downhill_pace_min_km=profile.avg_steep_downhill_pace_min_km,
        # Walk threshold
        walk_threshold_percent=profile.walk_threshold_percent,
        # Derived
        flat_speed_kmh=profile.flat_speed_kmh,
        # Statistics
        total_activities=profile.total_activities or 0,
        total_distance_km=profile.total_distance_km or 0.0,
        total_elevation_m=profile.total_elevation_m or 0.0,
        # Metadata
        has_profile_data=profile.has_profile_data,
        has_extended_gradient_data=profile.has_extended_gradient_data,
        last_calculated_at=profile.last_calculated_at
    )


@router.post("/{telegram_id}/trail-run/calculate", response_model=ProfileCalculateResponse)
async def calculate_trail_run_profile(
    telegram_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Calculate or recalculate user's trail running performance profile.

    Analyzes Strava Run/TrailRun activities to determine personal pace
    on different terrain gradients.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.strava_connected:
        raise HTTPException(status_code=400, detail="Strava not connected")

    try:
        profile = await UserProfileService.calculate_run_profile_with_splits(user.id, db)

        if not profile:
            return ProfileCalculateResponse(
                success=False,
                message="Insufficient data. Need at least 3 run activities with splits.",
                profile=None
            )

        return ProfileCalculateResponse(
            success=True,
            message=f"Profile calculated from {profile.total_activities} activities",
            profile=profile.to_dict()
        )

    except Exception as e:
        logger.error(f"Failed to calculate trail run profile for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Splits Sync Endpoint
# =============================================================================

@router.post("/{telegram_id}/sync-splits", response_model=SyncSplitsResponse)
async def sync_splits(
    telegram_id: str,
    max_activities: int = Query(20, ge=1, le=100, description="Maximum activities to sync"),
    activity_types: str = Query("hike,walk,run", description="Comma-separated activity types"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Sync splits (per-km data) for user's activities.

    Fetches detailed split data from Strava for activities
    that don't have splits yet. Splits enable more accurate
    profile calculation.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.strava_connected:
        raise HTTPException(status_code=400, detail="Strava not connected")

    # Parse activity types
    type_mapping = {
        "hike": "Hike",
        "walk": "Walk",
        "run": "Run",
        "trailrun": "TrailRun",
    }
    types = [
        type_mapping.get(t.strip().lower(), t.strip())
        for t in activity_types.split(",")
    ]

    try:
        service = StravaSyncService(db)
        result = await service.sync_splits_for_user(
            user_id=user.id,
            max_activities=max_activities,
            activity_types=types
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
