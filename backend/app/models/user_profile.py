"""
User Performance Profile Model

Stores calculated performance metrics from Strava activities.
Used for personalizing hiking time predictions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserPerformanceProfile(Base):
    """
    User's performance profile calculated from Strava activities.

    Metrics are computed from activity splits to determine:
    - Base pace on flat terrain
    - Pace adjustments for uphill/downhill
    - Personal "vertical ability" coefficient

    All pace values are in minutes per kilometer.
    """

    __tablename__ = "user_performance_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # === Pace metrics (calculated from splits) ===
    # Flat terrain: gradient between -3% and +3%
    avg_flat_pace_min_km = Column(Float, nullable=True)
    # Uphill: gradient > +3%
    avg_uphill_pace_min_km = Column(Float, nullable=True)
    # Downhill: gradient < -3%
    avg_downhill_pace_min_km = Column(Float, nullable=True)

    # === Personal coefficients ===
    # How much slower on uphills vs Naismith standard
    # 1.0 = standard, <1.0 = faster than standard, >1.0 = slower
    vertical_ability = Column(Float, default=1.0)

    # === Statistics ===
    total_activities_analyzed = Column(Integer, default=0)
    total_hike_activities = Column(Integer, default=0)
    total_distance_km = Column(Float, default=0.0)
    total_elevation_m = Column(Float, default=0.0)

    # === Metadata ===
    last_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="performance_profile")

    def __repr__(self):
        return f"<UserPerformanceProfile user={self.user_id} flat_pace={self.avg_flat_pace_min_km}>"

    @property
    def has_split_data(self) -> bool:
        """Check if profile has detailed split-based pace data."""
        return (
            self.avg_uphill_pace_min_km is not None
            and self.avg_downhill_pace_min_km is not None
        )

    @property
    def flat_speed_kmh(self) -> Optional[float]:
        """Convert flat pace to speed in km/h."""
        if self.avg_flat_pace_min_km and self.avg_flat_pace_min_km > 0:
            return round(60 / self.avg_flat_pace_min_km, 2)
        return None

    def to_dict(self) -> dict:
        """Convert profile to dictionary for API responses."""
        return {
            "avg_flat_pace_min_km": self.avg_flat_pace_min_km,
            "avg_uphill_pace_min_km": self.avg_uphill_pace_min_km,
            "avg_downhill_pace_min_km": self.avg_downhill_pace_min_km,
            "vertical_ability": self.vertical_ability,
            "flat_speed_kmh": self.flat_speed_kmh,
            "total_activities_analyzed": self.total_activities_analyzed,
            "total_hike_activities": self.total_hike_activities,
            "total_distance_km": round(self.total_distance_km, 1),
            "total_elevation_m": round(self.total_elevation_m, 0),
            "has_split_data": self.has_split_data,
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
        }
