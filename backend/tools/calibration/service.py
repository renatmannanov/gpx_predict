"""
Backtesting service - main orchestrator.

Loads user activities, runs predictions, calculates metrics.
Supports two modes: trail-run and hiking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.strava.models import StravaActivity
from app.features.trail_run.models import UserRunProfile

from .virtual_route import VirtualRouteBuilder, VirtualRoute
from .calculators import CalculatorAdapter, RoutePredictions
from .metrics import MetricsCalculator, MethodMetrics, GradientCategoryMetrics


class CalibrationMode(Enum):
    """Calibration mode determines activity filters and relevant methods."""
    TRAIL_RUN = "trail-run"   # TrailRun + Run with significant elevation
    HIKING = "hiking"          # Hike activities only


# Preset configurations for each mode
MODE_PRESETS = {
    CalibrationMode.TRAIL_RUN: {
        "activity_types": ["TrailRun", "Run"],
        "min_elevation_m": 200.0,
        "min_distance_km": 5.0,
        "primary_methods": [
            "strava_gap", "minetti_gap", "strava_minetti_gap",
            "personalized_race", "personalized_moderate", "personalized_easy",
        ],
        "secondary_methods": ["tobler", "naismith"],
    },
    CalibrationMode.HIKING: {
        "activity_types": ["Hike"],
        "min_elevation_m": 100.0,
        "min_distance_km": 3.0,
        "primary_methods": [
            "tobler", "naismith",
            "personalized_race", "personalized_moderate", "personalized_easy",
        ],
        "secondary_methods": ["strava_gap"],
    },
}


@dataclass
class BacktestFilters:
    """Filters for selecting activities."""

    mode: CalibrationMode = CalibrationMode.TRAIL_RUN
    activity_types: List[str] = field(default_factory=list)
    min_distance_km: Optional[float] = None
    min_elevation_m: Optional[float] = None
    limit: Optional[int] = None

    def __post_init__(self):
        """Apply mode presets if values not explicitly set."""
        preset = MODE_PRESETS[self.mode]
        if not self.activity_types:
            self.activity_types = preset["activity_types"]
        if self.min_elevation_m is None:
            self.min_elevation_m = preset["min_elevation_m"]
        if self.min_distance_km is None:
            self.min_distance_km = preset["min_distance_km"]


@dataclass
class ProfileInfo:
    """Summary of user's run profile."""

    available: bool
    total_activities: int = 0
    total_distance_km: float = 0.0
    categories_filled: int = 0
    categories_total: int = 7
    flat_pace_min_km: Optional[float] = None


@dataclass
class BacktestReport:
    """Complete backtesting report."""

    # Meta
    user_id: str
    run_at: datetime
    mode: CalibrationMode
    filters: BacktestFilters

    # Summary
    n_activities: int
    n_activities_skipped: int
    total_distance_km: float
    total_elevation_m: float
    total_actual_time_hours: float

    # Profile info
    profile: ProfileInfo

    # Results
    method_metrics: Dict[str, MethodMetrics]
    gradient_breakdown: Dict[str, GradientCategoryMetrics]
    activity_results: List[RoutePredictions]

    # Mode-specific
    primary_methods: List[str] = field(default_factory=list)
    secondary_methods: List[str] = field(default_factory=list)

    @property
    def best_method(self) -> Optional[str]:
        """Method with lowest MAPE among primary methods."""
        best = None
        best_mape = float("inf")

        for method in self.primary_methods:
            if method in self.method_metrics:
                m = self.method_metrics[method]
                if m.n_samples > 0 and m.mape_percent < best_mape:
                    best_mape = m.mape_percent
                    best = method

        return best


