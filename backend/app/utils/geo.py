"""
DEPRECATED: Use app.shared.geo

Re-exports for backward compatibility.
"""

from app.shared.geo import (
    haversine,
    calculate_gradient,
    gradient_to_percent,
    gradient_to_degrees,
    calculate_total_distance,
    EARTH_RADIUS_KM,
)

__all__ = [
    "haversine",
    "calculate_gradient",
    "gradient_to_percent",
    "gradient_to_degrees",
    "calculate_total_distance",
    "EARTH_RADIUS_KM",
]
