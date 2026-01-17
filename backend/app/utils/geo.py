"""
Geographic utility functions.

Shared functions for distance calculations.
"""

import math
from typing import Tuple, List


# Earth radius in kilometers
EARTH_RADIUS_KM = 6371


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula for calculating distances on a sphere.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance in kilometers

    Example:
        >>> haversine(55.7558, 37.6173, 59.9343, 30.3351)  # Moscow to St. Petersburg
        634.37...
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_KM * c


def calculate_total_distance(points: List[Tuple[float, float, float]]) -> float:
    """
    Calculate total distance for a route.

    Args:
        points: List of (lat, lon, elevation) tuples

    Returns:
        Total distance in kilometers
    """
    total = 0.0

    for i in range(1, len(points)):
        lat1, lon1, _ = points[i - 1]
        lat2, lon2, _ = points[i]
        total += haversine(lat1, lon1, lat2, lon2)

    return total
