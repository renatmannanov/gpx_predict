"""
Hike/Run Threshold Service

Determines when a trail runner should walk vs run based on gradient.
Supports static and dynamic thresholds.

References:
- University of Colorado Boulder (walking efficiency study)
- Runner's World power hiking guide
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from app.shared.calculator_types import MacroSegment
from app.shared.constants import DEFAULT_HIKE_THRESHOLD_PERCENT


class MovementMode(Enum):
    """Movement mode for a segment."""
    RUN = "run"
    HIKE = "hike"


@dataclass
class HikeRunDecision:
    """Decision for a single segment."""
    segment: MacroSegment
    mode: MovementMode
    threshold_used: float       # Threshold that triggered the decision (%)
    reason: str
    confidence: float           # 0.0 - 1.0


class HikeRunThresholdService:
    """
    Service for determining run vs walk mode on trail segments.

    Supports:
    - Static threshold: fixed gradient cutoff
    - Dynamic threshold: adjusts based on fatigue/distance
    - Personalization: learn threshold from Strava data
    """

    # Default thresholds - use centralized constant
    DEFAULT_UPHILL_THRESHOLD = DEFAULT_HIKE_THRESHOLD_PERCENT  # % gradient
    DEFAULT_DOWNHILL_THRESHOLD = -30.0   # % gradient (very steep technical)

    # Bounds for threshold adjustment
    MIN_THRESHOLD = DEFAULT_HIKE_THRESHOLD_PERCENT
    MAX_THRESHOLD = 35.0

    def __init__(
        self,
        uphill_threshold: Optional[float] = None,
        downhill_threshold: Optional[float] = None,
        dynamic: bool = False
    ):
        """
        Args:
            uphill_threshold: Gradient (%) above which to walk
            downhill_threshold: Gradient (%) below which to walk (steep descent)
            dynamic: If True, threshold decreases with fatigue
        """
        # Use None defaults to avoid Python's early binding issue with class attributes
        self.base_uphill_threshold = uphill_threshold if uphill_threshold is not None else DEFAULT_HIKE_THRESHOLD_PERCENT
        self.downhill_threshold = downhill_threshold if downhill_threshold is not None else -30.0
        self.dynamic = dynamic

    @classmethod
    def from_user_preference(
        cls,
        uphill_threshold: Optional[float] = None,
        dynamic: bool = False
    ) -> "HikeRunThresholdService":
        """Create service from user's manual preference."""
        return cls(
            uphill_threshold=uphill_threshold or cls.DEFAULT_UPHILL_THRESHOLD,
            dynamic=dynamic
        )

    @classmethod
    def from_strava_profile(
        cls,
        run_splits: List[dict],
        dynamic: bool = False
    ) -> "HikeRunThresholdService":
        """
        Detect threshold from Strava Run activity splits.

        Looks for the gradient where pace suddenly jumps (indicating walk).

        Args:
            run_splits: List of dicts with gradient_percent and pace_min_km
            dynamic: Enable dynamic threshold
        """
        if not run_splits or len(run_splits) < 10:
            return cls(dynamic=dynamic)

        # Sort by gradient
        sorted_splits = sorted(run_splits, key=lambda x: x.get("gradient_percent", 0))
        uphill_splits = [s for s in sorted_splits if s.get("gradient_percent", 0) > 5]

        if len(uphill_splits) < 5:
            return cls(dynamic=dynamic)

        # Find steepest pace derivative (where pace jumps)
        max_derivative = 0
        threshold = cls.DEFAULT_UPHILL_THRESHOLD

        for i in range(1, len(uphill_splits)):
            prev = uphill_splits[i - 1]
            curr = uphill_splits[i]

            prev_pace = prev.get("pace_min_km", 0)
            curr_pace = curr.get("pace_min_km", 0)
            prev_grad = prev.get("gradient_percent", 0)
            curr_grad = curr.get("gradient_percent", 0)

            pace_change = curr_pace - prev_pace
            gradient_change = curr_grad - prev_grad

            if gradient_change > 0 and pace_change > 0:
                derivative = pace_change / gradient_change
                if derivative > max_derivative:
                    max_derivative = derivative
                    threshold = (prev_grad + curr_grad) / 2

        # Clamp to reasonable range
        threshold = max(cls.MIN_THRESHOLD, min(cls.MAX_THRESHOLD, threshold))
        return cls(uphill_threshold=threshold, dynamic=dynamic)

    def get_threshold(
        self,
        elapsed_hours: float = 0,
        total_distance_km: float = 0
    ) -> float:
        """
        Get current threshold, adjusted for fatigue if dynamic=True.

        Args:
            elapsed_hours: Time since start
            total_distance_km: Total route distance (for ultra adjustments)

        Returns:
            Current uphill threshold (%)
        """
        if not self.dynamic:
            return self.base_uphill_threshold

        threshold = self.base_uphill_threshold

        # Fatigue: lower threshold after 2 hours (walk earlier when tired)
        if elapsed_hours > 2:
            fatigue_reduction = min(5.0, (elapsed_hours - 2) * 1.5)
            threshold -= fatigue_reduction

        # Ultra distance: lower threshold for 50k+
        if total_distance_km > 50:
            distance_reduction = min(3.0, (total_distance_km - 50) / 25)
            threshold -= distance_reduction

        return max(self.MIN_THRESHOLD, threshold)

    def decide(
        self,
        segment: MacroSegment,
        elapsed_hours: float = 0,
        total_distance_km: float = 0
    ) -> HikeRunDecision:
        """
        Decide run vs walk for a single segment.

        Args:
            segment: MacroSegment to evaluate
            elapsed_hours: Elapsed time (for dynamic threshold)
            total_distance_km: Total route distance (for ultra adjustment)

        Returns:
            HikeRunDecision with mode and explanation
        """
        gradient = segment.gradient_percent
        threshold = self.get_threshold(elapsed_hours, total_distance_km)

        # Steep uphill -> walk
        if gradient >= threshold:
            return HikeRunDecision(
                segment=segment,
                mode=MovementMode.HIKE,
                threshold_used=threshold,
                reason=f"Steep uphill ({gradient:.1f}% >= {threshold:.1f}%)",
                confidence=0.9 if gradient > threshold + 5 else 0.7
            )

        # Very steep downhill -> walk (technical terrain)
        if gradient <= self.downhill_threshold:
            return HikeRunDecision(
                segment=segment,
                mode=MovementMode.HIKE,
                threshold_used=self.downhill_threshold,
                reason=f"Technical descent ({gradient:.1f}% <= {self.downhill_threshold}%)",
                confidence=0.8
            )

        # Otherwise -> run
        return HikeRunDecision(
            segment=segment,
            mode=MovementMode.RUN,
            threshold_used=threshold,
            reason="Runnable gradient",
            confidence=0.9
        )

    def process_route(
        self,
        segments: List[MacroSegment],
        total_distance_km: float = 0
    ) -> List[HikeRunDecision]:
        """
        Process all segments and return decisions.

        Uses iterative time estimation for dynamic threshold.

        Args:
            segments: Route segments
            total_distance_km: Total route distance

        Returns:
            List of HikeRunDecision for each segment
        """
        decisions = []
        elapsed_hours = 0.0

        for segment in segments:
            decision = self.decide(segment, elapsed_hours, total_distance_km)
            decisions.append(decision)

            # Estimate time for next iteration (rough)
            avg_speed = 9.0 if decision.mode == MovementMode.RUN else 4.5
            elapsed_hours += segment.distance_km / avg_speed

        return decisions

    def get_summary(self, decisions: List[HikeRunDecision]) -> dict:
        """
        Get summary statistics from route decisions.

        Args:
            decisions: List of decisions from process_route()

        Returns:
            Summary dict with run/hike stats
        """
        if not decisions:
            return {
                "total_segments": 0,
                "run_segments": 0,
                "hike_segments": 0,
                "run_distance_km": 0,
                "hike_distance_km": 0,
                "run_percent": 0,
            }

        run_decisions = [d for d in decisions if d.mode == MovementMode.RUN]
        hike_decisions = [d for d in decisions if d.mode == MovementMode.HIKE]

        run_distance = sum(d.segment.distance_km for d in run_decisions)
        hike_distance = sum(d.segment.distance_km for d in hike_decisions)
        total_distance = run_distance + hike_distance

        return {
            "total_segments": len(decisions),
            "run_segments": len(run_decisions),
            "hike_segments": len(hike_decisions),
            "run_distance_km": round(run_distance, 2),
            "hike_distance_km": round(hike_distance, 2),
            "run_percent": round(run_distance / total_distance * 100, 1) if total_distance > 0 else 0,
        }

    def get_info(self) -> dict:
        """Get service configuration for API response."""
        return {
            "uphill_threshold": self.base_uphill_threshold,
            "downhill_threshold": self.downhill_threshold,
            "dynamic": self.dynamic,
            "example_thresholds": {
                "start": self.get_threshold(0, 0),
                "after_2h": self.get_threshold(2.5, 20) if self.dynamic else self.base_uphill_threshold,
                "after_4h": self.get_threshold(4.0, 40) if self.dynamic else self.base_uphill_threshold,
                "ultra_6h": self.get_threshold(6.0, 60) if self.dynamic else self.base_uphill_threshold,
            }
        }
