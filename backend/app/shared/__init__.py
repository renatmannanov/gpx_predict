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
from .gradients import (
    GRADIENT_THRESHOLDS,
    LEGACY_GRADIENT_THRESHOLDS,
    LEGACY_CATEGORY_MAPPING,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
    classify_gradient,
    classify_gradient_legacy,
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
from .repository import BaseRepository
from .telegram import TelegramNotifier, get_telegram_notifier
from .notification_formatter import format_notification

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
    # gradients
    "GRADIENT_THRESHOLDS",
    "LEGACY_GRADIENT_THRESHOLDS",
    "LEGACY_CATEGORY_MAPPING",
    "FLAT_GRADIENT_MIN",
    "FLAT_GRADIENT_MAX",
    "classify_gradient",
    "classify_gradient_legacy",
    # constants
    "ActivityType",
    "StravaActivityType",
    "PredictionType",
    "STRAVA_TO_ACTIVITY_TYPE",
    "STRAVA_TYPES_FOR_HIKING",
    "STRAVA_TYPES_FOR_TRAIL_RUN",
    "ALL_SUPPORTED_STRAVA_TYPES",
    # repository
    "BaseRepository",
    # telegram
    "TelegramNotifier",
    "get_telegram_notifier",
    # notification formatter
    "format_notification",
]
