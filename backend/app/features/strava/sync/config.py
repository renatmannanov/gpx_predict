"""
Strava sync configuration constants.

Contains all configuration values for sync behavior.
"""

from app.shared.constants import (
    STRAVA_TYPES_FOR_HIKING,
    STRAVA_TYPES_FOR_TRAIL_RUN,
    ALL_SUPPORTED_STRAVA_TYPES,
)


# Re-export with consistent naming
ACTIVITY_TYPES_FOR_HIKE_PROFILE = STRAVA_TYPES_FOR_HIKING
ACTIVITY_TYPES_FOR_RUN_PROFILE = STRAVA_TYPES_FOR_TRAIL_RUN
ALL_SUPPORTED_ACTIVITY_TYPES = ALL_SUPPORTED_STRAVA_TYPES


class SyncConfig:
    """Configuration for sync behavior."""

    # How many activities to fetch per API call
    ACTIVITIES_PER_PAGE = 30

    # How many activities to sync per user per batch
    ACTIVITIES_PER_USER_BATCH = 10

    # How many users to process per batch
    USERS_PER_BATCH = 5

    # Minimum interval between syncs for same user (hours)
    MIN_SYNC_INTERVAL_HOURS = 6

    # How far back to sync (days)
    MAX_HISTORY_DAYS = 365

    # Delay between API calls (seconds) to respect rate limits
    API_CALL_DELAY = 1.5

    # ==========================================================================
    # Profile Recalculation Strategy (during initial sync)
    # ==========================================================================
    # Recalculate profile at these checkpoints to avoid spam:
    # 1. After first 5 activities (quick feedback)
    # 2. At 30% completion
    # 3. At 60% completion
    # 4. At 100% completion (initial sync done)
    INITIAL_RECALC_AFTER_N_ACTIVITIES = 5
    INITIAL_RECALC_PROGRESS_CHECKPOINTS = [30, 60]  # percent

    # ==========================================================================
    # Post-Initial Sync Strategy
    # ==========================================================================
    # After initial sync is complete, recalculate when:
    # - At least N new activities with splits have been synced
    # This avoids recalculating for every single new activity
    POST_SYNC_RECALC_MIN_NEW_ACTIVITIES = 3

    # Progress notification interval
    PROGRESS_NOTIFICATION_INTERVAL = 10
