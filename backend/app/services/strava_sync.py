"""
DEPRECATED: Use app.features.strava.sync

Re-exports for backward compatibility.
"""

from app.features.strava.sync import (
    StravaSyncService,
    ActivitySyncService,
    SplitsSyncService,
    BackgroundSyncRunner,
    background_sync,
    sync_queue,
    trigger_user_sync,
    get_sync_stats,
    SyncConfig,
    ACTIVITY_TYPES_FOR_HIKE_PROFILE,
    ACTIVITY_TYPES_FOR_RUN_PROFILE,
    ALL_SUPPORTED_ACTIVITY_TYPES,
)

# Legacy: SyncQueueManager exported via sync_queue instance
SyncQueueManager = type(sync_queue)

__all__ = [
    "StravaSyncService",
    "ActivitySyncService",
    "SplitsSyncService",
    "BackgroundSyncRunner",
    "background_sync",
    "sync_queue",
    "SyncQueueManager",
    "trigger_user_sync",
    "get_sync_stats",
    "SyncConfig",
    "ACTIVITY_TYPES_FOR_HIKE_PROFILE",
    "ACTIVITY_TYPES_FOR_RUN_PROFILE",
    "ALL_SUPPORTED_ACTIVITY_TYPES",
]
