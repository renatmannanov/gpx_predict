"""
Profile Snapshot Model

Stores historical snapshots of user profiles for tracking changes
across profile improvements (IQR filtering, percentiles, etc).
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey

from app.models.base import Base


class ProfileSnapshot(Base):
    """
    Stores a snapshot of user profile at a specific point in time.

    Used for:
    - Tracking profile evolution (before/after IQR, percentiles, etc.)
    - Rollback if needed
    - Comparing "before" and "after" for each improvement phase
    """

    __tablename__ = "profile_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    profile_type = Column(String(20), nullable=False)  # "run" or "hiking"
    reason = Column(String(100), nullable=False)  # e.g. "phase_1_iqr", "manual_recalc"
    profile_data = Column(JSON, nullable=False)  # full profile snapshot
    activities_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<ProfileSnapshot user={self.user_id[:8]}... "
            f"type={self.profile_type} reason={self.reason}>"
        )
