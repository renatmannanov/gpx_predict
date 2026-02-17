"""
Naismith Calculator

Classic Naismith's Rule (1892) with Langmuir corrections for descent.
"""

from app.shared.calculator_types import (
    PaceCalculator,
    MacroSegment,
    MethodResult,
    SegmentType
)


class NaismithCalculator(PaceCalculator):
    """
    Naismith's Rule with Langmuir descent corrections.

    Base formula (1892):
    - 5 km/h on flat terrain
    - +1 hour per 600m elevation gain

    Langmuir corrections (1984):
    - Gentle descent (5-12 degrees): -10 min per 300m (faster)
    - Steep descent (>12 degrees): +10 min per 300m (slower)

    This is a conservative estimate, good for beginners
    and safety-critical planning.
    """

    # Constants
    BASE_SPEED_KMH = 5.0  # Flat terrain speed
    CLIMB_RATE_M_PER_HOUR = 600.0  # Vertical meters per hour uphill

    # Langmuir descent thresholds (in degrees)
    GENTLE_DESCENT_MIN = 5.0
    GENTLE_DESCENT_MAX = 12.0

    @property
    def name(self) -> str:
        return "naismith"

    @property
    def description(self) -> str:
        return "Naismith's Rule (1892) - conservative estimate"

    def calculate_segment(
        self,
        segment: MacroSegment,
        profile_multiplier: float = 1.0
    ) -> MethodResult:
        """
        Calculate time using Naismith + Langmuir.

        For ascent: horizontal time + vertical time
        For descent: horizontal time +/- Langmuir correction
        """
        distance_km = segment.distance_km
        gradient_deg = abs(segment.gradient_degrees)

        # Horizontal time (always applies)
        horizontal_hours = distance_km / self.BASE_SPEED_KMH

        # Vertical component depends on direction
        if segment.segment_type == SegmentType.ASCENT:
            # Uphill: add time for elevation gain
            vertical_hours = segment.elevation_gain_m / self.CLIMB_RATE_M_PER_HOUR
            total_hours = horizontal_hours + vertical_hours

            formula = (
                f"{distance_km:.1f}km / {self.BASE_SPEED_KMH}km/h = {horizontal_hours:.2f}h + "
                f"{segment.elevation_gain_m:.0f}m / {self.CLIMB_RATE_M_PER_HOUR:.0f}m/h = {vertical_hours:.2f}h"
            )

        elif segment.segment_type == SegmentType.DESCENT:
            # Downhill: apply Langmuir corrections
            descent_m = segment.elevation_loss_m
            descent_correction = self._langmuir_correction(descent_m, gradient_deg)
            total_hours = horizontal_hours + descent_correction

            if descent_correction >= 0:
                correction_str = f"+{descent_correction:.2f}h (steep)"
            else:
                correction_str = f"{descent_correction:.2f}h (faster)"

            formula = (
                f"{distance_km:.1f}km / {self.BASE_SPEED_KMH}km/h = {horizontal_hours:.2f}h "
                f"{correction_str}"
            )

        else:  # FLAT
            total_hours = horizontal_hours
            formula = f"{distance_km:.1f}km / {self.BASE_SPEED_KMH}km/h = {horizontal_hours:.2f}h"

        # Apply profile multiplier
        total_hours *= profile_multiplier

        # Calculate effective speed
        speed_kmh = distance_km / total_hours if total_hours > 0 else 0

        return MethodResult(
            method_name=self.name,
            speed_kmh=round(speed_kmh, 2),
            time_hours=round(total_hours, 3),
            formula_used=formula
        )

    def _langmuir_correction(self, descent_m: float, gradient_deg: float) -> float:
        """
        Calculate Langmuir descent time correction.

        Returns hours to add (positive) or subtract (negative).
        """
        if gradient_deg < self.GENTLE_DESCENT_MIN:
            # Very gentle - no significant effect
            return 0.0
        elif gradient_deg <= self.GENTLE_DESCENT_MAX:
            # Gentle descent (5-12 deg): subtract 10 min per 300m
            return -(descent_m / 300) * (10 / 60)
        else:
            # Steep descent (>12 deg): add 10 min per 300m
            return (descent_m / 300) * (10 / 60)
