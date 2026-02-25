"""
Races API Routes

Endpoints for race catalog, results, search, and predictions.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import CONTENT_DIR
from app.db.session import get_async_db
from app.features.races.catalog import RaceCatalog, normalize_distance_name
from app.features.races.matching import find_across_years
from app.features.races.service import RaceService
from app.features.races.stats import calculate_stats, format_time
from app.features.trail_run.repository import TrailRunProfileRepository
from app.features.users.repository import UserRepository

router = APIRouter()

# Singleton catalog (loaded once, cached)
_catalog = RaceCatalog(CONTENT_DIR)
_service = RaceService(_catalog)


# === Pydantic schemas ===


class RaceDistanceSchema(BaseModel):
    id: str
    name: str
    distance_km: Optional[float] = None
    elevation_gain_m: Optional[int] = None
    start_altitude_m: Optional[int] = None
    finish_altitude_m: Optional[int] = None
    grade: Optional[str] = None
    has_gpx: bool = False


class RaceEditionSchema(BaseModel):
    year: int
    date: Optional[str] = None
    has_results: bool = False
    registration_url: Optional[str] = None


class RaceSchema(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    location: Optional[str] = None
    distances: list[RaceDistanceSchema] = []
    editions: list[RaceEditionSchema] = []
    next_date: Optional[str] = None


class RaceStatsSchema(BaseModel):
    finishers: int
    best_time: str
    worst_time: str
    median_time: str
    p25_time: str
    p75_time: str
    time_buckets: list[dict] = []


class RaceResultSchema(BaseModel):
    name: str
    name_local: Optional[str] = None
    time_s: int
    time_formatted: str
    place: int
    category: Optional[str] = None
    gender: Optional[str] = None
    club: Optional[str] = None
    pace: Optional[str] = None


class DistanceResultsSchema(BaseModel):
    distance_name: str
    distance_km: Optional[float] = None
    year: int
    stats: RaceStatsSchema
    results: list[RaceResultSchema] = []


class SearchResultSchema(BaseModel):
    year: int
    result: Optional[RaceResultSchema] = None


class PredictRequest(BaseModel):
    distance_id: str
    flat_pace_min_km: float = Field(ge=3.0, le=15.0)
    mode: str = "trail_run"  # "trail_run" or "hiking"
    telegram_id: Optional[str] = None


class PredictionMethodSchema(BaseModel):
    name: str
    time_s: int
    time_formatted: str


class PredictResponse(BaseModel):
    race_name: str
    distance_name: str
    distance_km: Optional[float] = None
    elevation_gain_m: Optional[int] = None
    predicted_time_s: int
    predicted_time: str
    method: str
    flat_pace_used: float
    all_methods: list[PredictionMethodSchema] = []
    # Personalization
    personalized: bool = False
    personalized_times: Optional[dict] = None  # {fast, moderate, easy} → time_s
    run_profile_stats: Optional[dict] = None
    # Comparison
    percentile: Optional[float] = None
    estimated_place: Optional[int] = None
    comparison_year: Optional[int] = None
    total_finishers: Optional[int] = None
    stats: Optional[RaceStatsSchema] = None


# === Endpoints ===


@router.get("", response_model=list[RaceSchema])
async def list_races():
    """Get race catalog (all races with distances and editions)."""
    races = _catalog.races
    result = []
    for race in races:
        # Find next upcoming edition
        next_edition = None
        for edition in sorted(race.editions, key=lambda e: e.year):
            if not edition.results_file:  # No results = future or current
                next_edition = edition
                break

        distances = [
            RaceDistanceSchema(
                id=d.id,
                name=d.name,
                distance_km=d.distance_km,
                elevation_gain_m=d.elevation_gain_m,
                start_altitude_m=d.start_altitude_m,
                finish_altitude_m=d.finish_altitude_m,
                grade=d.grade,
                has_gpx=d.gpx_file is not None
                and _catalog.get_gpx_path(race.id, d.id) is not None,
            )
            for d in race.distances
            if d.distance_km is not None  # Only show distances with data
        ]

        editions = [
            RaceEditionSchema(
                year=e.year,
                date=e.date,
                has_results=e.results_file is not None,
                registration_url=e.registration_url,
            )
            for e in race.editions
        ]

        result.append(
            RaceSchema(
                id=race.id,
                name=race.name,
                type=race.type,
                location=race.location,
                distances=distances,
                editions=editions,
                next_date=next_edition.date if next_edition else None,
            )
        )

    return result


@router.get("/{race_id}", response_model=RaceSchema)
async def get_race(race_id: str):
    """Get single race details."""
    race = _catalog.get_race(race_id)
    if not race:
        raise HTTPException(status_code=404, detail=f"Race not found: {race_id}")

    next_edition = None
    for edition in sorted(race.editions, key=lambda e: e.year):
        if not edition.results_file:
            next_edition = edition
            break

    distances = [
        RaceDistanceSchema(
            id=d.id,
            name=d.name,
            distance_km=d.distance_km,
            elevation_gain_m=d.elevation_gain_m,
            start_altitude_m=d.start_altitude_m,
            finish_altitude_m=d.finish_altitude_m,
            grade=d.grade,
            has_gpx=d.gpx_file is not None
            and _catalog.get_gpx_path(race.id, d.id) is not None,
        )
        for d in race.distances
        if d.distance_km is not None
    ]

    editions = [
        RaceEditionSchema(
            year=e.year,
            date=e.date,
            has_results=e.results_file is not None,
            registration_url=e.registration_url,
        )
        for e in race.editions
    ]

    return RaceSchema(
        id=race.id,
        name=race.name,
        type=race.type,
        location=race.location,
        distances=distances,
        editions=editions,
        next_date=next_edition.date if next_edition else None,
    )


@router.get("/{race_id}/{year}/results", response_model=list[DistanceResultsSchema])
async def get_results(race_id: str, year: int):
    """Get race results for a specific year (all distances)."""
    race = _catalog.get_race(race_id)
    if not race:
        raise HTTPException(status_code=404, detail=f"Race not found: {race_id}")

    data = _catalog.load_results(race_id, year)
    if not data:
        raise HTTPException(
            status_code=404, detail=f"No results for {race_id} {year}"
        )

    result = []
    for dist in data.distances:
        stats = calculate_stats(dist.results)
        results_out = [
            RaceResultSchema(
                name=r.name,
                name_local=r.name_local,
                time_s=r.time_seconds,
                time_formatted=format_time(r.time_seconds),
                place=r.place,
                category=r.category,
                gender=r.gender,
                club=r.club,
                pace=r.pace,
            )
            for r in dist.results
        ]
        # Normalize distance name to canonical catalog form
        # (e.g. "Скайраннинг" → "Skyrunning" for 2023 data)
        canonical_name = normalize_distance_name(dist.distance_name, race)
        result.append(
            DistanceResultsSchema(
                distance_name=canonical_name,
                distance_km=dist.distance_km,
                year=year,
                stats=RaceStatsSchema(
                    finishers=stats.finishers,
                    best_time=format_time(stats.best_time_s),
                    worst_time=format_time(stats.worst_time_s),
                    median_time=format_time(stats.median_time_s),
                    p25_time=format_time(stats.p25_time_s),
                    p75_time=format_time(stats.p75_time_s),
                    time_buckets=[
                        {
                            "label": b.label,
                            "count": b.count,
                            "percent": b.percent,
                        }
                        for b in stats.time_buckets
                    ],
                ),
                results=results_out,
            )
        )

    return result


@router.get("/{race_id}/search", response_model=list[SearchResultSchema])
async def search_results(
    race_id: str,
    name: str = Query(..., min_length=2),
    distance_id: Optional[str] = None,
):
    """Search participant by name across all years.

    If distance_id is provided, searches only that distance.
    Otherwise searches the first distance with results.
    """
    race = _catalog.get_race(race_id)
    if not race:
        raise HTTPException(status_code=404, detail=f"Race not found: {race_id}")

    # Default to first distance with GPX
    if not distance_id:
        for d in race.distances:
            if d.distance_km is not None:
                distance_id = d.id
                break
    if not distance_id:
        raise HTTPException(status_code=400, detail="No valid distance found")

    results_by_year = find_across_years(_catalog, race_id, distance_id, name)

    output = []
    for year in sorted(results_by_year.keys(), reverse=True):
        r = results_by_year[year]
        output.append(
            SearchResultSchema(
                year=year,
                result=RaceResultSchema(
                    name=r.name,
                    name_local=r.name_local,
                    time_s=r.time_seconds,
                    time_formatted=format_time(r.time_seconds),
                    place=r.place,
                    category=r.category,
                    gender=r.gender,
                    club=r.club,
                    pace=r.pace,
                )
                if r
                else None,
            )
        )

    return output


@router.post("/{race_id}/predict", response_model=PredictResponse)
async def predict_race(
    race_id: str,
    request: PredictRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Predict race time based on flat pace."""
    # Load run profile if telegram_id provided
    run_profile = None
    if request.telegram_id:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(request.telegram_id)
        if user:
            run_repo = TrailRunProfileRepository(db)
            run_profile = await run_repo.get_by_user_id(user.id)

    try:
        prediction = _service.predict_by_pace(
            race_id=race_id,
            distance_id=request.distance_id,
            flat_pace_min_km=request.flat_pace_min_km,
            mode=request.mode,
            run_profile=run_profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    all_methods = [
        PredictionMethodSchema(
            name=name,
            time_s=seconds,
            time_formatted=format_time(seconds),
        )
        for name, seconds in sorted(prediction.all_methods.items(), key=lambda x: x[1])
    ]

    stats_schema = None
    total_finishers = None
    if prediction.stats:
        s = prediction.stats
        total_finishers = s.finishers
        stats_schema = RaceStatsSchema(
            finishers=s.finishers,
            best_time=format_time(s.best_time_s),
            worst_time=format_time(s.worst_time_s),
            median_time=format_time(s.median_time_s),
            p25_time=format_time(s.p25_time_s),
            p75_time=format_time(s.p75_time_s),
            time_buckets=[
                {"label": b.label, "count": b.count, "percent": b.percent}
                for b in s.time_buckets
            ],
        )

    return PredictResponse(
        race_name=prediction.race_name,
        distance_name=prediction.distance_name,
        distance_km=prediction.distance_km,
        elevation_gain_m=prediction.elevation_gain_m,
        predicted_time_s=prediction.predicted_time_s,
        predicted_time=format_time(prediction.predicted_time_s),
        method=prediction.method,
        flat_pace_used=prediction.flat_pace_used,
        all_methods=all_methods,
        personalized=prediction.personalized,
        personalized_times=prediction.personalized_times,
        run_profile_stats=prediction.run_profile_stats,
        percentile=prediction.percentile,
        estimated_place=prediction.estimated_place,
        comparison_year=prediction.comparison_year,
        total_finishers=total_finishers,
        stats=stats_schema,
    )
