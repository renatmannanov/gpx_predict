"""
Fatigue Service

Applies fatigue factor to route calculations.
Models the slowdown that occurs during long hikes due to accumulated tiredness.

Based on:
- Tranter's corrections for Naismith's rule
- Marathon pacing research (Frontiers in Psychology, 2023)
- Riegel's endurance formula
"""

from dataclasses import dataclass
from typing import List, Tuple


# Fatigue model parameters
# After this many hours, fatigue starts to accumulate
FATIGUE_THRESHOLD_HOURS = 3.0

# Linear component: X% slowdown per hour after threshold
LINEAR_DEGRADATION_PER_HOUR = 0.03  # 3%

# Quadratic component: additional slowdown that accelerates over time
QUADRATIC_DEGRADATION = 0.005


@dataclass
class FatigueConfig:
    """Configuration for fatigue model."""
    enabled: bool = False
    threshold_hours: float = FATIGUE_THRESHOLD_HOURS
    linear_rate: float = LINEAR_DEGRADATION_PER_HOUR
    quadratic_rate: float = QUADRATIC_DEGRADATION


class FatigueService:
    """
    Service for applying fatigue adjustments to route time calculations.

    The fatigue model is based on research showing that:
    - Minimal fatigue effect in first 3-4 hours
    - Progressive slowdown after threshold
    - Non-linear (accelerating) fatigue in very long efforts

    Formula:
        if elapsed <= threshold:
            multiplier = 1.0
        else:
            extra = elapsed - threshold
            multiplier = 1 + (linear_rate * extra) + (quadratic_rate * extra^2)

    Example multipliers (with default config):
        3h  → 1.00 (no effect)
        4h  → 1.035 (+3.5%)
        5h  → 1.08 (+8%)
        6h  → 1.135 (+13.5%)
        7h  → 1.20 (+20%)
        8h  → 1.275 (+27.5%)
        10h → 1.46 (+46%)
    """

    def __init__(self, config: FatigueConfig = None):
        """
        Initialize fatigue service.

        Args:
            config: FatigueConfig with model parameters.
                   If None, uses default disabled config.
        """
        self.config = config or FatigueConfig()

    @property
    def enabled(self) -> bool:
        """Check if fatigue calculation is enabled."""
        return self.config.enabled

    def calculate_multiplier(self, elapsed_hours: float) -> float:
        """
        Calculate fatigue multiplier for given elapsed time.

        Args:
            elapsed_hours: Time elapsed since start of hike

        Returns:
            Multiplier to apply to pace (1.0 = no change, 1.2 = 20% slower)
        """
        if not self.config.enabled:
            return 1.0

        if elapsed_hours <= self.config.threshold_hours:
            return 1.0

        extra = elapsed_hours - self.config.threshold_hours

        # Non-linear fatigue model: linear + quadratic components
        multiplier = (
            1.0
            + (self.config.linear_rate * extra)
            + (self.config.quadratic_rate * extra ** 2)
        )

        return multiplier

    def apply_to_segment(
        self,
        segment_time_hours: float,
        cumulative_time_hours: float
    ) -> Tuple[float, float]:
        """
        Apply fatigue to a single segment (per-segment calculation).

        Uses midpoint of segment for fatigue calculation to get
        more accurate average fatigue during segment traversal.

        Args:
            segment_time_hours: Base time for this segment (without fatigue)
            cumulative_time_hours: Time elapsed before this segment

        Returns:
            Tuple of (adjusted_time_hours, fatigue_multiplier)
        """
        if not self.config.enabled:
            return segment_time_hours, 1.0

        # Calculate fatigue at segment midpoint for better accuracy
        midpoint_time = cumulative_time_hours + (segment_time_hours / 2)
        multiplier = self.calculate_multiplier(midpoint_time)

        adjusted_time = segment_time_hours * multiplier

        return adjusted_time, multiplier

    def apply_to_route(
        self,
        segment_times: List[float]
    ) -> Tuple[List[float], List[float], float]:
        """
        Apply fatigue to entire route, segment by segment.

        This is the recommended method for accurate fatigue modeling.
        Each segment's time is adjusted based on cumulative elapsed time.

        Args:
            segment_times: List of base times for each segment (hours)

        Returns:
            Tuple of:
            - adjusted_times: List of adjusted times for each segment
            - multipliers: List of fatigue multipliers applied to each segment
            - total_time: Total adjusted time for the route
        """
        if not self.config.enabled:
            return segment_times, [1.0] * len(segment_times), sum(segment_times)

        adjusted_times = []
        multipliers = []
        cumulative_time = 0.0

        for base_time in segment_times:
            adjusted_time, multiplier = self.apply_to_segment(
                base_time,
                cumulative_time
            )
            adjusted_times.append(adjusted_time)
            multipliers.append(multiplier)
            cumulative_time += adjusted_time

        return adjusted_times, multipliers, cumulative_time

    def estimate_total_with_fatigue(
        self,
        base_time_hours: float
    ) -> Tuple[float, float]:
        """
        Quick estimate of total time with fatigue (post-processing method).

        Less accurate than per-segment calculation but useful for
        quick estimates. Applies average fatigue over entire route.

        Args:
            base_time_hours: Total base time without fatigue

        Returns:
            Tuple of (adjusted_time_hours, average_multiplier)
        """
        if not self.config.enabled:
            return base_time_hours, 1.0

        # Use 2/3 of total time as representative point
        # (accounts for slower pace in second half)
        representative_time = base_time_hours * 0.67
        multiplier = self.calculate_multiplier(representative_time)

        return base_time_hours * multiplier, multiplier

    @staticmethod
    def create_enabled(
        threshold_hours: float = FATIGUE_THRESHOLD_HOURS,
        linear_rate: float = LINEAR_DEGRADATION_PER_HOUR,
        quadratic_rate: float = QUADRATIC_DEGRADATION
    ) -> 'FatigueService':
        """
        Factory method to create an enabled FatigueService.

        Args:
            threshold_hours: Hours before fatigue kicks in
            linear_rate: Linear degradation rate per hour
            quadratic_rate: Quadratic degradation rate

        Returns:
            Configured and enabled FatigueService
        """
        config = FatigueConfig(
            enabled=True,
            threshold_hours=threshold_hours,
            linear_rate=linear_rate,
            quadratic_rate=quadratic_rate
        )
        return FatigueService(config)

    def get_fatigue_info(self) -> dict:
        """
        Get fatigue model info for API responses.

        Returns:
            Dict with model configuration and example multipliers
        """
        if not self.config.enabled:
            return {"enabled": False}

        # Calculate example multipliers
        examples = {}
        for hours in [3, 4, 5, 6, 7, 8, 10, 12]:
            mult = self.calculate_multiplier(hours)
            examples[f"{hours}h"] = round(mult, 3)

        return {
            "enabled": True,
            "threshold_hours": self.config.threshold_hours,
            "linear_rate": self.config.linear_rate,
            "quadratic_rate": self.config.quadratic_rate,
            "example_multipliers": examples
        }
