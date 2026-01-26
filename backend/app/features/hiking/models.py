"""
Hiking profile models.

Re-exports UserPerformanceProfile from app.models.user_profile
with the new name UserHikingProfile.

The actual model definition stays in app.models.user_profile
to avoid circular import issues.
"""
from app.models.user_profile import UserPerformanceProfile

# New name for the model
UserHikingProfile = UserPerformanceProfile

__all__ = ["UserHikingProfile", "UserPerformanceProfile"]
