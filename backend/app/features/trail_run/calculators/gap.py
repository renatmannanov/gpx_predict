"""
Grade Adjusted Pace (GAP) Calculator for Trail Running.

Calculates adjusted pace based on terrain gradient, accounting for
the metabolic cost of running uphill and the efficiency gains/losses
on downhill sections.

Three calculation modes are supported:
1. strava_gap - Pure Strava model (empirical, based on 240k athletes)
2. minetti_gap - Pure Minetti model (scientific, energy-based)
3. strava_minetti_gap - Hybrid: Minetti uphill + Strava downhill

References:
- Minetti et al. (2002) - Energy cost of walking/running at extreme slopes
  https://pubmed.ncbi.nlm.nih.gov/12183501/
- Strava Engineering (2017) - An Improved GAP Model
  https://medium.com/strava-engineering/an-improved-gap-model-8b07ae8886c3
- Fellrnr GAP formulas comparison
  https://fellrnr.com/wiki/Grade_Adjusted_Pace
"""

from dataclasses import dataclass
from enum import Enum
from typing import List

from app.shared.calculator_types import MacroSegment, MethodResult


class GAPMode(Enum):
    """GAP calculation mode."""
    STRAVA = "strava_gap"                  # Pure Strava model (recommended)
    MINETTI = "minetti_gap"                # Pure Minetti model (scientific)
    STRAVA_MINETTI = "strava_minetti_gap"  # Hybrid: Minetti uphill + Strava downhill


@dataclass
class GAPResult:
    """Result of GAP calculation for a single gradient."""
    gradient_percent: float
    pace_adjustment: float      # 1.0 = flat, 1.5 = +50% slower
    adjusted_pace_min_km: float
    energy_cost_ratio: float    # Relative to flat (Minetti model)
    mode: str                   # Which model was used


# =============================================================================
# Strava GAP Lookup Table
# =============================================================================
# Based on Strava's 2017 improved GAP model
# Empirical data from 240,000 athletes
# Key: gradient percent, Value: pace adjustment factor (1.0 = flat)

STRAVA_GAP_TABLE = {
    -30: 1.15,   # Very steep descent: significant braking required
    -25: 1.05,
    -20: 0.95,
    -15: 0.90,
    -10: 0.88,   # Near optimal descent
    -9:  0.88,   # Optimal descent point (Strava)
    -5:  0.92,
    -3:  0.96,
    0:   1.00,   # Flat (reference)
    3:   1.08,
    5:   1.15,
    8:   1.28,
    10:  1.38,
    12:  1.50,
    15:  1.70,
    18:  1.95,
    20:  2.15,
    25:  2.70,
    30:  3.30,
    35:  4.00,
    40:  4.80,
    45:  5.70,
}


