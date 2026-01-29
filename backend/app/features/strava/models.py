"""
Strava-related database models.

Models:
- StravaToken: OAuth tokens for Strava API
- StravaActivity: Synchronized activity data
- StravaActivitySplit: Per-kilometer split data
- StravaSyncStatus: Sync progress tracking
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class StravaToken(Base):
    """
    Strava OAuth token storage.

    Stores access and refresh tokens for Strava API authentication.
    Tokens should be encrypted in production.
    """

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


class StravaActivity(Base):
    """
    Strava activity summary for calibration.

    Stores only aggregated metrics (allowed by Strava API Agreement).
    Does NOT store: GPS coordinates, polylines.
    Splits are stored separately (aggregated metrics per km).
    """

    __tablename__ = "strava_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Strava identifiers
    strava_id = Column(BigInteger, unique=True, nullable=False)  # Strava activity ID

    # Activity info
    name = Column(String(255), nullable=True)
    activity_type = Column(String(50), nullable=False)  # Run, Hike, Walk, etc.
    start_date = Column(DateTime, nullable=False, index=True)

    # Core metrics (aggregated - safe to store)
    distance_m = Column(Float, nullable=True)
    moving_time_s = Column(Integer, nullable=True)
    elapsed_time_s = Column(Integer, nullable=True)
    elevation_gain_m = Column(Float, nullable=True)
    elevation_loss_m = Column(Float, nullable=True)

    # Performance metrics
    avg_speed_mps = Column(Float, nullable=True)  # meters per second
    max_speed_mps = Column(Float, nullable=True)

    # Heart rate (if available)
    avg_heartrate = Column(Float, nullable=True)
    max_heartrate = Column(Float, nullable=True)

    # Running specific
    avg_cadence = Column(Float, nullable=True)  # steps per minute

    # Strava computed
    suffer_score = Column(Integer, nullable=True)  # Relative effort

    # Splits sync flag
    splits_synced = Column(Integer, default=0)  # Boolean as int for SQLite

    # Sync metadata
    synced_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="strava_activities")
    splits = relationship(
        "StravaActivitySplit",
        back_populates="activity",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<StravaActivity {self.strava_id} {self.activity_type} {self.distance_m}m>"

    @property
    def distance_km(self) -> float:
        """Distance in kilometers."""
        return round(self.distance_m / 1000, 2) if self.distance_m else 0

    @property
    def pace_min_per_km(self) -> float | None:
        """Average pace in min/km."""
        if not self.distance_m or not self.moving_time_s or self.distance_m == 0:
            return None
        return round((self.moving_time_s / 60) / (self.distance_m / 1000), 2)


class StravaActivitySplit(Base):
    """
    Split data (~1km segments) from Strava activity.

    Contains aggregated metrics per kilometer - safe to store long-term.
    Does NOT contain GPS coordinates or polylines.
    """

    __tablename__ = "strava_activity_splits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer,
        ForeignKey("strava_activities.id"),
        nullable=False,
        index=True
    )

    # Split info
    split_number = Column(Integer, nullable=False)  # 1, 2, 3...
    distance_m = Column(Float, nullable=False)      # Usually ~1000m

    # Time metrics
    moving_time_s = Column(Integer, nullable=False)
    elapsed_time_s = Column(Integer, nullable=False)

    # Elevation (key for terrain classification!)
    elevation_diff_m = Column(Float, nullable=True)  # +/- meters

    # Performance
    average_speed_mps = Column(Float, nullable=True)
    average_heartrate = Column(Float, nullable=True)
    pace_zone = Column(Integer, nullable=True)

    # Relationship
    activity = relationship("StravaActivity", back_populates="splits")

    def __repr__(self):
        return f"<Split #{self.split_number} {self.distance_m}m {self.elevation_diff_m}m>"

    @property
    def pace_min_km(self) -> Optional[float]:
        """Pace in minutes per kilometer."""
        if self.distance_m and self.moving_time_s and self.distance_m > 0:
            return round((self.moving_time_s / 60) / (self.distance_m / 1000), 2)
        return None

    @property
    def gradient_percent(self) -> Optional[float]:
        """Gradient as percentage."""
        if self.distance_m and self.elevation_diff_m is not None and self.distance_m > 0:
            return round((self.elevation_diff_m / self.distance_m) * 100, 1)
        return None


class StravaSyncStatus(Base):
    """
    Tracks sync status per user for incremental syncing.

    Used to:
    - Track sync progress during initial sync
    - Determine when to recalculate user profiles
    - Resume sync after interruption
    """

    __tablename__ = "strava_sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    # Sync progress
    last_sync_at = Column(DateTime, nullable=True)
    oldest_synced_date = Column(DateTime, nullable=True)  # How far back we've synced
    newest_synced_date = Column(DateTime, nullable=True)  # Most recent synced activity

    # Counts
    total_activities_synced = Column(Integer, default=0)
    total_activities_estimated = Column(Integer, nullable=True)  # Estimate from Strava stats
    activities_with_splits = Column(Integer, default=0)  # Activities with splits synced

    # Status
    sync_in_progress = Column(Integer, default=0)  # Boolean as int for SQLite
    initial_sync_complete = Column(Integer, default=0)  # Boolean: first full sync done
    last_error = Column(String(500), nullable=True)

    # Profile recalculation tracking
    # After initial sync: count of new activities since last profile recalc
    new_activities_since_recalc = Column(Integer, default=0)

    # Sync progress tracking (for notifications)
    # Flag: first batch processed and notification sent
    first_batch_notified = Column(Integer, default=0)  # Boolean as int
    # Last progress checkpoint reached (0, 30, 60, 100 percent)
    # Note: reuses last_recalc_checkpoint column with new semantics
    last_recalc_checkpoint = Column(Integer, default=0)

    # Relationship
    user = relationship("User", backref="strava_sync_status")
