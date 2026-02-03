"""
Calculator adapters for backtesting.

Runs virtual routes through our prediction calculators
and collects predicted times.
"""

from dataclasses import dataclass
from typing import Dict, Optional, List

from app.shared.calculator_types import MacroSegment, SegmentType
from app.features.trail_run.calculators.gap import GAPCalculator, GAPMode
from app.features.hiking.calculators.tobler import ToblerCalculator
from app.features.hiking.calculators.naismith import NaismithCalculator
from app.features.trail_run.calculators.personalization import (
    RunPersonalizationService,
    DEFAULT_FLAT_PACE_MIN_KM,
)
from app.features.trail_run.models import UserRunProfile

from .virtual_route import VirtualRoute, VirtualSegment


@dataclass
class SegmentPredictions:
    """Predicted times for one segment by all methods."""

    segment_index: int
    distance_m: float
    gradient_percent: float
    actual_time_s: int

    # Predictions (seconds)
    strava_gap: float
    minetti_gap: float
    strava_minetti_gap: float
    personalized: Optional[float]  # None if no profile
    tobler: float
    naismith: float


@dataclass
class RoutePredictions:
    """Predicted times for entire route by all methods."""

    activity_id: int
    activity_name: str

    # Actual
    actual_time_s: int

    # Totals by method (seconds)
    strava_gap: float
    minetti_gap: float
    strava_minetti_gap: float
    personalized: Optional[float]
    tobler: float
    naismith: float

    # Per-segment (for detailed analysis)
    segments: List[SegmentPredictions]

    def get_predictions_dict(self) -> Dict[str, float]:
        """Get all predictions as dict."""
        result = {
            "strava_gap": self.strava_gap,
            "minetti_gap": self.minetti_gap,
            "strava_minetti_gap": self.strava_minetti_gap,
            "tobler": self.tobler,
            "naismith": self.naismith,
        }
        if self.personalized is not None:
            result["personalized"] = self.personalized
        return result


def _segment_type_from_gradient(gradient: float) -> SegmentType:
    """Determine segment type from gradient."""
    if gradient > 3:
        return SegmentType.ASCENT
    elif gradient < -3:
        return SegmentType.DESCENT
    return SegmentType.FLAT


def _create_macro_segment(
    index: int,
    distance_km: float,
    gradient_percent: float,
    elevation_diff_m: float
) -> MacroSegment:
    """Create a MacroSegment from simple values."""
    seg_type = _segment_type_from_gradient(gradient_percent)

    # Calculate gain/loss based on elevation_diff
    if elevation_diff_m > 0:
        gain = elevation_diff_m
        loss = 0.0
    else:
        gain = 0.0
        loss = abs(elevation_diff_m)

    return MacroSegment(
        segment_number=index,
        segment_type=seg_type,
        distance_km=distance_km,
        elevation_gain_m=gain,
        elevation_loss_m=loss,
        start_elevation_m=0,  # Not needed for calculations
        end_elevation_m=elevation_diff_m,
    )


