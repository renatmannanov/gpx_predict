"""
User management module.

Usage:
    from app.features.users import User, Notification

Models:
- User: Application user with Telegram/email auth
- Notification: User notifications
"""

from .models import User, Notification
from .schemas import (
    UserCreate,
    UserResponse,
    NotificationCreate,
    NotificationResponse,
)

__all__ = [
    # Models
    "User",
    "Notification",
    # Schemas
    "UserCreate",
    "UserResponse",
    "NotificationCreate",
    "NotificationResponse",
]
