"""
Trail Run Service

Orchestrates all trail running components:
- Route segmentation
- Hike/Run threshold detection
- GAP calculation for running segments
- Tobler/personalization for hiking segments
- Runner fatigue model

This is the main entry point for trail running predictions.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from app.services.calculators.base import MacroSegment
from app.services.calculators.segmenter import RouteSegmenter
from app.features.hiking.calculators import ToblerCalculator, HikePersonalizationService
from app.features.trail_run.calculators.personalization import RunPersonalizationService
from app.features.trail_run.calculators.gap import GAPCalculator, GAPMode
from app.features.trail_run.calculators.threshold import (
    HikeRunThresholdService,
    MovementMode,
    HikeRunDecision,
)
from app.features.trail_run.calculators.fatigue import RunnerFatigueService

from app.features.hiking.models import UserHikingProfile
from app.features.trail_run.models import UserRunProfile


# Default flat pace if no profile
DEFAULT_FLAT_PACE_MIN_KM = 6.0


@dataclass
class SegmentResult:
    """Result for a single segment."""
    segment: MacroSegment
    movement: HikeRunDecision
    times: Dict[str, float]      # method → hours
    fatigue_multiplier: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            "segment_number": self.segment.segment_number,
            "start_km": round(self.segment.start_km, 2) if hasattr(self.segment, 'start_km') else 0,
            "end_km": round(self.segment.end_km, 2) if hasattr(self.segment, 'end_km') else 0,
            "distance_km": round(self.segment.distance_km, 2),
            "elevation_change_m": round(self.segment.elevation_change_m, 0),
            "gradient_percent": round(self.segment.gradient_percent, 1),
            "movement": {
                "mode": self.movement.mode.value,
                "reason": self.movement.reason,
                "threshold_used": self.movement.threshold_used,
                "confidence": self.movement.confidence,
            },
            "times": {k: round(v, 4) for k, v in self.times.items()},
            "fatigue_multiplier": round(self.fatigue_multiplier, 3),
        }


@dataclass
class TrailRunSummary:
    """Summary statistics for trail run prediction."""
    total_distance_km: float
    total_elevation_gain_m: float
    total_elevation_loss_m: float
    running_time_hours: float
    hiking_time_hours: float
    running_distance_km: float
    hiking_distance_km: float
    flat_equivalent_hours: float
    elevation_impact_percent: float

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            "total_distance_km": round(self.total_distance_km, 2),
            "total_elevation_gain_m": round(self.total_elevation_gain_m, 0),
            "total_elevation_loss_m": round(self.total_elevation_loss_m, 0),
            "running_time_hours": round(self.running_time_hours, 3),
            "hiking_time_hours": round(self.hiking_time_hours, 3),
            "running_distance_km": round(self.running_distance_km, 2),
            "hiking_distance_km": round(self.hiking_distance_km, 2),
            "flat_equivalent_hours": round(self.flat_equivalent_hours, 3),
            "elevation_impact_percent": round(self.elevation_impact_percent, 1),
        }


@dataclass
class TrailRunResult:
    """Complete result of trail run prediction."""
    segments: List[SegmentResult]
    totals: Dict[str, float]
    summary: TrailRunSummary
    personalized: bool
    total_activities_used: int
    hike_activities_used: int
    run_activities_used: int
    walk_threshold_used: float
    gap_mode: str
    fatigue_applied: bool
    fatigue_info: Optional[Dict] = None

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            "segments": [s.to_dict() for s in self.segments],
            "totals": {k: round(v, 4) for k, v in self.totals.items()},
            "summary": self.summary.to_dict(),
            "personalized": self.personalized,
            "total_activities_used": self.total_activities_used,
            "hike_activities_used": self.hike_activities_used,
            "run_activities_used": self.run_activities_used,
            "walk_threshold_used": self.walk_threshold_used,
            "gap_mode": self.gap_mode,
            "fatigue_applied": self.fatigue_applied,
            "fatigue_info": self.fatigue_info,
        }


class TrailRunService:
    """
    Main service for trail running time predictions.

    Combines:
    - GAPCalculator for running segments
    - ToblerCalculator for hiking segments
    - HikeRunThresholdService for mode detection
    - RunnerFatigueService for fatigue modeling
    - Personalization for both run and hike segments

    Example usage:
        service = TrailRunService(
            gap_mode=GAPMode.STRAVA,
            flat_pace_min_km=5.5,
            apply_fatigue=True,
        )
        result = service.calculate_route(points)
    """

    def __init__(
        self,
        gap_mode: GAPMode = GAPMode.STRAVA,
        flat_pace_min_km: float = DEFAULT_FLAT_PACE_MIN_KM,
        hike_profile: Optional[UserHikingProfile] = None,
        run_profile: Optional[UserRunProfile] = None,
        apply_fatigue: bool = False,
        apply_dynamic_threshold: bool = False,
        walk_threshold_override: Optional[float] = None,
        use_extended_gradients: bool = True,
        total_distance_km: Optional[float] = None,
    ):
        """
        Initialize trail run service.

        Args:
            gap_mode: GAP calculation mode (STRAVA or MINETTI)
            flat_pace_min_km: Base flat pace for GAP (if no run profile)
            hike_profile: UserHikingProfile for hiking segments
            run_profile: UserRunProfile for running segments
            apply_fatigue: Enable runner fatigue model
            apply_dynamic_threshold: Enable dynamic hike/run threshold
            walk_threshold_override: Manual override for walk threshold
            use_extended_gradients: Use 7-category gradient system
            total_distance_km: Total route distance (for ultra adaptation)
        """
        self.gap_mode = gap_mode
        self.use_extended_gradients = use_extended_gradients

        # Determine flat pace from profile or manual input
        if run_profile and run_profile.avg_flat_pace_min_km:
            self.flat_pace = run_profile.avg_flat_pace_min_km
        else:
            self.flat_pace = flat_pace_min_km

        # Store profiles
        self.hike_profile = hike_profile
        self.run_profile = run_profile

        # Calculators
        self._gap_calc = GAPCalculator(self.flat_pace, gap_mode)
        self._tobler_calc = ToblerCalculator()

        # Personalization services (if profiles valid)
        self._run_pers = None
        self._hike_pers = None

        if RunPersonalizationService.is_profile_valid(run_profile):
            self._run_pers = RunPersonalizationService(run_profile, use_extended_gradients)

        if HikePersonalizationService.is_profile_valid(hike_profile):
            self._hike_pers = HikePersonalizationService(hike_profile, use_extended_gradients)

        # Threshold service
        threshold = walk_threshold_override
        if threshold is None and run_profile and run_profile.walk_threshold_percent:
            threshold = run_profile.walk_threshold_percent

        self._threshold_service = HikeRunThresholdService(
            uphill_threshold=threshold or 25.0,
            dynamic=apply_dynamic_threshold
        )

        # Fatigue service
        self._apply_fatigue = apply_fatigue
        if apply_fatigue:
            self._fatigue_service = RunnerFatigueService.create_enabled(
                distance_km=total_distance_km
            )
        else:
            self._fatigue_service = RunnerFatigueService.create_disabled()

        # Store for result
        self._total_distance_km = total_distance_km

    def calculate_route(
        self,
        points: List[tuple]
    ) -> TrailRunResult:
        """
        Calculate trail run prediction for a route.

        Args:
            points: List of (lat, lon, elevation) tuples

        Returns:
            TrailRunResult with all predictions
        """
        # Segment route
        segments = RouteSegmenter.segment_route(points)

        total_distance = sum(s.distance_km for s in segments)

        # Update fatigue service with actual distance if not provided
        if self._apply_fatigue and self._total_distance_km is None:
            self._fatigue_service = RunnerFatigueService.create_enabled(
                distance_km=total_distance
            )

        # Get hike/run decisions
        decisions = self._threshold_service.process_route(
            segments,
            total_distance_km=total_distance
        )

        # Calculate each segment
        results = []
        cumulative_time = 0.0

        # Track totals by method
        totals = {
            "strava_gap": 0.0,
            "minetti_gap": 0.0,
            "tobler": 0.0,
        }

        if self._run_pers:
            totals["run_personalized"] = 0.0
        if self._hike_pers:
            totals["hike_personalized"] = 0.0

        # Combined best estimate
        totals["combined"] = 0.0

        running_time = 0.0
        hiking_time = 0.0
        running_distance = 0.0
        hiking_distance = 0.0

        for segment, decision in zip(segments, decisions):
            times = {}

            if decision.mode == MovementMode.RUN:
                # Running segment
                running_distance += segment.distance_km

                # Always calculate both GAP modes for comparison
                strava_calc = GAPCalculator(self.flat_pace, GAPMode.STRAVA)
                minetti_calc = GAPCalculator(self.flat_pace, GAPMode.MINETTI)

                strava_result = strava_calc.calculate_segment(segment)
                minetti_result = minetti_calc.calculate_segment(segment)

                times["strava_gap"] = strava_result.time_hours
                times["minetti_gap"] = minetti_result.time_hours

                # Run personalization
                if self._run_pers:
                    pers_result = self._run_pers.calculate_segment(segment)
                    times["run_personalized"] = pers_result.time_hours

                # Primary time for this segment (for fatigue and combined)
                if self._run_pers:
                    primary_time = times["run_personalized"]
                elif self.gap_mode == GAPMode.STRAVA:
                    primary_time = times["strava_gap"]
                else:
                    primary_time = times["minetti_gap"]

            else:
                # Hiking segment
                hiking_distance += segment.distance_km

                # Tobler
                tobler_result = self._tobler_calc.calculate_segment(segment)
                times["tobler"] = tobler_result.time_hours

                # Hike personalization
                if self._hike_pers:
                    pers_result = self._hike_pers.calculate_segment(segment)
                    times["hike_personalized"] = pers_result.time_hours

                # Primary time
                if self._hike_pers:
                    primary_time = times["hike_personalized"]
                else:
                    primary_time = times["tobler"]

            # Apply fatigue to primary time
            adjusted_time, multiplier = self._fatigue_service.apply_to_segment(
                primary_time,
                cumulative_time,
                segment.gradient_percent
            )

            # Track cumulative time with fatigue
            cumulative_time += adjusted_time

            # Track running/hiking time
            if decision.mode == MovementMode.RUN:
                running_time += adjusted_time
            else:
                hiking_time += adjusted_time

            # Add to combined total
            totals["combined"] += adjusted_time

            # Accumulate totals for each method (with fatigue applied consistently)
            for method, time in times.items():
                if method in totals:
                    fatigue_adj, _ = self._fatigue_service.apply_to_segment(
                        time,
                        cumulative_time - adjusted_time,
                        segment.gradient_percent
                    )
                    totals[method] += fatigue_adj

            results.append(SegmentResult(
                segment=segment,
                movement=decision,
                times=times,
                fatigue_multiplier=multiplier
            ))

        # Calculate elevation stats
        total_elevation_gain = sum(s.elevation_gain_m for s in segments)
        total_elevation_loss = sum(s.elevation_loss_m for s in segments)

        # Calculate flat equivalent
        flat_speed_kmh = 60 / self.flat_pace
        flat_time = total_distance / flat_speed_kmh
        primary_total = totals["combined"]
        elevation_impact = ((primary_total / flat_time) - 1) * 100 if flat_time > 0 else 0

        summary = TrailRunSummary(
            total_distance_km=total_distance,
            total_elevation_gain_m=total_elevation_gain,
            total_elevation_loss_m=total_elevation_loss,
            running_time_hours=running_time,
            hiking_time_hours=hiking_time,
            running_distance_km=running_distance,
            hiking_distance_km=hiking_distance,
            flat_equivalent_hours=flat_time,
            elevation_impact_percent=elevation_impact,
        )

        # Activity counts
        hike_activities = 0
        run_activities = 0

        if self.hike_profile:
            hike_activities = self.hike_profile.total_activities_analyzed or 0

        if self.run_profile:
            run_activities = self.run_profile.total_activities or 0

        return TrailRunResult(
            segments=results,
            totals=totals,
            summary=summary,
            personalized=self._run_pers is not None or self._hike_pers is not None,
            total_activities_used=hike_activities + run_activities,
            hike_activities_used=hike_activities,
            run_activities_used=run_activities,
            walk_threshold_used=self._threshold_service.base_uphill_threshold,
            gap_mode=self.gap_mode.value,
            fatigue_applied=self._apply_fatigue,
            fatigue_info=self._fatigue_service.get_info() if self._apply_fatigue else None,
        )

    def get_info(self) -> dict:
        """Get service configuration info."""
        return {
            "gap_mode": self.gap_mode.value,
            "flat_pace_min_km": self.flat_pace,
            "use_extended_gradients": self.use_extended_gradients,
            "walk_threshold": self._threshold_service.base_uphill_threshold,
            "dynamic_threshold": self._threshold_service.dynamic,
            "fatigue_enabled": self._apply_fatigue,
            "run_personalized": self._run_pers is not None,
            "hike_personalized": self._hike_pers is not None,
        }
