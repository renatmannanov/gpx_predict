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

from app.shared.calculator_types import MacroSegment, EffortLevel
from app.features.gpx import RouteSegmenter
from app.features.hiking.calculators.tobler import ToblerCalculator
from app.features.hiking.calculators.naismith import NaismithCalculator
from app.features.hiking.calculators.personalization import HikePersonalizationService
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
        # Round numeric values, pass through dicts (like run_profile)
        totals_formatted = {}
        for k, v in self.totals.items():
            if isinstance(v, (int, float)):
                totals_formatted[k] = round(v, 4)
            else:
                totals_formatted[k] = v

        return {
            "segments": [s.to_dict() for s in self.segments],
            "totals": totals_formatted,
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

        # Use provided flat_pace directly (caller decides the source)
        # Profile is for personalization coefficients, not base pace
        self.flat_pace = flat_pace_min_km

        # Store profiles
        self.hike_profile = hike_profile
        self.run_profile = run_profile

        # Calculators
        self._gap_calc = GAPCalculator(self.flat_pace, gap_mode)
        self._tobler_calc = ToblerCalculator()
        self._naismith_calc = NaismithCalculator()

        # Personalization services (if profiles valid)
        # _run_pers = default (MODERATE) for backward compat (fatigue, combined)
        # _run_pers_by_effort = all 3 effort levels for API response
        self._run_pers = None
        self._run_pers_by_effort: Dict[EffortLevel, RunPersonalizationService] = {}
        self._hike_pers = None

        if RunPersonalizationService.is_profile_valid(run_profile):
            for effort in EffortLevel:
                self._run_pers_by_effort[effort] = RunPersonalizationService(
                    run_profile, use_extended_gradients, effort=effort
                )
            # Default (MODERATE) used for fatigue/combined/primary_time
            self._run_pers = self._run_pers_by_effort[EffortLevel.MODERATE]

        if HikePersonalizationService.is_profile_valid(hike_profile):
            self._hike_pers = HikePersonalizationService(hike_profile, use_extended_gradients)

        # Threshold service
        threshold = walk_threshold_override
        if threshold is None and run_profile and run_profile.walk_threshold_percent:
            threshold = run_profile.walk_threshold_percent

        self._threshold_service = HikeRunThresholdService(
            uphill_threshold=threshold or HikeRunThresholdService.DEFAULT_UPHILL_THRESHOLD,
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

        # Create calculators for all 3 GAP modes
        strava_calc = GAPCalculator(self.flat_pace, GAPMode.STRAVA)
        minetti_calc = GAPCalculator(self.flat_pace, GAPMode.MINETTI)
        strava_minetti_calc = GAPCalculator(self.flat_pace, GAPMode.STRAVA_MINETTI)

        # Track totals by method
        # Phase 1: "all_run_*" = all segments calculated as running (full route)
        totals = {
            "all_run_strava": 0.0,
            "all_run_minetti": 0.0,
            "all_run_strava_minetti": 0.0,
            "tobler": 0.0,
            "naismith": 0.0,
            # Phase 2: "run_hike_*" = run on flat/moderate, hike on steep (6 combinations)
            "run_hike_strava_tobler": 0.0,
            "run_hike_strava_naismith": 0.0,
            "run_hike_minetti_tobler": 0.0,
            "run_hike_minetti_naismith": 0.0,
            "run_hike_strava_minetti_tobler": 0.0,
            "run_hike_strava_minetti_naismith": 0.0,
        }

        if self._run_pers:
            totals["run_personalized"] = 0.0
        if self._hike_pers:
            totals["hike_personalized"] = 0.0

        # Phase 3: Personalized combinations (default MODERATE for legacy)
        all_run_personalized = 0.0
        run_hike_personalized_tobler = 0.0
        run_hike_personalized_naismith = 0.0

        # Effort-level accumulators: all_run_personalized_{effort}
        effort_all_run = {e: 0.0 for e in EffortLevel} if self._run_pers_by_effort else {}
        effort_run_hike_tobler = {e: 0.0 for e in EffortLevel} if self._run_pers_by_effort else {}
        effort_run_hike_naismith = {e: 0.0 for e in EffortLevel} if self._run_pers_by_effort else {}

        # Combined best estimate (legacy, uses threshold logic)
        totals["combined"] = 0.0

        running_time = 0.0
        hiking_time = 0.0
        running_distance = 0.0
        hiking_distance = 0.0

        for segment, decision in zip(segments, decisions):
            times = {}

            # Always calculate ALL 3 GAP modes for EVERY segment (for "all_run_*" totals)
            strava_result = strava_calc.calculate_segment(segment)
            minetti_result = minetti_calc.calculate_segment(segment)
            strava_minetti_result = strava_minetti_calc.calculate_segment(segment)

            times["strava_gap"] = strava_result.time_hours
            times["minetti_gap"] = minetti_result.time_hours
            times["strava_minetti_gap"] = strava_minetti_result.time_hours

            # Accumulate "all_run_*" totals (full route as running)
            totals["all_run_strava"] += strava_result.time_hours
            totals["all_run_minetti"] += minetti_result.time_hours
            totals["all_run_strava_minetti"] += strava_minetti_result.time_hours

            # Calculate hiking methods for every segment
            tobler_result = self._tobler_calc.calculate_segment(segment)
            naismith_result = self._naismith_calc.calculate_segment(segment)
            times["tobler"] = tobler_result.time_hours
            times["naismith"] = naismith_result.time_hours
            totals["tobler"] += tobler_result.time_hours
            totals["naismith"] += naismith_result.time_hours

            # Phase 2: Accumulate run_hike_* totals based on threshold decision
            if decision.mode == MovementMode.RUN:
                # RUN segment: use GAP times for run_hike_* totals
                totals["run_hike_strava_tobler"] += strava_result.time_hours
                totals["run_hike_strava_naismith"] += strava_result.time_hours
                totals["run_hike_minetti_tobler"] += minetti_result.time_hours
                totals["run_hike_minetti_naismith"] += minetti_result.time_hours
                totals["run_hike_strava_minetti_tobler"] += strava_minetti_result.time_hours
                totals["run_hike_strava_minetti_naismith"] += strava_minetti_result.time_hours
            else:
                # HIKE segment: use hiking times for run_hike_* totals
                totals["run_hike_strava_tobler"] += tobler_result.time_hours
                totals["run_hike_strava_naismith"] += naismith_result.time_hours
                totals["run_hike_minetti_tobler"] += tobler_result.time_hours
                totals["run_hike_minetti_naismith"] += naismith_result.time_hours
                totals["run_hike_strava_minetti_tobler"] += tobler_result.time_hours
                totals["run_hike_strava_minetti_naismith"] += naismith_result.time_hours

            # Phase 3: Personalized time for this segment (default MODERATE)
            if self._run_pers:
                run_pers_result = self._run_pers.calculate_segment(segment)
                run_pers_time = run_pers_result.time_hours
            else:
                # Fallback to strava_minetti if no personalization
                run_pers_time = strava_minetti_result.time_hours

            # Accumulate personalized totals (MODERATE for legacy)
            all_run_personalized += run_pers_time

            if decision.mode == MovementMode.RUN:
                run_hike_personalized_tobler += run_pers_time
                run_hike_personalized_naismith += run_pers_time
            else:
                run_hike_personalized_tobler += tobler_result.time_hours
                run_hike_personalized_naismith += naismith_result.time_hours

            # Effort-level personalized times (all 3 levels)
            for effort, pers_service in self._run_pers_by_effort.items():
                pers_result_e = pers_service.calculate_segment(segment)
                pers_time_e = pers_result_e.time_hours
                effort_all_run[effort] += pers_time_e
                if decision.mode == MovementMode.RUN:
                    effort_run_hike_tobler[effort] += pers_time_e
                    effort_run_hike_naismith[effort] += pers_time_e
                else:
                    effort_run_hike_tobler[effort] += tobler_result.time_hours
                    effort_run_hike_naismith[effort] += naismith_result.time_hours

            if decision.mode == MovementMode.RUN:
                # Running segment
                running_distance += segment.distance_km

                # Run personalization
                if self._run_pers:
                    pers_result = self._run_pers.calculate_segment(segment)
                    times["run_personalized"] = pers_result.time_hours

                # Primary time for this segment (for fatigue and combined)
                if self._run_pers:
                    primary_time = times["run_personalized"]
                elif self.gap_mode == GAPMode.STRAVA:
                    primary_time = times["strava_gap"]
                elif self.gap_mode == GAPMode.MINETTI:
                    primary_time = times["minetti_gap"]
                else:  # STRAVA_MINETTI
                    primary_time = times["strava_minetti_gap"]

            else:
                # Hiking segment
                hiking_distance += segment.distance_km

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

            # Accumulate personalized totals
            if "run_personalized" in times and "run_personalized" in totals:
                totals["run_personalized"] += times["run_personalized"]
            if "hike_personalized" in times and "hike_personalized" in totals:
                totals["hike_personalized"] += times["hike_personalized"]

            results.append(SegmentResult(
                segment=segment,
                movement=decision,
                times=times,
                fatigue_multiplier=multiplier
            ))

        # Add run/hike statistics to totals (Phase 2)
        totals["run_distance_km"] = running_distance
        totals["hike_distance_km"] = hiking_distance
        totals["run_percent"] = (running_distance / total_distance * 100) if total_distance > 0 else 100
        totals["hike_percent"] = (hiking_distance / total_distance * 100) if total_distance > 0 else 0
        totals["threshold_used"] = self._threshold_service.base_uphill_threshold

        # Phase 3: Add personalized totals (if profile exists)
        if self._run_pers:
            totals["all_run_personalized"] = all_run_personalized
            totals["run_hike_personalized_tobler"] = run_hike_personalized_tobler
            totals["run_hike_personalized_naismith"] = run_hike_personalized_naismith
            totals["run_profile"] = self._build_run_profile_info()

        # Effort-level totals (all 3 levels for API)
        if self._run_pers_by_effort:
            for effort in EffortLevel:
                key = effort.value  # "race", "moderate", "easy"
                totals[f"all_run_personalized_{key}"] = effort_all_run[effort]
                totals[f"run_hike_personalized_tobler_{key}"] = effort_run_hike_tobler[effort]
                totals[f"run_hike_personalized_naismith_{key}"] = effort_run_hike_naismith[effort]

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

    def _build_run_profile_info(self) -> Optional[dict]:
        """Build run profile info for totals output."""
        if not self.run_profile:
            return None

        # Minimum samples for personalization
        MIN_SAMPLES = 5

        # Build detailed gradient profile
        gradient_profile = [
            {
                "category": "steep_uphill",
                "label": "steep_up (+15%↑)",
                "pace": self.run_profile.avg_steep_uphill_pace_min_km,
                "samples": self.run_profile.steep_uphill_sample_count or 0,
                "is_personal": (self.run_profile.steep_uphill_sample_count or 0) >= MIN_SAMPLES,
            },
            {
                "category": "moderate_uphill",
                "label": "moderate_up (+8-15%)",
                "pace": self.run_profile.avg_moderate_uphill_pace_min_km,
                "samples": self.run_profile.moderate_uphill_sample_count or 0,
                "is_personal": (self.run_profile.moderate_uphill_sample_count or 0) >= MIN_SAMPLES,
            },
            {
                "category": "gentle_uphill",
                "label": "gentle_up (+3-8%)",
                "pace": self.run_profile.avg_gentle_uphill_pace_min_km,
                "samples": self.run_profile.gentle_uphill_sample_count or 0,
                "is_personal": (self.run_profile.gentle_uphill_sample_count or 0) >= MIN_SAMPLES,
            },
            {
                "category": "flat",
                "label": "flat (-3 to +3%)",
                "pace": self.run_profile.avg_flat_pace_min_km,
                "samples": self.run_profile.flat_sample_count or 0,
                "is_personal": (self.run_profile.flat_sample_count or 0) >= MIN_SAMPLES,
            },
            {
                "category": "gentle_downhill",
                "label": "gentle_down (-3-8%)",
                "pace": self.run_profile.avg_gentle_downhill_pace_min_km,
                "samples": self.run_profile.gentle_downhill_sample_count or 0,
                "is_personal": (self.run_profile.gentle_downhill_sample_count or 0) >= MIN_SAMPLES,
            },
            {
                "category": "moderate_downhill",
                "label": "moderate_dn (-8-15%)",
                "pace": self.run_profile.avg_moderate_downhill_pace_min_km,
                "samples": self.run_profile.moderate_downhill_sample_count or 0,
                "is_personal": (self.run_profile.moderate_downhill_sample_count or 0) >= MIN_SAMPLES,
            },
            {
                "category": "steep_downhill",
                "label": "steep_down (-15%↓)",
                "pace": self.run_profile.avg_steep_downhill_pace_min_km,
                "samples": self.run_profile.steep_downhill_sample_count or 0,
                "is_personal": (self.run_profile.steep_downhill_sample_count or 0) >= MIN_SAMPLES,
            },
        ]

        # Count categories with enough samples for personalization
        categories_personal = sum(1 for g in gradient_profile if g["is_personal"])

        return {
            "total_distance_km": self.run_profile.total_distance_km or 0,
            "total_activities": self.run_profile.total_activities or 0,
            "total_splits": self._get_total_splits(),
            "categories_filled": categories_personal,
            "categories_total": 7,
            "gradient_profile": gradient_profile,
            "min_samples_threshold": MIN_SAMPLES,
        }

    def _get_total_splits(self) -> int:
        """Count total splits in run profile."""
        if not self.run_profile:
            return 0

        return sum([
            self.run_profile.flat_sample_count or 0,
            self.run_profile.gentle_uphill_sample_count or 0,
            self.run_profile.moderate_uphill_sample_count or 0,
            self.run_profile.steep_uphill_sample_count or 0,
            self.run_profile.gentle_downhill_sample_count or 0,
            self.run_profile.moderate_downhill_sample_count or 0,
            self.run_profile.steep_downhill_sample_count or 0,
        ])
