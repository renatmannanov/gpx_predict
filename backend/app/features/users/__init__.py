"""
User management module.

Usage:
    from app.features.users import User, Notification, UserRepository

Models:
- User: Application user with Telegram/email auth
- Notification: User notifications

Repositories:
- UserRepository: Data access for users
- NotificationRepository: Data access for notifications
"""

from .models import User, Notification
from .schemas import (
    UserCreate,
    UserResponse,
    NotificationCreate,
    NotificationResponse,
)
from .repository import UserRepository, NotificationRepository

__all__ = [
    # Models
    "User",
    "Notification",
    # Schemas
    "UserCreate",
    "UserResponse",
    "NotificationCreate",
    "NotificationResponse",
    # Repositories
    "UserRepository",
    "NotificationRepository",
]
