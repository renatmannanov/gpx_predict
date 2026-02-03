"""
Virtual route builder for backtesting.

Converts Strava activity splits into a format suitable for
running through our calculators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.features.strava.models import StravaActivity, StravaActivitySplit


@dataclass
class VirtualSegment:
    """One segment of a virtual route (typically ~1km)."""

    distance_m: float
    gradient_percent: float
    elevation_diff_m: float
    actual_time_s: int  # Ground truth from Strava


@dataclass
class VirtualRoute:
    """Virtual route built from Strava splits."""

    # Activity info
    activity_id: int
    strava_id: int
    activity_name: str
    activity_type: str
    activity_date: datetime

    # Segments
    segments: List[VirtualSegment] = field(default_factory=list)

    # Totals (calculated)
    @property
    def total_distance_m(self) -> float:
        return sum(s.distance_m for s in self.segments)

    @property
    def total_distance_km(self) -> float:
        return self.total_distance_m / 1000

    @property
    def total_elevation_gain_m(self) -> float:
        return sum(s.elevation_diff_m for s in self.segments if s.elevation_diff_m > 0)

    @property
    def total_elevation_loss_m(self) -> float:
        return abs(sum(s.elevation_diff_m for s in self.segments if s.elevation_diff_m < 0))

    @property
    def actual_total_time_s(self) -> int:
        return sum(s.actual_time_s for s in self.segments)

    @property
    def actual_total_time_hours(self) -> float:
        return self.actual_total_time_s / 3600


class VirtualRouteBuilder:
    """
    Builds virtual routes from Strava activities.

    Converts splits (1km segments with elevation data) into
    a format our calculators can process.
    """

    def build_from_activity(
        self,
        activity: StravaActivity,
        splits: List[StravaActivitySplit]
    ) -> Optional[VirtualRoute]:
        """
        Build a virtual route from activity and its splits.

        Args:
            activity: Strava activity record
            splits: List of splits for this activity

        Returns:
            VirtualRoute or None if not enough data
        """
        if not splits:
            return None

        segments = []
        for split in splits:
            # Skip invalid splits
            if not split.distance_m or split.distance_m <= 0:
                continue
            if split.moving_time_s is None or split.moving_time_s <= 0:
                continue

            # Calculate gradient if not available
            gradient = split.gradient_percent
            if gradient is None and split.elevation_diff_m is not None:
                gradient = (split.elevation_diff_m / split.distance_m) * 100

            # Default to 0 if still None
            if gradient is None:
                gradient = 0.0

            segment = VirtualSegment(
                distance_m=split.distance_m,
                gradient_percent=round(gradient, 1),
                elevation_diff_m=split.elevation_diff_m or 0.0,
                actual_time_s=split.moving_time_s,
            )
            segments.append(segment)

        if not segments:
            return None

        return VirtualRoute(
            activity_id=activity.id,
            strava_id=activity.strava_id,
            activity_name=activity.name or "Unnamed",
            activity_type=activity.activity_type,
            activity_date=activity.start_date,
            segments=segments,
        )