class CalculatorAdapter:
    """
    Adapter to run virtual routes through calculators.

    Initializes all calculators and provides a unified interface
    for getting predictions.
    """

    def __init__(
        self,
        run_profile: Optional[UserRunProfile] = None,
        flat_pace_min_km: float = DEFAULT_FLAT_PACE_MIN_KM,
    ):
        """
        Initialize adapter with optional user profile.

        Args:
            run_profile: User's run profile for personalization
            flat_pace_min_km: Base flat pace for GAP calculations
        """
        self._flat_pace = flat_pace_min_km

        # Use profile's flat pace if available
        if run_profile and run_profile.avg_flat_pace_min_km:
            self._flat_pace = run_profile.avg_flat_pace_min_km

        # GAP calculators (3 modes)
        self._gap_strava = GAPCalculator(
            base_flat_pace_min_km=self._flat_pace,
            mode=GAPMode.STRAVA
        )
        self._gap_minetti = GAPCalculator(
            base_flat_pace_min_km=self._flat_pace,
            mode=GAPMode.MINETTI
        )
        self._gap_strava_minetti = GAPCalculator(
            base_flat_pace_min_km=self._flat_pace,
            mode=GAPMode.STRAVA_MINETTI
        )

        # Hiking calculators
        self._tobler = ToblerCalculator()
        self._naismith = NaismithCalculator()

        # Personalization (if profile available)
        self._personalization = None
        self._run_profile = run_profile
        if run_profile and run_profile.has_profile_data:
            self._personalization = RunPersonalizationService(run_profile)

    def calculate_route(self, route: VirtualRoute) -> RoutePredictions:
        """
        Calculate predictions for entire route.

        Args:
            route: Virtual route to analyze

        Returns:
            RoutePredictions with all method results
        """
        segment_predictions = []

        # Accumulators for totals
        total_strava = 0.0
        total_minetti = 0.0
        total_strava_minetti = 0.0
        total_personalized = 0.0 if self._personalization else None
        total_tobler = 0.0
        total_naismith = 0.0

        for i, segment in enumerate(route.segments):
            seg_pred = self._calculate_segment(i, segment)
            segment_predictions.append(seg_pred)

            # Accumulate totals
            total_strava += seg_pred.strava_gap
            total_minetti += seg_pred.minetti_gap
            total_strava_minetti += seg_pred.strava_minetti_gap
            total_tobler += seg_pred.tobler
            total_naismith += seg_pred.naismith

            if seg_pred.personalized is not None and total_personalized is not None:
                total_personalized += seg_pred.personalized

        return RoutePredictions(
            activity_id=route.activity_id,
            activity_name=route.activity_name,
            actual_time_s=route.actual_total_time_s,
            strava_gap=total_strava,
            minetti_gap=total_minetti,
            strava_minetti_gap=total_strava_minetti,
            personalized=total_personalized,
            tobler=total_tobler,
            naismith=total_naismith,
            segments=segment_predictions,
        )

    def _calculate_segment(
        self,
        index: int,
        segment: VirtualSegment
    ) -> SegmentPredictions:
        """Calculate predictions for single segment."""

        distance_km = segment.distance_m / 1000
        gradient = segment.gradient_percent

        # Create MacroSegment for calculators that need it
        macro_seg = _create_macro_segment(
            index, distance_km, gradient, segment.elevation_diff_m
        )

        # GAP methods (calculate returns GAPResult)
        strava_result = self._gap_strava.calculate(gradient)
        strava_time = (distance_km / (60 / strava_result.adjusted_pace_min_km)) * 3600

        minetti_result = self._gap_minetti.calculate(gradient)
        minetti_time = (distance_km / (60 / minetti_result.adjusted_pace_min_km)) * 3600

        sm_result = self._gap_strava_minetti.calculate(gradient)
        sm_time = (distance_km / (60 / sm_result.adjusted_pace_min_km)) * 3600

        # Hiking methods (calculate_segment returns MethodResult with time_hours)
        tobler_result = self._tobler.calculate_segment(macro_seg)
        tobler_time = tobler_result.time_hours * 3600

        naismith_result = self._naismith.calculate_segment(macro_seg)
        naismith_time = naismith_result.time_hours * 3600

        # Personalized (if available)
        personalized_time = None
        if self._personalization:
            pers_result = self._personalization.calculate_segment(macro_seg)
            personalized_time = pers_result.time_hours * 3600

        return SegmentPredictions(
            segment_index=index,
            distance_m=segment.distance_m,
            gradient_percent=gradient,
            actual_time_s=segment.actual_time_s,
            strava_gap=strava_time,
            minetti_gap=minetti_time,
            strava_minetti_gap=sm_time,
            personalized=personalized_time,
            tobler=tobler_time,
            naismith=naismith_time,
        )
