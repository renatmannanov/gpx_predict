"""
User Run Performance Profile Model

Stores calculated performance metrics from Strava Run activities.
Used for personalizing trail running time predictions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.shared.constants import DEFAULT_HIKE_THRESHOLD_PERCENT


class UserRunProfile(Base):
    """
    User's running performance profile from Strava Run/TrailRun activities.

    Similar to UserHikingProfile but:
    - Different activity types (Run, TrailRun, VirtualRun)
    - Includes walk threshold detection
    - Uses GAP-based fallbacks instead of Tobler
    """

    __tablename__ = "user_run_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # === Pace metrics (7-category system) ===
    avg_flat_pace_min_km = Column(Float, nullable=True)
    avg_gentle_uphill_pace_min_km = Column(Float, nullable=True)
    avg_moderate_uphill_pace_min_km = Column(Float, nullable=True)
    avg_steep_uphill_pace_min_km = Column(Float, nullable=True)
    avg_gentle_downhill_pace_min_km = Column(Float, nullable=True)
    avg_moderate_downhill_pace_min_km = Column(Float, nullable=True)
    avg_steep_downhill_pace_min_km = Column(Float, nullable=True)

    # === Sample counts per category (for confidence assessment) ===
    flat_sample_count = Column(Integer, default=0)
    gentle_uphill_sample_count = Column(Integer, default=0)
    moderate_uphill_sample_count = Column(Integer, default=0)
    steep_uphill_sample_count = Column(Integer, default=0)
    gentle_downhill_sample_count = Column(Integer, default=0)
    moderate_downhill_sample_count = Column(Integer, default=0)
    steep_downhill_sample_count = Column(Integer, default=0)

    # === Walk threshold ===
    # Auto-detected from splits or set manually
    # NOTE: default uses constant to stay in sync with codebase
    walk_threshold_percent = Column(Float, nullable=True, default=DEFAULT_HIKE_THRESHOLD_PERCENT)

    # === Statistics ===
    total_activities = Column(Integer, default=0)
    total_distance_km = Column(Float, default=0.0)
    total_elevation_m = Column(Float, default=0.0)

    # === Metadata ===
    last_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="run_profile")

    def __repr__(self):
        return f"<UserRunProfile user={self.user_id} flat_pace={self.avg_flat_pace_min_km}>"

    @property
    def has_profile_data(self) -> bool:
        """Check if profile has any pace data."""
        return self.avg_flat_pace_min_km is not None

    @property
    def has_extended_gradient_data(self) -> bool:
        """Check if profile has 7-category gradient data."""
        has_uphill = (
            self.avg_gentle_uphill_pace_min_km is not None
            or self.avg_moderate_uphill_pace_min_km is not None
            or self.avg_steep_uphill_pace_min_km is not None
        )
        has_downhill = (
            self.avg_gentle_downhill_pace_min_km is not None
            or self.avg_moderate_downhill_pace_min_km is not None
            or self.avg_steep_downhill_pace_min_km is not None
        )
        return has_uphill and has_downhill

    @property
    def flat_speed_kmh(self) -> Optional[float]:
        """Convert flat pace to speed."""
        if self.avg_flat_pace_min_km and self.avg_flat_pace_min_km > 0:
            return round(60 / self.avg_flat_pace_min_km, 2)
        return None

    def get_sample_count(self, category: str) -> int:
        """Get sample count for a gradient category."""
        mapping = {
            'flat': self.flat_sample_count,
            'gentle_uphill': self.gentle_uphill_sample_count,
            'moderate_uphill': self.moderate_uphill_sample_count,
            'steep_uphill': self.steep_uphill_sample_count,
            'gentle_downhill': self.gentle_downhill_sample_count,
            'moderate_downhill': self.moderate_downhill_sample_count,
            'steep_downhill': self.steep_downhill_sample_count,
        }
        return mapping.get(category, 0) or 0

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "avg_flat_pace_min_km": self.avg_flat_pace_min_km,
            "avg_gentle_uphill_pace_min_km": self.avg_gentle_uphill_pace_min_km,
            "avg_moderate_uphill_pace_min_km": self.avg_moderate_uphill_pace_min_km,
            "avg_steep_uphill_pace_min_km": self.avg_steep_uphill_pace_min_km,
            "avg_gentle_downhill_pace_min_km": self.avg_gentle_downhill_pace_min_km,
            "avg_moderate_downhill_pace_min_km": self.avg_moderate_downhill_pace_min_km,
            "avg_steep_downhill_pace_min_km": self.avg_steep_downhill_pace_min_km,
            "walk_threshold_percent": self.walk_threshold_percent,
            "flat_speed_kmh": self.flat_speed_kmh,
            "total_activities": self.total_activities,
            "total_distance_km": round(self.total_distance_km, 1) if self.total_distance_km else 0,
            "total_elevation_m": round(self.total_elevation_m, 0) if self.total_elevation_m else 0,
            "has_profile_data": self.has_profile_data,
            "has_extended_gradient_data": self.has_extended_gradient_data,
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
        }
