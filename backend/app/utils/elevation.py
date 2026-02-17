"""
DEPRECATED: Use app.shared.elevation

Re-exports for backward compatibility.
"""

from app.shared.elevation import (
    smooth_elevations,
    calculate_elevation_changes,
    DEFAULT_SMOOTHING_WINDOW,
)

__all__ = [
    "smooth_elevations",
    "calculate_elevation_changes",
    "DEFAULT_SMOOTHING_WINDOW",
]
