"""
Shared utilities (NOT business logic).

Usage:
    from app.shared import haversine, smooth_elevations
    from app.shared.formatters import format_time_hours
"""
from .geo import (
    haversine,
    calculate_gradient,
    gradient_to_percent,
    gradient_to_degrees,
    calculate_total_distance,
    EARTH_RADIUS_KM,
)
from .elevation import (
    smooth_elevations,
    calculate_elevation_changes,
)
from .formatters import (
    format_time_hours,
    format_pace,
    format_distance_km,
    format_elevation,
)
from .formulas import (
    tobler_hiking_speed,
    naismith_base_time,
)
from .constants import (
    ActivityType,
    StravaActivityType,
    PredictionType,
    STRAVA_TO_ACTIVITY_TYPE,
    STRAVA_TYPES_FOR_HIKING,
    STRAVA_TYPES_FOR_TRAIL_RUN,
    ALL_SUPPORTED_STRAVA_TYPES,
)

__all__ = [
    # geo
    "haversine",
    "calculate_gradient",
    "gradient_to_percent",
    "gradient_to_degrees",
    "calculate_total_distance",
    "EARTH_RADIUS_KM",
    # elevation
    "smooth_elevations",
    "calculate_elevation_changes",
    # formatters
    "format_time_hours",
    "format_pace",
    "format_distance_km",
    "format_elevation",
    # formulas
    "tobler_hiking_speed",
    "naismith_base_time",
    # constants
    "ActivityType",
    "StravaActivityType",
    "PredictionType",
    "STRAVA_TO_ACTIVITY_TYPE",
    "STRAVA_TYPES_FOR_HIKING",
    "STRAVA_TYPES_FOR_TRAIL_RUN",
    "ALL_SUPPORTED_STRAVA_TYPES",
]
