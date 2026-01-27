"""
Unified constants for activity types and predictions.

This module provides a single source of truth for activity type naming
across the entire application.
"""

from enum import Enum


class ActivityType(str, Enum):
    """
    Our internal activity types for predictions.

    Used in:
    - User preferences (preferred_activity_type)
    - Prediction requests
    - Profile types
    """
    HIKING = "hiking"
    TRAIL_RUN = "trail_run"
    # Future: ROAD_RUN = "road_run"


class StravaActivityType(str, Enum):
    """
    Activity types from Strava API.

    These are Strava's naming conventions, not ours.
    Use STRAVA_TO_ACTIVITY_TYPE to map to our types.
    """
    RUN = "Run"
    TRAIL_RUN = "TrailRun"
    VIRTUAL_RUN = "VirtualRun"
    HIKE = "Hike"
    WALK = "Walk"


# Mapping: Strava type -> our ActivityType
STRAVA_TO_ACTIVITY_TYPE: dict[StravaActivityType, ActivityType] = {
    StravaActivityType.HIKE: ActivityType.HIKING,
    StravaActivityType.WALK: ActivityType.HIKING,
    StravaActivityType.RUN: ActivityType.TRAIL_RUN,
    StravaActivityType.TRAIL_RUN: ActivityType.TRAIL_RUN,
    StravaActivityType.VIRTUAL_RUN: ActivityType.TRAIL_RUN,
}


# Strava types used for each profile calculation
STRAVA_TYPES_FOR_HIKING: list[str] = [
    StravaActivityType.HIKE.value,
    StravaActivityType.WALK.value,
]

STRAVA_TYPES_FOR_TRAIL_RUN: list[str] = [
    StravaActivityType.RUN.value,
    StravaActivityType.TRAIL_RUN.value,
    StravaActivityType.VIRTUAL_RUN.value,
]

# All supported activity types for sync
ALL_SUPPORTED_STRAVA_TYPES: list[str] = (
    STRAVA_TYPES_FOR_HIKING + STRAVA_TYPES_FOR_TRAIL_RUN
)


class PredictionType(str, Enum):
    """
    Type of prediction request.

    Corresponds to ActivityType but used specifically in prediction context.
    """
    HIKING = "hiking"
    TRAIL_RUN = "trail_run"
