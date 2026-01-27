"""
Hiking profile models.

Re-exports UserHikingProfile from app.models.user_profile.
"""
from app.models.user_profile import UserHikingProfile, UserPerformanceProfile

__all__ = ["UserHikingProfile", "UserPerformanceProfile"]
