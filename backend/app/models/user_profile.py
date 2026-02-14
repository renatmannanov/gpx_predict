"""
User Hiking Profile Model

Stores calculated performance metrics from Strava hiking activities.
Used for personalizing hiking time predictions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.shared.gradients import LEGACY_CATEGORY_MAPPING


class UserHikingProfile(Base):
    """
    User's hiking performance profile calculated from Strava activities.

    Metrics are computed from activity splits to determine:
    - Base pace on flat terrain
    - Pace adjustments for uphill/downhill
    - Personal "vertical ability" coefficient

    All pace values are in minutes per kilometer.
    """

    __tablename__ = "user_hiking_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # === Pace metrics (calculated from splits) ===
    # Legacy 3-category system (kept for backward compatibility)
    # Flat terrain: gradient between -3% and +3%
    avg_flat_pace_min_km = Column(Float, nullable=True)
    # Uphill: gradient > +3%
    avg_uphill_pace_min_km = Column(Float, nullable=True)
    # Downhill: gradient < -3%
    avg_downhill_pace_min_km = Column(Float, nullable=True)

    # === Extended 7-category gradient system ===
    # Steep downhill: gradient < -15%
    avg_steep_downhill_pace_min_km = Column(Float, nullable=True)
    # Moderate downhill: gradient -15% to -8%
    avg_moderate_downhill_pace_min_km = Column(Float, nullable=True)
    # Gentle downhill: gradient -8% to -3%
    avg_gentle_downhill_pace_min_km = Column(Float, nullable=True)
    # Flat: gradient -3% to +3% (same as avg_flat_pace_min_km)
    # Gentle uphill: gradient +3% to +8%
    avg_gentle_uphill_pace_min_km = Column(Float, nullable=True)
    # Moderate uphill: gradient +8% to +15%
    avg_moderate_uphill_pace_min_km = Column(Float, nullable=True)
    # Steep uphill: gradient > +15%
    avg_steep_uphill_pace_min_km = Column(Float, nullable=True)

    # === Sample counts per category (for confidence assessment) ===
    flat_sample_count = Column(Integer, default=0)
    gentle_uphill_sample_count = Column(Integer, default=0)
    moderate_uphill_sample_count = Column(Integer, default=0)
    steep_uphill_sample_count = Column(Integer, default=0)
    gentle_downhill_sample_count = Column(Integer, default=0)
    moderate_downhill_sample_count = Column(Integer, default=0)
    steep_downhill_sample_count = Column(Integer, default=0)

    # === 11-category gradient data (JSON) ===
    # {category: {"avg": float, "samples": int}} — 11 categories from shared/gradients.py
    gradient_paces = Column(JSON, nullable=True)
    # {category: {"p25": float, "p50": float, "p75": float}} — percentiles after IQR
    gradient_percentiles = Column(JSON, nullable=True)

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
    user = relationship("User", back_populates="hiking_profile")

    def __repr__(self):
        return f"<UserHikingProfile user={self.user_id} flat_pace={self.avg_flat_pace_min_km}>"

    @property
    def has_split_data(self) -> bool:
        """Check if profile has detailed split-based pace data (3-category)."""
        return (
            self.avg_uphill_pace_min_km is not None
            and self.avg_downhill_pace_min_km is not None
        )

    @property
    def has_extended_gradient_data(self) -> bool:
        """Check if profile has extended 7-category gradient data."""
        # Need at least flat + some uphill + some downhill categories
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
        """Convert flat pace to speed in km/h."""
        if self.avg_flat_pace_min_km and self.avg_flat_pace_min_km > 0:
            return round(60 / self.avg_flat_pace_min_km, 2)
        return None

    def get_sample_count(self, category: str) -> int:
        """Get sample count for a legacy 7-category gradient."""
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

    def get_pace_for_category(self, category: str) -> Optional[float]:
        """Get avg pace from JSON (11-cat), fallback to legacy column (7-cat)."""
        if self.gradient_paces and category in self.gradient_paces:
            return self.gradient_paces[category].get('avg')
        # Fallback to legacy column
        legacy_name = LEGACY_CATEGORY_MAPPING.get(category)
        if legacy_name:
            field = f"avg_{legacy_name}_pace_min_km"
            return getattr(self, field, None)
        return None

    def get_percentile(self, category: str, percentile: str) -> Optional[float]:
        """Get percentile (p25/p50/p75) for a gradient category."""
        if not self.gradient_percentiles:
            return None
        cat_data = self.gradient_percentiles.get(category)
        if not cat_data:
            return None
        return cat_data.get(percentile)

    def get_sample_count_extended(self, category: str) -> int:
        """Get sample count from JSON (11-cat), fallback to legacy column."""
        if self.gradient_paces and category in self.gradient_paces:
            return self.gradient_paces[category].get('samples', 0)
        # Fallback to legacy column
        legacy_name = LEGACY_CATEGORY_MAPPING.get(category)
        if legacy_name:
            return self.get_sample_count(legacy_name)
        return 0

    def to_dict(self) -> dict:
        """Convert profile to dictionary for API responses."""
        return {
            # Legacy 3-category
            "avg_flat_pace_min_km": self.avg_flat_pace_min_km,
            "avg_uphill_pace_min_km": self.avg_uphill_pace_min_km,
            "avg_downhill_pace_min_km": self.avg_downhill_pace_min_km,
            # Extended 7-category
            "avg_steep_downhill_pace_min_km": self.avg_steep_downhill_pace_min_km,
            "avg_moderate_downhill_pace_min_km": self.avg_moderate_downhill_pace_min_km,
            "avg_gentle_downhill_pace_min_km": self.avg_gentle_downhill_pace_min_km,
            "avg_gentle_uphill_pace_min_km": self.avg_gentle_uphill_pace_min_km,
            "avg_moderate_uphill_pace_min_km": self.avg_moderate_uphill_pace_min_km,
            "avg_steep_uphill_pace_min_km": self.avg_steep_uphill_pace_min_km,
            # 11-category JSON
            "gradient_paces": self.gradient_paces,
            "gradient_percentiles": self.gradient_percentiles,
            # Coefficients and stats
            "vertical_ability": self.vertical_ability,
            "flat_speed_kmh": self.flat_speed_kmh,
            "total_activities_analyzed": self.total_activities_analyzed,
            "total_hike_activities": self.total_hike_activities,
            "total_distance_km": round(self.total_distance_km, 1) if self.total_distance_km else 0,
            "total_elevation_m": round(self.total_elevation_m, 0) if self.total_elevation_m else 0,
            "has_split_data": self.has_split_data,
            "has_extended_gradient_data": self.has_extended_gradient_data,
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
        }


# Backward compatibility alias
UserPerformanceProfile = UserHikingProfile
