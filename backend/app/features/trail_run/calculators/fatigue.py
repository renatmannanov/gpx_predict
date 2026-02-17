"""
Runner Fatigue Service

Fatigue model adapted for trail runners.

Key differences from hiking:
1. Earlier threshold (2h vs 3h)
2. More aggressive degradation
3. Downhills degrade MORE than uphills late in race

References:
- UTMB Pacing Study (PMC7578994)
- Riegel's endurance formula
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# Runner fatigue constants
FATIGUE_THRESHOLD_HOURS = 2.0       # vs 3.0 for hiking
LINEAR_DEGRADATION = 0.05           # vs 0.03 for hiking
QUADRATIC_DEGRADATION = 0.008       # vs 0.005 for hiking
DOWNHILL_FATIGUE_MULTIPLIER = 1.5   # Downhills hurt more when tired

# Ultra adaptations
ULTRA_THRESHOLD_50K = 3.0   # Delayed fatigue for trained ultra runners
ULTRA_THRESHOLD_100K = 4.0


@dataclass
class RunnerFatigueConfig:
    """Configuration for runner fatigue model."""
    enabled: bool = False
    threshold_hours: float = FATIGUE_THRESHOLD_HOURS
    linear_rate: float = LINEAR_DEGRADATION
    quadratic_rate: float = QUADRATIC_DEGRADATION
    downhill_multiplier: float = DOWNHILL_FATIGUE_MULTIPLIER


class RunnerFatigueService:
    """
    Fatigue service for trail runners.

    Example multipliers (enabled, default config):
        2h  -> 1.00
        3h  -> 1.058 (+5.8%)
        4h  -> 1.13 (+13%)
        5h  -> 1.22 (+22%)
        6h  -> 1.33 (+33%)
        8h  -> 1.59 (+59%)
        10h -> 1.92 (+92%)

    Downhill at 6h -> 1.33 * 1.5 = 2.0 (+100%)
    """

    def __init__(self, config: Optional[RunnerFatigueConfig] = None):
        self.config = config or RunnerFatigueConfig()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @classmethod
    def create_enabled(
        cls,
        distance_km: Optional[float] = None,
        threshold_hours: Optional[float] = None
    ) -> "RunnerFatigueService":
        """
        Factory for enabled service with auto-adapted threshold.

        Args:
            distance_km: Total route distance (for ultra adaptation)
            threshold_hours: Manual override for threshold
        """
        if threshold_hours is not None:
            threshold = threshold_hours
        elif distance_km and distance_km >= 100:
            threshold = ULTRA_THRESHOLD_100K
        elif distance_km and distance_km >= 50:
            threshold = ULTRA_THRESHOLD_50K
        else:
            threshold = FATIGUE_THRESHOLD_HOURS

        config = RunnerFatigueConfig(
            enabled=True,
            threshold_hours=threshold
        )
        return cls(config)

    @classmethod
    def create_disabled(cls) -> "RunnerFatigueService":
        """Factory for disabled service."""
        return cls(RunnerFatigueConfig(enabled=False))

    def calculate_multiplier(
        self,
        elapsed_hours: float,
        is_downhill: bool = False
    ) -> float:
        """
        Calculate fatigue multiplier.

        Args:
            elapsed_hours: Time since start
            is_downhill: If True, apply extra downhill penalty

        Returns:
            Multiplier (1.0 = no effect)
        """
        if not self.config.enabled:
            return 1.0

        if elapsed_hours <= self.config.threshold_hours:
            return 1.0

        extra = elapsed_hours - self.config.threshold_hours

        base_mult = (
            1.0
            + self.config.linear_rate * extra
            + self.config.quadratic_rate * extra ** 2
        )

        if is_downhill:
            # Downhills hurt more when tired (muscle damage, braking)
            return base_mult * self.config.downhill_multiplier

        return base_mult

    def apply_to_segment(
        self,
        base_time_hours: float,
        elapsed_hours: float,
        gradient_percent: float = 0
    ) -> Tuple[float, float]:
        """
        Apply fatigue to segment time.

        Args:
            base_time_hours: Time without fatigue
            elapsed_hours: Time before this segment
            gradient_percent: Segment gradient (for downhill detection)

        Returns:
            (adjusted_time, multiplier)
        """
        if not self.config.enabled:
            return base_time_hours, 1.0

        # Downhill defined as < -5%
        is_downhill = gradient_percent < -5.0

        # Use midpoint for more accurate fatigue
        midpoint = elapsed_hours + base_time_hours / 2
        multiplier = self.calculate_multiplier(midpoint, is_downhill)

        return base_time_hours * multiplier, round(multiplier, 3)

    def get_info(self) -> Dict:
        """Get model info for API response."""
        if not self.config.enabled:
            return {"enabled": False, "model": "runner"}

        examples = {}
        for hours in [2, 3, 4, 5, 6, 8, 10]:
            examples[f"{hours}h"] = round(self.calculate_multiplier(hours, False), 3)
            examples[f"{hours}h_downhill"] = round(self.calculate_multiplier(hours, True), 3)

        return {
            "enabled": True,
            "model": "runner",
            "threshold_hours": self.config.threshold_hours,
            "linear_rate": self.config.linear_rate,
            "quadratic_rate": self.config.quadratic_rate,
            "downhill_multiplier": self.config.downhill_multiplier,
            "example_multipliers": examples
        }
