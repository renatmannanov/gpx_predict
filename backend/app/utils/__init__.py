"""
DEPRECATED: Use app.shared

Utility functions re-exported for backward compatibility.
New code should import from app.shared directly.
"""

from app.utils.geo import haversine, calculate_total_distance, EARTH_RADIUS_KM
from app.utils.elevation import smooth_elevations, calculate_elevation_changes

__all__ = [
    "haversine",
    "calculate_total_distance",
    "EARTH_RADIUS_KM",
    "smooth_elevations",
    "calculate_elevation_changes",
]
