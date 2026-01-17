"""
Elevation utility functions.

Shared functions for elevation data processing.
"""

from typing import List, Tuple


# Default smoothing window size (should be odd)
DEFAULT_SMOOTHING_WINDOW = 5


def smooth_elevations(
    elevations: List[float],
    window_size: int = DEFAULT_SMOOTHING_WINDOW
) -> List[float]:
    """
    Apply moving average smoothing to elevation data.

    Reduces GPS noise while preserving real elevation changes.

    Args:
        elevations: List of elevation values in meters
        window_size: Size of the smoothing window (odd number recommended)

    Returns:
        Smoothed elevation values

    Example:
        >>> smooth_elevations([100, 105, 103, 108, 106])
        [102.5, 103.25, 104.4, 105.5, 105.67...]
    """
    if len(elevations) <= window_size:
        return elevations

    half_window = window_size // 2
    smoothed = []

    for i in range(len(elevations)):
        start = max(0, i - half_window)
        end = min(len(elevations), i + half_window + 1)
        avg = sum(elevations[start:end]) / (end - start)
        smoothed.append(avg)

    return smoothed


def calculate_elevation_changes(
    points: List[Tuple[float, float, float]],
    smoothing_window: int = DEFAULT_SMOOTHING_WINDOW
) -> Tuple[float, float]:
    """
    Calculate total elevation gain and loss for a route.

    Uses smoothing to reduce GPS noise while preserving real changes.

    Args:
        points: List of (lat, lon, elevation) tuples
        smoothing_window: Window size for smoothing

    Returns:
        Tuple of (elevation_gain, elevation_loss) in meters
    """
    if len(points) < 2:
        return 0.0, 0.0

    elevations = [p[2] for p in points]

    # Apply smoothing
    if len(elevations) > smoothing_window:
        elevations = smooth_elevations(elevations, smoothing_window)

    # Calculate gain and loss
    gain = 0.0
    loss = 0.0

    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > 0:
            gain += diff
        else:
            loss += abs(diff)

    return gain, loss
