"""
Tobler Calculator

Tobler's Hiking Function (1993) - exponential speed model.
"""

from app.shared.formulas import tobler_hiking_speed
from app.services.calculators.base import (
    PaceCalculator,
    MacroSegment,
    MethodResult,
    SegmentType
)


class ToblerCalculator(PaceCalculator):
    """
    Tobler's Hiking Function (1993).

    Formula: Speed = 6 * exp(-3.5 * |gradient + 0.05|) km/h

    Key characteristics:
    - Maximum speed 6 km/h at -5% gradient (slight downhill)
    - 5 km/h on flat terrain
    - Asymmetric: mild descent is faster than flat
    - More realistic for experienced hikers

    Based on Swiss military marching data (Imhof, 1950).
    """

    # Tobler constants
    MAX_SPEED = 6.0  # Maximum walking speed km/h
    DECAY_RATE = 3.5  # How quickly speed drops with gradient
    OPTIMAL_GRADIENT = -0.05  # Optimal gradient (-5%)

    @property
    def name(self) -> str:
        return "tobler"

    @property
    def description(self) -> str:
        return "Tobler's Hiking Function (1993) - gradient-adaptive"

    def calculate_segment(
        self,
        segment: MacroSegment,
        profile_multiplier: float = 1.0
    ) -> MethodResult:
        """
        Calculate time using Tobler's function.

        Uses average gradient to determine speed.
        """
        distance_km = segment.distance_km
        gradient_decimal = segment.gradient_percent / 100  # Convert to decimal

        # Tobler's formula
        speed_kmh = self._tobler_speed(gradient_decimal)

        # Time calculation
        base_hours = distance_km / speed_kmh if speed_kmh > 0 else float('inf')

        # Apply profile multiplier
        total_hours = base_hours * profile_multiplier

        # Recalculate effective speed after multiplier
        effective_speed = distance_km / total_hours if total_hours > 0 else 0

        formula = (
            f"6 * exp(-3.5 * |{gradient_decimal:.3f} + 0.05|) = {speed_kmh:.2f} km/h, "
            f"{distance_km:.1f}km / {speed_kmh:.2f}km/h = {base_hours:.2f}h"
        )

        return MethodResult(
            method_name=self.name,
            speed_kmh=round(effective_speed, 2),
            time_hours=round(total_hours, 3),
            formula_used=formula
        )

    def _tobler_speed(self, gradient: float) -> float:
        """
        Calculate walking speed using Tobler's function.

        Args:
            gradient: Slope as decimal (0.1 = 10%, -0.05 = -5%)

        Returns:
            Speed in km/h
        """
        return tobler_hiking_speed(gradient)

    @classmethod
    def speed_at_gradient(cls, gradient_percent: float) -> float:
        """
        Utility to get speed at a specific gradient.

        Args:
            gradient_percent: Gradient as percentage (10 = 10%)

        Returns:
            Speed in km/h
        """
        gradient_decimal = gradient_percent / 100
        return tobler_hiking_speed(gradient_decimal)
