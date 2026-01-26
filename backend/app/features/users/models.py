"""
User-related models.

Models:
- User: Application user with Telegram/email auth
- Notification: User notifications (sync progress, profile updates)
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base


class User(Base):
    """
    Application user.

    Users can authenticate via Telegram or email.
    Connected to Strava for activity sync.
    """

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(String(20), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)

    # Profile
    name = Column(String(100), nullable=True)

    # Strava integration
    strava_athlete_id = Column(String(20), nullable=True)
    strava_connected = Column(Boolean, default=False)

    # Onboarding
    preferred_activity_type = Column(String(20), nullable=True)  # "hiking" | "running"
    onboarding_complete = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    performance_profile = relationship(
        "UserPerformanceProfile",
        back_populates="user",
        uselist=False,
        lazy="joined"
    )

    run_profile = relationship(
        "UserRunProfile",
        back_populates="user",
        uselist=False,
        lazy="joined"
    )

    notifications = relationship(
        "Notification",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.id} ({self.name})>"


class Notification(Base):
    """
    User notification.

    Types:
    - profile_updated: Hiking/running profile was recalculated
    - profile_complete: All 7 gradient categories are filled
    - profile_incomplete: Some categories missing (with recommendations)
    - sync_complete: Strava sync finished
    - sync_progress: Sync progress update (every N activities)
    """

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Notification type
    type = Column(String(50), nullable=False)

    # Notification data (JSON for flexibility)
    data = Column(JSON, nullable=True)

    # Status
    read = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification {self.id} type={self.type} read={self.read}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "read": self.read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
