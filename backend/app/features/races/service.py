"""RaceService — race time prediction and comparison with past results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.features.gpx.parser import GPXParserService
from app.features.trail_run.service import TrailRunService
from app.features.trail_run.calculators.gap import GAPMode
from app.services.calculators.comparison import ComparisonService

from .catalog import RaceCatalog, RaceDistance, find_distance_results
from .models import RaceEditionData, RaceResult, RaceStats
from .stats import calculate_stats, format_time, get_percentile


@dataclass
class RacePrediction:
    """Result of a race time prediction."""

    race_name: str
    distance_name: str
    distance_km: float | None
    elevation_gain_m: int | None

    # Prediction
    predicted_time_s: int
    method: str  # "trail_run" / "hiking_tobler" / "hiking_naismith"
    flat_pace_used: float  # min/km

    # Trail run details (if method=trail_run)
    all_methods: dict[str, int] = field(default_factory=dict)  # {method: seconds}

    # Comparison with past results
    percentile: float | None = None  # top-X%
    estimated_place: int | None = None
    comparison_year: int | None = None
    stats: RaceStats | None = None

    # User's past result (if found)
    past_result: RaceResult | None = None
    past_result_year: int | None = None


class RaceService:
    """Predicts race times and compares with historical results."""

    def __init__(self, catalog: RaceCatalog):
        self.catalog = catalog

    def predict_by_pace(
        self,
        race_id: str,
        distance_id: str,
        flat_pace_min_km: float,
        mode: str = "trail_run",
    ) -> RacePrediction:
        """Predict race time based on flat pace (no Strava profile needed).

        Args:
            race_id: Race ID from catalog (e.g. "alpine_race")
            distance_id: Distance ID (e.g. "skyrunning")
            flat_pace_min_km: Runner's flat pace in min/km
            mode: "trail_run" (GAP-based) or "hiking" (Tobler/Naismith)
        """
        race = self.catalog.get_race(race_id)
        if not race:
            raise ValueError(f"Race not found: {race_id}")

        dist = self.catalog.get_distance(race_id, distance_id)
        if not dist:
            raise ValueError(f"Distance not found: {distance_id}")

        gpx_path = self.catalog.get_gpx_path(race_id, distance_id)
        if not gpx_path:
            raise ValueError(
                f"GPX file not found for {race_id}/{distance_id}. "
                f"Expected: content/races/gpx/{dist.gpx_file}"
            )

        # Parse GPX → points
        gpx_content = gpx_path.read_bytes()
        points = GPXParserService.extract_points(gpx_content)

        # Calculate prediction
        if mode == "trail_run":
            predicted_s, method_name, all_methods = self._predict_trail_run(
                points, flat_pace_min_km
            )
        else:
            predicted_s, method_name, all_methods = self._predict_hiking(
                points
            )

        # Build prediction
        prediction = RacePrediction(
            race_name=race.name,
            distance_name=dist.name,
            distance_km=dist.distance_km,
            elevation_gain_m=dist.elevation_gain_m,
            predicted_time_s=predicted_s,
            method=method_name,
            flat_pace_used=flat_pace_min_km,
            all_methods=all_methods,
        )

        # Add comparison with latest results
        self._add_comparison(prediction, race_id, distance_id)

        return prediction

    def _predict_trail_run(
        self,
        points: list[tuple],
        flat_pace_min_km: float,
    ) -> tuple[int, str, dict[str, int]]:
        """Run trail running prediction. Returns (seconds, method_name, all_methods)."""
        service = TrailRunService(
            gap_mode=GAPMode.STRAVA,
            flat_pace_min_km=flat_pace_min_km,
            apply_fatigue=False,
        )
        result = service.calculate_route(points)

        # Convert hours → seconds for all methods
        all_methods: dict[str, int] = {}
        for key in [
            "all_run_strava",
            "all_run_minetti",
            "all_run_strava_minetti",
            "run_hike_strava_tobler",
            "run_hike_strava_naismith",
            "run_hike_minetti_tobler",
            "run_hike_minetti_naismith",
            "run_hike_strava_minetti_tobler",
            "run_hike_strava_minetti_naismith",
            "tobler",
            "naismith",
        ]:
            val = result.totals.get(key)
            if val is not None:
                all_methods[key] = int(val * 3600)

        # Primary method: all_run_strava
        primary_key = "all_run_strava"
        primary_s = all_methods.get(primary_key, 0)

        return primary_s, "trail_run_strava_gap", all_methods

    def _predict_hiking(
        self,
        points: list[tuple],
    ) -> tuple[int, str, dict[str, int]]:
        """Run hiking prediction (Tobler + Naismith). Returns (seconds, method, all)."""
        comparison = ComparisonService()
        result = comparison.compare_route(points)

        all_methods: dict[str, int] = {}
        for key, val in result.totals.items():
            if val is not None:
                all_methods[key] = int(val * 3600)

        primary_key = "tobler"
        primary_s = all_methods.get(primary_key, 0)

        return primary_s, "hiking_tobler", all_methods

    def _add_comparison(
        self,
        prediction: RacePrediction,
        race_id: str,
        distance_id: str,
    ) -> None:
        """Add percentile and stats from latest past results."""
        latest = self.catalog.get_latest_results_path(race_id)
        if not latest:
            return

        year, path = latest
        data = self.catalog.load_results(race_id, year)
        if not data:
            return

        # Find matching distance in results
        # Match by distance_id or by lowercase name
        dist_info = self.catalog.get_distance(race_id, distance_id)
        dist_results = find_distance_results(data, dist_info)
        if not dist_results or not dist_results.results:
            return

        stats = calculate_stats(dist_results.results)
        percentile = get_percentile(dist_results.results, prediction.predicted_time_s)

        # Estimate place
        faster_count = sum(
            1 for r in dist_results.results
            if r.time_seconds < prediction.predicted_time_s
        )
        estimated_place = faster_count + 1

        prediction.comparison_year = year
        prediction.stats = stats
        prediction.percentile = percentile
        prediction.estimated_place = estimated_place


def find_distance_results(
    data: RaceEditionData,
    dist_info: RaceDistance | None,
) -> RaceEditionData | None:
    """Find matching distance results by name (handles Russian/English variants)."""
    if not dist_info:
        return None

    target_name = dist_info.name.lower()
    for d in data.distances:
        if d.distance_name.lower() == target_name:
            return d
        # Also match Russian variants
        if target_name == "skyrunning" and d.distance_name.lower() in (
            "skyrunning",
            "скайраннинг",
        ):
            return d
        if target_name == "skyrunning lite" and d.distance_name.lower() in (
            "skyrunning lite",
            "скайраннинг лайт",
        ):
            return d
    return None