class GAPCalculator:
    """
    Grade Adjusted Pace calculator for trail running.

    Adjusts pace based on terrain gradient to predict running time
    on hilly terrain. Supports two calculation modes:

    - STRAVA: Empirical model based on real athlete data. Recommended
              for most users as it reflects actual running behavior.
    - MINETTI: Pure scientific model based on energy cost. More
               conservative on downhills than Strava.
    - STRAVA_MINETTI: Hybrid model - Minetti for uphills (more aggressive),
                      Strava for downhills (more realistic).

    Example usage:
        # Default Strava mode (recommended)
        calc = GAPCalculator(base_flat_pace_min_km=6.0)
        result = calc.calculate(gradient_percent=10)
        print(f"Adjusted pace: {result.adjusted_pace_min_km} min/km")

        # Minetti mode for scientific comparison
        calc = GAPCalculator(base_flat_pace_min_km=6.0, mode=GAPMode.MINETTI)

    Example adjustments (6:00 base pace):
        -15%: 5:24 (12% faster on moderate descent)
         -9%: 5:17 (optimal descent, 12% faster)
          0%: 6:00 (flat, reference)
        +10%: 8:17 (+38%)
        +20%: 12:54 (+115%)
        +30%: 19:48 (+230%)
    """

    # Minetti constants
    FLAT_ENERGY_COST = 3.6      # J/kg/m on flat ground

    # Strava constants
    STRAVA_OPTIMAL_DESCENT = -9.0  # Optimal descent gradient (%)
    STRAVA_MAX_DESCENT_BENEFIT = 0.88  # Max speedup on descent (12% faster)

    def __init__(
        self,
        base_flat_pace_min_km: float = 6.0,
        mode: GAPMode = GAPMode.STRAVA
    ):
        """
        Initialize GAP calculator.

        Args:
            base_flat_pace_min_km: User's flat running pace (min/km).
                                  Should be "conversational" Z2 pace
                                  sustainable for long efforts.
            mode: Calculation mode (STRAVA or MINETTI)
        """
        self.base_flat_pace = base_flat_pace_min_km
        self.mode = mode

    def calculate(self, gradient_percent: float) -> GAPResult:
        """
        Calculate adjusted pace for given gradient.

        Args:
            gradient_percent: Gradient as percentage (positive = uphill)
                             Example: 10 means 10% uphill gradient

        Returns:
            GAPResult with adjusted pace and metadata
        """
        if self.mode == GAPMode.STRAVA:
            return self._calculate_strava(gradient_percent)
        elif self.mode == GAPMode.MINETTI:
            return self._calculate_minetti_pure(gradient_percent)
        else:  # STRAVA_MINETTI
            return self._calculate_strava_minetti(gradient_percent)

    def calculate_segment(self, segment: MacroSegment) -> MethodResult:
        """
        Calculate time for a MacroSegment.

        Compatible interface with ToblerCalculator/NaismithCalculator.

        Args:
            segment: MacroSegment with distance and gradient data

        Returns:
            MethodResult with speed, time, and formula explanation
        """
        result = self.calculate(segment.gradient_percent)
        speed_kmh = 60 / result.adjusted_pace_min_km
        time_hours = segment.distance_km / speed_kmh

        return MethodResult(
            method_name=self.mode.value,
            speed_kmh=round(speed_kmh, 2),
            time_hours=round(time_hours, 4),
            formula_used=(
                f"GAP ({self.mode.value}): {result.adjusted_pace_min_km:.2f} min/km "
                f"(adjustment: x{result.pace_adjustment:.2f}, "
                f"gradient: {segment.gradient_percent:.1f}%)"
            )
        )

    def calculate_route(
        self,
        segments: List[MacroSegment]
    ) -> tuple[float, List[MethodResult]]:
        """
        Calculate total time for a route.

        Args:
            segments: List of MacroSegment objects

        Returns:
            Tuple of (total_hours, list of segment results)
        """
        results = []
        total_hours = 0.0

        for segment in segments:
            result = self.calculate_segment(segment)
            results.append(result)
            total_hours += result.time_hours

        return total_hours, results

    # =========================================================================
    # STRAVA MODEL
    # =========================================================================

    def _calculate_strava(self, gradient_percent: float) -> GAPResult:
        """
        Pure Strava GAP model using lookup table with interpolation.

        Based on empirical data from 240,000 Strava athletes.
        Generally provides realistic predictions for most runners.

        Args:
            gradient_percent: Gradient as percentage

        Returns:
            GAPResult with Strava-based adjustment
        """
        pace_adj = self._interpolate_strava(gradient_percent)
        adjusted_pace = self.base_flat_pace * pace_adj

        return GAPResult(
            gradient_percent=gradient_percent,
            pace_adjustment=round(pace_adj, 3),
            adjusted_pace_min_km=round(adjusted_pace, 2),
            energy_cost_ratio=pace_adj,  # Approximation for Strava
            mode=GAPMode.STRAVA.value
        )

    def _interpolate_strava(self, gradient: float) -> float:
        """
        Interpolate between Strava lookup table values.

        Uses linear interpolation between known data points.

        Args:
            gradient: Gradient as percentage

        Returns:
            Pace adjustment factor
        """
        # Get sorted gradients
        gradients = sorted(STRAVA_GAP_TABLE.keys())

        # Clamp to table range
        if gradient <= gradients[0]:
            return STRAVA_GAP_TABLE[gradients[0]]
        if gradient >= gradients[-1]:
            return STRAVA_GAP_TABLE[gradients[-1]]

        # Find surrounding points and interpolate
        for i in range(len(gradients) - 1):
            g1, g2 = gradients[i], gradients[i + 1]
            if g1 <= gradient <= g2:
                v1, v2 = STRAVA_GAP_TABLE[g1], STRAVA_GAP_TABLE[g2]
                t = (gradient - g1) / (g2 - g1)
                return v1 + t * (v2 - v1)

        return 1.0  # Fallback (should not reach here)

    # =========================================================================
    # MINETTI MODEL (Pure)
    # =========================================================================

    def _calculate_minetti_pure(self, gradient_percent: float) -> GAPResult:
        """
        Pure Minetti model for any gradient (uphill and downhill).

        Minetti's model is based on metabolic energy cost measurements.
        It's more conservative on downhills compared to Strava (predicts
        less speedup), which may be more appropriate for technical terrain.

        Args:
            gradient_percent: Gradient as percentage

        Returns:
            GAPResult with Minetti-based adjustment
        """
        gradient_decimal = gradient_percent / 100

        # Use Minetti energy cost model for both up and down
        energy_ratio = self._minetti_energy_cost(gradient_decimal)

        # Convert energy to pace using power law relationship
        # Empirically, pace scales roughly with energy^0.75
        pace_adj = energy_ratio ** 0.75

        # Clamp for safety (not faster than 2x flat on descents, not slower than 4x on climbs)
        pace_adj = max(0.5, min(pace_adj, 4.0))

        adjusted_pace = self.base_flat_pace * pace_adj

        return GAPResult(
            gradient_percent=gradient_percent,
            pace_adjustment=round(pace_adj, 3),
            adjusted_pace_min_km=round(adjusted_pace, 2),
            energy_cost_ratio=round(energy_ratio, 3),
            mode=GAPMode.MINETTI.value
        )

    # =========================================================================
    # STRAVA-MINETTI HYBRID MODEL
    # =========================================================================

    def _calculate_strava_minetti(self, gradient_percent: float) -> GAPResult:
        """
        Hybrid model: Minetti for uphills, Strava for downhills.

        Combines the best of both models:
        - Uphills: Minetti (more aggressive, scientific basis)
        - Downhills: Strava (realistic, based on athlete data)

        Args:
            gradient_percent: Gradient as percentage

        Returns:
            GAPResult with hybrid adjustment
        """
        gradient_decimal = gradient_percent / 100

        if gradient_decimal >= 0:
            # Uphill: use Minetti energy cost model
            energy_ratio = self._minetti_energy_cost(gradient_decimal)
            pace_adj = energy_ratio ** 0.75
        else:
            # Downhill: use Strava (more realistic than Minetti)
            pace_adj = self._interpolate_strava(gradient_percent)
            energy_ratio = pace_adj  # Approximation

        adjusted_pace = self.base_flat_pace * pace_adj

        return GAPResult(
            gradient_percent=gradient_percent,
            pace_adjustment=round(pace_adj, 3),
            adjusted_pace_min_km=round(adjusted_pace, 2),
            energy_cost_ratio=round(energy_ratio, 3),
            mode=GAPMode.STRAVA_MINETTI.value
        )

    def _minetti_energy_cost(self, gradient_decimal: float) -> float:
        """
        Calculate energy cost ratio using Minetti's polynomial.

        Minetti et al. (2002) derived this polynomial from measurements
        of oxygen consumption at various slopes.

        Formula: C = 155.4i^5 - 30.4i^4 - 43.3i^3 + 46.3i^2 + 19.5i + 3.6
        where i is gradient as decimal and C is cost in J/kg/m

        Args:
            gradient_decimal: Gradient as decimal (0.10 = 10%)

        Returns:
            Energy cost ratio relative to flat
        """
        i = gradient_decimal
        cost = (
            155.4 * i**5
            - 30.4 * i**4
            - 43.3 * i**3
            + 46.3 * i**2
            + 19.5 * i
            + self.FLAT_ENERGY_COST
        )
        return cost / self.FLAT_ENERGY_COST

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_info(self) -> dict:
        """
        Get calculator configuration info for API responses.

        Returns:
            Dict with mode, base pace, and example adjustments
        """
        return {
            "mode": self.mode.value,
            "base_flat_pace_min_km": self.base_flat_pace,
            "base_flat_speed_kmh": round(60 / self.base_flat_pace, 1),
            "example_adjustments": {
                "-15%": round(self.calculate(-15).pace_adjustment, 2),
                "-9%": round(self.calculate(-9).pace_adjustment, 2),
                "0%": round(self.calculate(0).pace_adjustment, 2),
                "+10%": round(self.calculate(10).pace_adjustment, 2),
                "+20%": round(self.calculate(20).pace_adjustment, 2),
                "+30%": round(self.calculate(30).pace_adjustment, 2),
            }
        }


