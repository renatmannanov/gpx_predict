"""
Notification Model

Stores notifications for users (profile updates, sync progress, etc.)
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class Notification(Base):
    """
    User notification model.

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
    type = Column(String(50), nullable=False)  # profile_updated, sync_complete, etc.

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
