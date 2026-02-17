"""
Strava sync services.

Provides:
- StravaSyncService: Main sync orchestrator
- ActivitySyncService: Activity fetching and saving
- SplitsSyncService: Splits fetching and saving
- BackgroundSyncRunner: Background sync task runner
"""

from .service import StravaSyncService
from .activities import ActivitySyncService
from .splits import SplitsSyncService
from .background import (
    BackgroundSyncRunner,
    background_sync,
    sync_queue,
    trigger_user_sync,
    get_sync_stats,
)
from .config import (
    SyncConfig,
    ACTIVITY_TYPES_FOR_HIKE_PROFILE,
    ACTIVITY_TYPES_FOR_RUN_PROFILE,
    ALL_SUPPORTED_ACTIVITY_TYPES,
)

__all__ = [
    # Services
    "StravaSyncService",
    "ActivitySyncService",
    "SplitsSyncService",
    # Background
    "BackgroundSyncRunner",
    "background_sync",
    "sync_queue",
    "trigger_user_sync",
    "get_sync_stats",
    # Config
    "SyncConfig",
    "ACTIVITY_TYPES_FOR_HIKE_PROFILE",
    "ACTIVITY_TYPES_FOR_RUN_PROFILE",
    "ALL_SUPPORTED_ACTIVITY_TYPES",
]
