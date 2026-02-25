"""
User schemas.

Pydantic models for user operations.
"""

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class UserCreate(BaseModel):
    """Create user request."""

    telegram_id: Optional[int] = None
    email: Optional[str] = None
    name: Optional[str] = None


class UserResponse(BaseModel):
    """User response."""

    id: str
    telegram_id: Optional[int]
    email: Optional[str]
    name: Optional[str]
    strava_connected: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    """Create notification."""

    user_id: str
    type: str
    data: Optional[dict[str, Any]] = None


class NotificationResponse(BaseModel):
    """Notification response."""

    id: int
    type: str
    data: Optional[dict[str, Any]]
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True