class BacktestingService:
    """
    Main backtesting orchestrator.

    Usage:
        service = BacktestingService(session, user_id)
        report = await service.run()

        # Or with hiking mode:
        filters = BacktestFilters(mode=CalibrationMode.HIKING)
        service = BacktestingService(session, user_id, filters)
        report = await service.run()
    """

    def __init__(
        self,
        session: AsyncSession,
        user_id: str,
        filters: Optional[BacktestFilters] = None,
    ):
        self._session = session
        self._user_id = user_id
        self._filters = filters or BacktestFilters()

        self._route_builder = VirtualRouteBuilder()
        self._metrics_calc = MetricsCalculator()

    async def run(self) -> BacktestReport:
        """
        Run backtesting for user.

        Returns:
            BacktestReport with all results
        """
        # Load profile
        profile = await self._load_profile()
        profile_info = self._build_profile_info(profile)

        # Load activities
        activities = await self._load_activities()

        # Build routes and calculate predictions
        calc_adapter = CalculatorAdapter(run_profile=profile)
        predictions: List[RoutePredictions] = []
        skipped = 0

        total_distance_km = 0.0
        total_elevation_m = 0.0

        for activity in activities:
            route = self._route_builder.build_from_activity(
                activity, activity.splits
            )

            if route is None:
                skipped += 1
                continue

            pred = calc_adapter.calculate_route(route)
            predictions.append(pred)

            total_distance_km += route.total_distance_km
            total_elevation_m += route.total_elevation_gain_m

        # Calculate metrics
        method_metrics = self._metrics_calc.calculate_all_methods(predictions)
        gradient_breakdown = self._metrics_calc.calculate_gradient_breakdown(predictions)

        # Get mode presets
        preset = MODE_PRESETS[self._filters.mode]

        # Build report
        return BacktestReport(
            user_id=self._user_id,
            run_at=datetime.utcnow(),
            mode=self._filters.mode,
            filters=self._filters,
            n_activities=len(predictions),
            n_activities_skipped=skipped,
            total_distance_km=round(total_distance_km, 1),
            total_elevation_m=round(total_elevation_m, 0),
            total_actual_time_hours=sum(p.actual_time_s for p in predictions) / 3600,
            profile=profile_info,
            method_metrics=method_metrics,
            gradient_breakdown=gradient_breakdown,
            activity_results=predictions,
            primary_methods=preset["primary_methods"],
            secondary_methods=preset["secondary_methods"],
        )

    async def _load_profile(self) -> Optional[UserRunProfile]:
        """Load user's run profile."""
        result = await self._session.execute(
            select(UserRunProfile)
            .where(UserRunProfile.user_id == self._user_id)
        )
        return result.scalar_one_or_none()

    async def _load_activities(self) -> List[StravaActivity]:
        """Load activities matching filters."""
        query = (
            select(StravaActivity)
            .options(selectinload(StravaActivity.splits))
            .where(StravaActivity.user_id == self._user_id)
            .where(StravaActivity.splits_synced == 1)
            .where(StravaActivity.activity_type.in_(self._filters.activity_types))
        )

        # Distance filter (in meters)
        if self._filters.min_distance_km and self._filters.min_distance_km > 0:
            query = query.where(
                StravaActivity.distance_m >= self._filters.min_distance_km * 1000
            )

        # Elevation filter
        if self._filters.min_elevation_m and self._filters.min_elevation_m > 0:
            query = query.where(
                StravaActivity.elevation_gain_m >= self._filters.min_elevation_m
            )

        # Order by date (newest first)
        query = query.order_by(StravaActivity.start_date.desc())

        # Limit
        if self._filters.limit:
            query = query.limit(self._filters.limit)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    def _build_profile_info(self, profile: Optional[UserRunProfile]) -> ProfileInfo:
        """Build profile summary."""
        if not profile:
            return ProfileInfo(available=False)

        # Count filled categories
        categories = [
            profile.avg_flat_pace_min_km,
            profile.avg_gentle_uphill_pace_min_km,
            profile.avg_moderate_uphill_pace_min_km,
            profile.avg_steep_uphill_pace_min_km,
            profile.avg_gentle_downhill_pace_min_km,
            profile.avg_moderate_downhill_pace_min_km,
            profile.avg_steep_downhill_pace_min_km,
        ]
        filled = sum(1 for c in categories if c is not None)

        return ProfileInfo(
            available=True,
            total_activities=profile.total_activities or 0,
            total_distance_km=profile.total_distance_km or 0,
            categories_filled=filled,
            categories_total=7,
            flat_pace_min_km=profile.avg_flat_pace_min_km,
        )
