"""
User Routes

Endpoints for user management, onboarding, and preferences.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User

router = APIRouter()


# === Schemas ===

class UserInfoSchema(BaseModel):
    """User info response schema."""
    telegram_id: str
    name: Optional[str] = None
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
async def get_current_user(db: Session = Depends(get_db)):
    """Get current user profile."""
    # TODO: Implement authentication
    return {"message": "Not implemented yet"}


@router.get("/{telegram_id}", response_model=UserInfoSchema)
async def get_user_info(telegram_id: str, db: Session = Depends(get_db)):
    """
    Get user info by Telegram ID.

    Returns user's onboarding status, Strava connection, and preferences.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserInfoSchema(
        telegram_id=user.telegram_id,
        name=user.name,
        strava_connected=user.strava_connected or False,
        onboarding_complete=user.onboarding_complete or False,
        preferred_activity_type=user.preferred_activity_type
    )


@router.post("/{telegram_id}/onboarding", response_model=UserUpdateResponse)
async def complete_onboarding(
    telegram_id: str,
    request: OnboardingCompleteRequest,
    db: Session = Depends(get_db)
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

    # Find or create user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)

    # Update onboarding status
    user.onboarding_complete = True
    user.preferred_activity_type = request.activity_type
    db.commit()

    return UserUpdateResponse(
        success=True,
        message=f"Onboarding completed with activity type: {request.activity_type}"
    )


@router.put("/{telegram_id}/preferences", response_model=UserUpdateResponse)
async def update_preferences(
    telegram_id: str,
    request: PreferencesUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update user preferences.

    Can update preferred_activity_type.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update preferences
    if request.preferred_activity_type is not None:
        if request.preferred_activity_type not in ("hiking", "running"):
            raise HTTPException(
                status_code=400,
                detail="preferred_activity_type must be 'hiking' or 'running'"
            )
        user.preferred_activity_type = request.preferred_activity_type

    db.commit()

    return UserUpdateResponse(
        success=True,
        message="Preferences updated successfully"
    )


@router.post("/{telegram_id}/create", response_model=UserInfoSchema)
async def create_user(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """
    Create a new user or return existing one.

    Used by bot to ensure user exists before starting onboarding.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    return UserInfoSchema(
        telegram_id=user.telegram_id,
        name=user.name,
        strava_connected=user.strava_connected or False,
        onboarding_complete=user.onboarding_complete or False,
        preferred_activity_type=user.preferred_activity_type
    )
