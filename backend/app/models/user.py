"""
User Model

Stores user information and preferences.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base


class User(Base):
    """User model for storing user data."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(String(20), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)

    # Profile
    name = Column(String(100), nullable=True)

    # Strava integration (future)
    strava_athlete_id = Column(String(20), nullable=True)
    strava_connected = Column(Boolean, default=False)

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

    def __repr__(self):
        return f"<User {self.id} ({self.name})>"
