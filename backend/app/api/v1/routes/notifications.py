"""
Notification Routes

Endpoints for managing user notifications.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.notification import Notification

router = APIRouter()


# === Schemas ===

class NotificationSchema(BaseModel):
    """Notification response schema."""
    id: int
    type: str
    data: Optional[dict] = None
    read: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Response for notification list."""
    notifications: List[NotificationSchema]
    unread_count: int
    total_count: int


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: Optional[List[int]] = None  # None = mark all as read


class MarkReadResponse(BaseModel):
    """Response for mark read action."""
    marked_count: int


# === Endpoints ===

@router.get("/notifications/{telegram_id}", response_model=NotificationListResponse)
async def get_notifications(
    telegram_id: str,
    unread_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get notifications for a user.

    Args:
        telegram_id: User's Telegram ID
        unread_only: If True, return only unread notifications
        limit: Maximum number of notifications to return
        offset: Offset for pagination
    """
    # Find user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build query
    query = db.query(Notification).filter(Notification.user_id == user.id)

    if unread_only:
        query = query.filter(Notification.read == False)

    # Get counts
    total_count = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.read == False
    ).count()

    # Get notifications with pagination
    notifications = query.order_by(
        Notification.created_at.desc()
    ).offset(offset).limit(limit).all()

    return NotificationListResponse(
        notifications=[NotificationSchema.model_validate(n) for n in notifications],
        unread_count=unread_count,
        total_count=total_count
    )


@router.post("/notifications/{telegram_id}/read", response_model=MarkReadResponse)
async def mark_notifications_read(
    telegram_id: str,
    request: MarkReadRequest,
    db: Session = Depends(get_db)
):
    """
    Mark notifications as read.

    Args:
        telegram_id: User's Telegram ID
        request: List of notification IDs to mark, or None to mark all
    """
    # Find user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build query
    query = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.read == False
    )

    if request.notification_ids:
        query = query.filter(Notification.id.in_(request.notification_ids))

    # Update
    count = query.update({"read": True}, synchronize_session=False)
    db.commit()

    return MarkReadResponse(marked_count=count)


@router.get("/notifications/{telegram_id}/all", response_model=NotificationListResponse)
async def get_all_notifications(
    telegram_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get all notifications (including read) for a user.

    Args:
        telegram_id: User's Telegram ID
        limit: Maximum number of notifications to return
        offset: Offset for pagination
    """
    return await get_notifications(
        telegram_id=telegram_id,
        unread_only=False,
        limit=limit,
        offset=offset,
        db=db
    )


# === Helper functions for creating notifications ===

def create_notification(
    db: Session,
    user_id: str,
    notification_type: str,
    data: Optional[dict] = None
) -> Notification:
    """
    Create a notification for a user.

    Args:
        db: Database session
        user_id: User's UUID
        notification_type: Type of notification
        data: Optional JSON data

    Returns:
        Created notification
    """
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        data=data
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def create_profile_updated_notification(
    db: Session,
    user_id: str,
    profile_type: str,  # "hiking" or "running"
    activities_count: int,
    splits_count: int
) -> Notification:
    """Create notification when profile is updated."""
    return create_notification(
        db=db,
        user_id=user_id,
        notification_type="profile_updated",
        data={
            "profile_type": profile_type,
            "activities_count": activities_count,
            "splits_count": splits_count
        }
    )


def create_sync_complete_notification(
    db: Session,
    user_id: str,
    activities_synced: int,
    activities_with_splits: int
) -> Notification:
    """Create notification when Strava sync completes."""
    return create_notification(
        db=db,
        user_id=user_id,
        notification_type="sync_complete",
        data={
            "activities_synced": activities_synced,
            "activities_with_splits": activities_with_splits
        }
    )


def create_sync_progress_notification(
    db: Session,
    user_id: str,
    progress_percent: int,
    activities_synced: int,
    total_estimated: int
) -> Notification:
    """Create notification for sync progress update."""
    return create_notification(
        db=db,
        user_id=user_id,
        notification_type="sync_progress",
        data={
            "progress_percent": progress_percent,
            "activities_synced": activities_synced,
            "total_estimated": total_estimated
        }
    )
