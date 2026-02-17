"""
Trail run profile models.

Re-exports UserRunProfile from app.models.user_run_profile.

The actual model definition stays in app.models.user_run_profile
to avoid circular import issues.
"""

from app.models.user_run_profile import UserRunProfile

__all__ = ["UserRunProfile"]
