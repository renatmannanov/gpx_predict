"""
Strava Activity Model

Stores aggregated activity data for calibration.
Only stores metrics allowed by Strava API Agreement (no GPS/polylines).
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from app.models.base import Base


class StravaActivity(Base):
    """
    Strava activity summary for calibration.

    Stores only aggregated metrics (allowed by Strava API Agreement).
    Does NOT store: GPS coordinates, polylines, splits, laps.
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

    # Sync metadata
    synced_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", backref="strava_activities")

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


class StravaSyncStatus(Base):
    """
    Tracks sync status per user for incremental syncing.
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

    # Status
    sync_in_progress = Column(Integer, default=0)  # Boolean as int for SQLite
    last_error = Column(String(500), nullable=True)

    # Relationship
    user = relationship("User", backref="strava_sync_status")
