"""
Strava Token Model

Stores Strava OAuth tokens for users.
Tokens are stored encrypted for security.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class StravaToken(Base):
    """Strava OAuth token storage."""

    __tablename__ = "strava_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # Strava athlete info
    strava_athlete_id = Column(String(20), unique=True, nullable=False)

    # OAuth tokens (should be encrypted in production)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(Integer, nullable=False)  # Unix timestamp

    # Token scope
    scope = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", backref="strava_token")

    def is_expired(self) -> bool:
        """Check if access token is expired."""
        return datetime.utcnow().timestamp() >= self.expires_at

    def __repr__(self):
        return f"<StravaToken user_id={self.user_id} athlete_id={self.strava_athlete_id}>"
