"""
Geographic utility functions.

This is the SINGLE SOURCE OF TRUTH for geographic calculations.
DO NOT duplicate these functions elsewhere.
"""
import math

# Earth radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calculate great-circle distance between two points.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in kilometers
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) *
        math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def calculate_gradient(
    distance_km: float,
    elevation_diff_m: float
) -> float:
    """
    Calculate gradient as decimal.

    Args:
        distance_km: Horizontal distance in km
        elevation_diff_m: Elevation difference in meters

    Returns:
        Gradient as decimal (0.10 = 10%)
    """
    if distance_km <= 0:
        return 0.0
    return elevation_diff_m / (distance_km * 1000)


def gradient_to_percent(gradient: float) -> float:
    """Convert gradient decimal to percent."""
    return gradient * 100


def gradient_to_degrees(gradient: float) -> float:
    """Convert gradient decimal to degrees."""
    return math.degrees(math.atan(gradient))


def calculate_total_distance(points: list[tuple[float, float, float]]) -> float:
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
