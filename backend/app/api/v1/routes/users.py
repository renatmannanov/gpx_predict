"""
User Routes

Endpoints for user management, onboarding, and preferences.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.features.users import UserRepository

router = APIRouter()


# === Schemas ===

class UserInfoSchema(BaseModel):
    """User info response schema."""
    telegram_id: int
    name: Optional[str] = None
    race_search_name: Optional[str] = None
    strava_connected: bool
    onboarding_complete: bool
    preferred_activity_type: Optional[str] = None

    class Config:
        from_attributes = True


class OnboardingCompleteRequest(BaseModel):
    """Request to complete onboarding."""
    activity_type: str  # "hiking" or "running"


class PreferencesUpdateRequest(BaseModel):
    """Request to update user preferences."""
    preferred_activity_type: Optional[str] = None


class UserUpdateResponse(BaseModel):
    """Response for user update actions."""
    success: bool
    message: str


# === Endpoints ===

@router.get("/me")
async def get_current_user(db: AsyncSession = Depends(get_async_db)):
    """Get current user profile."""
    # TODO: Implement authentication
    return {"message": "Not implemented yet"}


@router.get("/{telegram_id}", response_model=UserInfoSchema)
async def get_user_info(telegram_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Get user info by Telegram ID.

    Returns user's onboarding status, Strava connection, and preferences.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserInfoSchema(
        telegram_id=user.telegram_id,
        name=user.name,
        race_search_name=user.race_search_name,
        strava_connected=user.strava_connected or False,
        onboarding_complete=user.onboarding_complete or False,
        preferred_activity_type=user.preferred_activity_type
    )


@router.post("/{telegram_id}/onboarding", response_model=UserUpdateResponse)
async def complete_onboarding(
    telegram_id: int,
    request: OnboardingCompleteRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Complete user onboarding.

    Sets onboarding_complete=True and saves the preferred activity type.
    Creates the user if it doesn't exist.
    """
    # Validate activity type
    if request.activity_type not in ("hiking", "running"):
        raise HTTPException(
            status_code=400,
            detail="activity_type must be 'hiking' or 'running'"
        )

    user_repo = UserRepository(db)

    # Find or create user
    user, created = await user_repo.get_or_create(telegram_id)

    # Complete onboarding
    await user_repo.complete_onboarding(user, request.activity_type)
    await db.commit()

    return UserUpdateResponse(
        success=True,
        message=f"Onboarding completed with activity type: {request.activity_type}"
    )


@router.put("/{telegram_id}/preferences", response_model=UserUpdateResponse)
async def update_preferences(
    telegram_id: int,
    request: PreferencesUpdateRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update user preferences.

    Can update preferred_activity_type.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update preferences
    if request.preferred_activity_type is not None:
        if request.preferred_activity_type not in ("hiking", "running"):
            raise HTTPException(
                status_code=400,
                detail="preferred_activity_type must be 'hiking' or 'running'"
            )
        await user_repo.update(user, preferred_activity_type=request.preferred_activity_type)

    await db.commit()

    return UserUpdateResponse(
        success=True,
        message="Preferences updated successfully"
    )


class RaceSearchNameRequest(BaseModel):
    """Request to update race search name."""
    race_search_name: str


@router.put("/{telegram_id}/race-search-name", response_model=UserUpdateResponse)
async def update_race_search_name(
    telegram_id: int,
    request: RaceSearchNameRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Save the name used for searching race results."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await user_repo.update(user, race_search_name=request.race_search_name)
    await db.commit()

    return UserUpdateResponse(success=True, message="Race search name updated")


@router.post("/{telegram_id}/create", response_model=UserInfoSchema)
async def create_user(
    telegram_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a new user or return existing one.

    Used by bot to ensure user exists before starting onboarding.
    """
    user_repo = UserRepository(db)
    user, created = await user_repo.get_or_create(telegram_id)

    if created:
        await db.commit()

    return UserInfoSchema(
        telegram_id=user.telegram_id,
        name=user.name,
        race_search_name=user.race_search_name,
        strava_connected=user.strava_connected or False,
        onboarding_complete=user.onboarding_complete or False,
        preferred_activity_type=user.preferred_activity_type
    )
