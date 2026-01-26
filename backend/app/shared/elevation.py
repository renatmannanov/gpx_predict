"""
Elevation processing utilities.

This is the SINGLE SOURCE OF TRUTH for elevation calculations.
"""
from typing import List, Tuple


def smooth_elevations(
    elevations: List[float],
    window_size: int = 5
) -> List[float]:
    """
    Smooth elevation data using moving average.

    Args:
        elevations: Raw elevation values
        window_size: Size of smoothing window (odd number recommended)

    Returns:
        Smoothed elevation values
    """
    if len(elevations) < window_size:
        return elevations

    smoothed = []
    half_window = window_size // 2

    for i in range(len(elevations)):
        start = max(0, i - half_window)
        end = min(len(elevations), i + half_window + 1)
        window = elevations[start:end]
        smoothed.append(sum(window) / len(window))

    return smoothed


def calculate_elevation_changes(
    elevations: List[float]
) -> Tuple[float, float]:
    """
    Calculate total elevation gain and loss.

    Args:
        elevations: List of elevation values

    Returns:
        Tuple of (gain_m, loss_m)
    """
    gain = 0.0
    loss = 0.0

    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > 0:
            gain += diff
        else:
            loss += abs(diff)

    return gain, loss
