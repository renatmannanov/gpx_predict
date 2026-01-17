"""
Comparison Service

Compares multiple calculation methods side-by-side.
Supports optional personalization based on user's Strava activity data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from app.services.calculators.base import (
    PaceCalculator,
    MacroSegment,
    MethodResult,
    SegmentType
)
from app.services.calculators.naismith import NaismithCalculator
from app.services.calculators.tobler import ToblerCalculator
from app.services.calculators.segmenter import RouteSegmenter
from app.services.calculators.personalization import PersonalizationService
from app.models.user_profile import UserPerformanceProfile


@dataclass
class SegmentComparison:
    """Comparison of methods for a single segment."""
    segment_number: int
    segment_type: str  # "ascent", "descent", "flat"
    distance_km: float
    elevation_change_m: float
    gradient_percent: float
    gradient_degrees: float
    start_elevation_m: float
    end_elevation_m: float

    # Results by method
    methods: Dict[str, MethodResult] = field(default_factory=dict)


@dataclass
class RouteComparison:
    """Full route comparison with all segments and methods."""
    # Route summary
    total_distance_km: float
    total_ascent_m: float
    total_descent_m: float
    ascent_distance_km: float
    descent_distance_km: float

    # Segment breakdown
    segments: List[SegmentComparison] = field(default_factory=list)

    # Totals by method (hours)
    totals: Dict[str, float] = field(default_factory=dict)

    # Method descriptions
    method_descriptions: Dict[str, str] = field(default_factory=dict)

    # Personalization info
    personalized: bool = False
    activities_used: int = 0


class ComparisonService:
    """
    Service to compare different pace calculation methods.

    Provides side-by-side comparison of Naismith, Tobler,
    and future methods on the same route.
    """

    def __init__(self):
        self.calculators: List[PaceCalculator] = [
            NaismithCalculator(),
            ToblerCalculator(),
        ]

    def compare_route(
        self,
        points: List[Tuple[float, float, float]],
        profile_multiplier: float = 1.0,
        user_profile: Optional[UserPerformanceProfile] = None
    ) -> RouteComparison:
        """
        Compare all methods on a route.

        Args:
            points: List of (lat, lon, elevation) tuples
            profile_multiplier: Multiplier from hiker profile
            user_profile: Optional user profile for personalized calculations

        Returns:
            RouteComparison with segment-by-segment and total results
        """
        # Segment the route into macro-segments
        macro_segments = RouteSegmenter.segment_route(points)

        if not macro_segments:
            return self._empty_comparison(user_profile)

        # Calculate totals
        total_distance = sum(s.distance_km for s in macro_segments)
        total_ascent = sum(s.elevation_gain_m for s in macro_segments)
        total_descent = sum(s.elevation_loss_m for s in macro_segments)

        ascent_distance = sum(
            s.distance_km for s in macro_segments
            if s.segment_type == SegmentType.ASCENT
        )
        descent_distance = sum(
            s.distance_km for s in macro_segments
            if s.segment_type == SegmentType.DESCENT
        )

        # Setup personalization if profile is valid
        personalization = None
        is_personalized = False
        activities_used = 0

        if PersonalizationService.is_profile_valid(user_profile):
            personalization = PersonalizationService(user_profile)
            is_personalized = True
            activities_used = user_profile.total_activities_analyzed

        # Compare each segment
        segment_comparisons = []
        method_totals: Dict[str, float] = {c.name: 0.0 for c in self.calculators}

        # Add personalized method totals if profile available
        if personalization:
            method_totals["tobler_personalized"] = 0.0
            method_totals["naismith_personalized"] = 0.0

        for segment in macro_segments:
            comparison = SegmentComparison(
                segment_number=segment.segment_number,
                segment_type=segment.segment_type.value,
                distance_km=segment.distance_km,
                elevation_change_m=segment.elevation_change_m,
                gradient_percent=round(segment.gradient_percent, 1),
                gradient_degrees=round(segment.gradient_degrees, 1),
                start_elevation_m=segment.start_elevation_m,
                end_elevation_m=segment.end_elevation_m,
                methods={}
            )

            # Calculate with base methods
            for calculator in self.calculators:
                result = calculator.calculate_segment(segment, profile_multiplier)
                comparison.methods[calculator.name] = result
                method_totals[calculator.name] += result.time_hours

            # Calculate with personalized methods
            if personalization:
                for base_method in ["tobler", "naismith"]:
                    result = personalization.calculate_segment(segment, base_method)
                    comparison.methods[result.method_name] = result
                    method_totals[result.method_name] += result.time_hours

            segment_comparisons.append(comparison)

        # Round totals
        method_totals = {k: round(v, 2) for k, v in method_totals.items()}

        # Method descriptions
        descriptions = {c.name: c.description for c in self.calculators}

        # Add personalized descriptions if available
        if personalization:
            descriptions["tobler_personalized"] = f"Tobler + ваш темп ({activities_used} активностей)"
            descriptions["naismith_personalized"] = f"Naismith + ваш темп ({activities_used} активностей)"

        return RouteComparison(
            total_distance_km=round(total_distance, 2),
            total_ascent_m=round(total_ascent, 0),
            total_descent_m=round(total_descent, 0),
            ascent_distance_km=round(ascent_distance, 2),
            descent_distance_km=round(descent_distance, 2),
            segments=segment_comparisons,
            totals=method_totals,
            method_descriptions=descriptions,
            personalized=is_personalized,
            activities_used=activities_used
        )

    def _empty_comparison(
        self,
        user_profile: Optional[UserPerformanceProfile] = None
    ) -> RouteComparison:
        """Return empty comparison for invalid routes."""
        totals = {c.name: 0.0 for c in self.calculators}
        descriptions = {c.name: c.description for c in self.calculators}

        # Add personalized methods if profile valid
        is_personalized = False
        activities_used = 0
        if PersonalizationService.is_profile_valid(user_profile):
            is_personalized = True
            activities_used = user_profile.total_activities_analyzed
            totals["tobler_personalized"] = 0.0
            totals["naismith_personalized"] = 0.0
            descriptions["tobler_personalized"] = f"Tobler + ваш темп ({activities_used} активностей)"
            descriptions["naismith_personalized"] = f"Naismith + ваш темп ({activities_used} активностей)"

        return RouteComparison(
            total_distance_km=0,
            total_ascent_m=0,
            total_descent_m=0,
            ascent_distance_km=0,
            descent_distance_km=0,
            segments=[],
            totals=totals,
            method_descriptions=descriptions,
            personalized=is_personalized,
            activities_used=activities_used
        )

    def format_comparison(self, comparison: RouteComparison) -> str:
        """
        Format comparison as human-readable text.

        Useful for debugging and bot output.
        """
        lines = []

        # Header
        lines.append(f"Маршрут: {comparison.total_distance_km} км")
        lines.append(
            f"  Подъём: {comparison.ascent_distance_km} км (+{comparison.total_ascent_m:.0f} м)"
        )
        lines.append(
            f"  Спуск: {comparison.descent_distance_km} км (-{comparison.total_descent_m:.0f} м)"
        )
        lines.append("")

        # Segments
        for seg in comparison.segments:
            seg_type_ru = {
                "ascent": "Подъём",
                "descent": "Спуск",
                "flat": "Ровный"
            }.get(seg.segment_type, seg.segment_type)

            ele_str = f"+{seg.elevation_change_m:.0f}" if seg.elevation_change_m >= 0 else f"{seg.elevation_change_m:.0f}"

            lines.append(
                f"Часть {seg.segment_number}: {seg_type_ru} "
                f"({seg.distance_km} км, {ele_str} м)"
            )
            lines.append(
                f"  Градиент: {seg.gradient_percent}% ({seg.gradient_degrees}°)"
            )
            lines.append(
                f"  Высота: {seg.start_elevation_m:.0f}м → {seg.end_elevation_m:.0f}м"
            )

            for method_name, result in seg.methods.items():
                time_str = self._format_time(result.time_hours)
                lines.append(
                    f"  [{method_name}] {result.speed_kmh} км/ч → {time_str}"
                )

            lines.append("")

        # Totals
        lines.append("=" * 40)
        lines.append("ИТОГО (чистое время движения):")
        for method_name, total_hours in comparison.totals.items():
            time_str = self._format_time(total_hours)
            desc = comparison.method_descriptions.get(method_name, "")
            lines.append(f"  {method_name}: {time_str}")

        return "\n".join(lines)

    @staticmethod
    def _format_time(hours: float) -> str:
        """Format hours as 'Xч Yмин'."""
        h = int(hours)
        m = int((hours - h) * 60)
        if h > 0:
            return f"{h}ч {m}мин"
        return f"{m}мин"
