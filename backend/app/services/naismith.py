"""
Naismith's Rule Implementation

Classic hiking time estimation formula from 1892.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ExperienceLevel(str, Enum):
    """Hiker experience level."""
    BEGINNER = "beginner"
    CASUAL = "casual"
    REGULAR = "regular"
    EXPERIENCED = "experienced"


class BackpackWeight(str, Enum):
    """Backpack weight category."""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass
class HikerProfile:
    """Profile for hiking time estimation."""
    experience: ExperienceLevel
    backpack: BackpackWeight
    group_size: int = 1
    max_altitude_m: float = 0
    has_children: bool = False
    has_elderly: bool = False
    first_time_altitude: bool = False


def naismith_time(distance_km: float, elevation_gain_m: float) -> float:
    """
    Classic Naismith's Rule (1892).

    - 5 km/hour on flat terrain
    - +1 hour per 600m elevation gain

    Args:
        distance_km: Total distance in kilometers
        elevation_gain_m: Total elevation gain in meters

    Returns:
        Estimated time in hours
    """
    horizontal_time = distance_km / 5.0
    vertical_time = elevation_gain_m / 600.0

    return horizontal_time + vertical_time


def naismith_with_descent(
    distance_km: float,
    elevation_gain_m: float,
    elevation_loss_m: float
) -> float:
    """
    Enhanced Naismith with Tranter's corrections (1970).

    Accounts for descent time:
    - Gentle descent: slightly faster
    - Steep descent: slower (knee stress, caution)

    Args:
        distance_km: Total distance
        elevation_gain_m: Total ascent
        elevation_loss_m: Total descent

    Returns:
        Estimated time in hours
    """
    base_time = naismith_time(distance_km, elevation_gain_m)

    # Steep descent adds ~10 min per 300m
    if elevation_loss_m > 0:
        descent_factor = elevation_loss_m / 300
        descent_time = descent_factor * (10 / 60)  # Convert to hours
        base_time += descent_time

    return base_time


def get_experience_multiplier(experience: ExperienceLevel) -> float:
    """Get time multiplier based on experience."""
    multipliers = {
        ExperienceLevel.BEGINNER: 1.5,
        ExperienceLevel.CASUAL: 1.2,
        ExperienceLevel.REGULAR: 1.0,
        ExperienceLevel.EXPERIENCED: 0.85
    }
    return multipliers.get(experience, 1.0)


def get_backpack_multiplier(backpack: BackpackWeight) -> float:
    """Get time multiplier based on backpack weight."""
    multipliers = {
        BackpackWeight.LIGHT: 1.0,
        BackpackWeight.MEDIUM: 1.1,
        BackpackWeight.HEAVY: 1.25
    }
    return multipliers.get(backpack, 1.0)


def get_group_multiplier(group_size: int) -> float:
    """Get time multiplier based on group size."""
    if group_size <= 2:
        return 1.0
    elif group_size <= 5:
        return 1.1
    else:
        return 1.3


def get_altitude_multiplier(max_altitude_m: float) -> float:
    """Get time multiplier based on maximum altitude."""
    if max_altitude_m < 2500:
        return 1.0
    elif max_altitude_m < 3000:
        return 1.1
    elif max_altitude_m < 3500:
        return 1.2
    else:
        return 1.35


def get_total_multiplier(profile: HikerProfile) -> float:
    """
    Calculate total time multiplier from hiker profile.

    All factors are multiplied together as they compound.
    """
    total = 1.0

    total *= get_experience_multiplier(profile.experience)
    total *= get_backpack_multiplier(profile.backpack)
    total *= get_group_multiplier(profile.group_size)
    total *= get_altitude_multiplier(profile.max_altitude_m)

    # Additional factors
    if profile.has_children:
        total *= 1.4
    if profile.has_elderly:
        total *= 1.3
    if profile.first_time_altitude and profile.max_altitude_m > 3000:
        total *= 1.15

    return round(total, 2)


def estimate_rest_time(duration_hours: float, experience: ExperienceLevel) -> float:
    """
    Estimate rest time based on hike duration and experience.

    Returns additional time in hours.
    """
    if experience == ExperienceLevel.BEGINNER:
        # 15 min rest per hour
        return (duration_hours // 1) * (15 / 60)
    elif experience == ExperienceLevel.CASUAL:
        # 10 min rest per hour
        return (duration_hours // 1) * (10 / 60)
    else:
        # 10 min rest per 2 hours
        return (duration_hours // 2) * (10 / 60)


def calculate_start_time(
    estimated_hours: float,
    sunset: str = "20:00",
    safety_buffer: float = 1.0
) -> str:
    """
    Calculate recommended start time.

    Goal: Return at least 1 hour before sunset.

    Args:
        estimated_hours: Estimated hike duration
        sunset: Sunset time (HH:MM)
        safety_buffer: Hours of buffer before sunset

    Returns:
        Recommended start time (HH:MM)
    """
    sunset_hour = int(sunset.split(":")[0])
    target_return = sunset_hour - safety_buffer

    # Add 20% safety margin
    safe_duration = estimated_hours * 1.2

    start_hour = target_return - safe_duration

    # Not earlier than 5 AM
    if start_hour < 5:
        start_hour = 5

    return f"{int(start_hour):02d}:00"