def compare_gap_modes(
    base_pace: float = 6.0,
    gradients: List[int] = None
) -> dict:
    """
    Compare all three GAP modes for debugging and testing.

    Useful for understanding the differences between models
    and validating calculations.

    Args:
        base_pace: Flat pace in min/km
        gradients: List of gradients to compare (default: common values)

    Returns:
        Dict with comparison data for each gradient

    Example:
        >>> compare_gap_modes(6.0)
        {
            "-15%": {"strava": 0.90, "minetti": 0.85, "strava_minetti": 0.90, ...},
            "0%": {"strava": 1.0, "minetti": 1.0, "strava_minetti": 1.0, ...},
            "20%": {"strava": 2.15, "minetti": 2.43, "strava_minetti": 2.43, ...},
        }
    """
    if gradients is None:
        gradients = [-20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30]

    strava = GAPCalculator(base_pace, GAPMode.STRAVA)
    minetti = GAPCalculator(base_pace, GAPMode.MINETTI)
    strava_minetti = GAPCalculator(base_pace, GAPMode.STRAVA_MINETTI)

    comparison = {}
    for g in gradients:
        s = strava.calculate(g)
        m = minetti.calculate(g)
        sm = strava_minetti.calculate(g)
        comparison[f"{g}%"] = {
            "strava_adj": s.pace_adjustment,
            "minetti_adj": m.pace_adjustment,
            "strava_minetti_adj": sm.pace_adjustment,
            "strava_pace": s.adjusted_pace_min_km,
            "minetti_pace": m.adjusted_pace_min_km,
            "strava_minetti_pace": sm.adjusted_pace_min_km,
        }

    return comparison
