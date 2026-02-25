"""
Notification Routes

Endpoints for managing user notifications.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.session import get_async_db
from app.features.users import UserRepository, NotificationRepository

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
    telegram_id: int,
    unread_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get notifications for a user.

    Args:
        telegram_id: User's Telegram ID
        unread_only: If True, return only unread notifications
        limit: Maximum number of notifications to return
        offset: Offset for pagination
    """
    user_repo = UserRepository(db)
    notification_repo = NotificationRepository(db)

    # Find user
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get notifications
    notifications = await notification_repo.get_for_user(
        user_id=user.id,
        unread_only=unread_only,
        limit=limit
    )

    # Get counts
    all_notifications = await notification_repo.get_for_user(
        user_id=user.id,
        unread_only=False,
        limit=1000
    )
    unread_notifications = await notification_repo.get_for_user(
        user_id=user.id,
        unread_only=True,
        limit=1000
    )

    return NotificationListResponse(
        notifications=[NotificationSchema.model_validate(n) for n in notifications],
        unread_count=len(unread_notifications),
        total_count=len(all_notifications)
    )


@router.post("/notifications/{telegram_id}/read", response_model=MarkReadResponse)
async def mark_notifications_read(
    telegram_id: int,
    request: MarkReadRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Mark notifications as read.

    Args:
        telegram_id: User's Telegram ID
        request: List of notification IDs to mark, or None to mark all
    """
    user_repo = UserRepository(db)
    notification_repo = NotificationRepository(db)

    # Find user
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as read
    if request.notification_ids:
        count = await notification_repo.mark_as_read(request.notification_ids)
    else:
        count = await notification_repo.mark_all_read_for_user(user.id)

    await db.commit()

    return MarkReadResponse(marked_count=count)


@router.get("/notifications/{telegram_id}/all", response_model=NotificationListResponse)
async def get_all_notifications(
    telegram_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db)
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

async def create_notification(
    db: AsyncSession,
    user_id: str,
    notification_type: str,
    data: Optional[dict] = None
):
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
    notification_repo = NotificationRepository(db)
    notification = await notification_repo.create_notification(
        user_id=user_id,
        notification_type=notification_type,
        data=data
    )
    await db.commit()
    return notification


async def create_profile_updated_notification(
    db: AsyncSession,
    user_id: str,
    profile_type: str,  # "hiking" or "running"
    activities_count: int,
    splits_count: int
):
    """Create notification when profile is updated."""
    return await create_notification(
        db=db,
        user_id=user_id,
        notification_type="profile_updated",
        data={
            "profile_type": profile_type,
            "activities_count": activities_count,
            "splits_count": splits_count
        }
    )


async def create_sync_complete_notification(
    db: AsyncSession,
    user_id: str,
    activities_synced: int,
    activities_with_splits: int
):
    """Create notification when Strava sync completes."""
    return await create_notification(
        db=db,
        user_id=user_id,
        notification_type="sync_complete",
        data={
            "activities_synced": activities_synced,
            "activities_with_splits": activities_with_splits
        }
    )


async def create_sync_progress_notification(
    db: AsyncSession,
    user_id: str,
    progress_percent: int,
    activities_synced: int,
    total_estimated: int
):
    """Create notification for sync progress update."""
    return await create_notification(
        db=db,
        user_id=user_id,
        notification_type="sync_progress",
        data={
            "progress_percent": progress_percent,
            "activities_synced": activities_synced,
            "total_estimated": total_estimated
        }
    )
