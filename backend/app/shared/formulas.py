"""
Mathematical formulas for route time calculations.

These formulas are used by different calculators across the application.
Centralizing them here eliminates duplication and ensures consistency.
"""

import math


def tobler_hiking_speed(gradient_decimal: float) -> float:
    """
    Calculate walking speed using Tobler's Hiking Function (1993).

    Formula: v = 6 * exp(-3.5 * |s + 0.05|)

    Args:
        gradient_decimal: Slope as decimal (0.10 = 10%, -0.05 = -5%)
                         Positive = uphill, Negative = downhill

    Returns:
        Speed in km/h

    Notes:
        - Maximum speed (6 km/h) at -5% gradient (slight downhill)
        - Speed decreases exponentially with steeper gradients
        - Works well for typical hiking terrain

    References:
        Tobler, W. (1993). Three Presentations on Geographical Analysis
        and Modeling. NCGIA Technical Report 93-1.
    """
    OPTIMAL_GRADIENT = -0.05  # Slight downhill is optimal
    MAX_SPEED_KMH = 6.0
    DECAY_RATE = 3.5

    exponent = -DECAY_RATE * abs(gradient_decimal - OPTIMAL_GRADIENT)
    return MAX_SPEED_KMH * math.exp(exponent)


def naismith_base_time(distance_km: float, elevation_gain_m: float) -> float:
    """
    Calculate base hiking time using Naismith's Rule (1892).

    Rule: 5 km/h + 1 hour per 600m of ascent

    Args:
        distance_km: Horizontal distance in kilometers
        elevation_gain_m: Total elevation gain in meters

    Returns:
        Time in hours

    Notes:
        - Does not account for descent
        - Use with corrections for real-world estimates
    """
    BASE_SPEED_KMH = 5.0
    METERS_PER_HOUR_ASCENT = 600.0

    horizontal_time = distance_km / BASE_SPEED_KMH
    ascent_time = elevation_gain_m / METERS_PER_HOUR_ASCENT

    return horizontal_time + ascent_time
