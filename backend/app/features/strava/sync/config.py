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
    # First Batch Quality Threshold
    # ==========================================================================
    # After first batch, determines the message text:
    # - 0 activities: "No suitable activities"
    # - 1-4 activities: "Profile preliminary"
    # - 5+ activities: "Profile basic"
    FIRST_BATCH_QUALITY_THRESHOLD = 5

    # ==========================================================================
    # Sync Progress Checkpoints
    # ==========================================================================
    # After first batch, recalculate profile and send notification at these
    # percentages of total_activities_estimated
    SYNC_PROGRESS_CHECKPOINTS = [30, 60, 100]  # percent

    # ==========================================================================
    # Post-Initial Sync Strategy
    # ==========================================================================
    # After initial sync is complete, recalculate when:
    # - At least N new activities with splits have been synced
    # This avoids recalculating for every single new activity
    POST_SYNC_RECALC_MIN_NEW_ACTIVITIES = 3

    # ==========================================================================
    # Priority Sync Settings (for new users after OAuth)
    # ==========================================================================
    # Optimized for 20 users/day with Strava rate limits:
    # - 100 requests / 15 min
    # - 1000 requests / day
    # 1 batch = ~11 requests, so 4 batches = 44 requests per user
    # 1000 / 50 (requests per user) = 20 users/day capacity
    PRIORITY_SYNC_BATCH_DELAY_SECONDS = 90  # seconds between batches
    PRIORITY_SYNC_MAX_CONSECUTIVE_BATCHES = 4  # max batches per priority sync

    # Background sync interval (seconds)
    BACKGROUND_SYNC_INTERVAL_SECONDS = 300  # 5 minutes
