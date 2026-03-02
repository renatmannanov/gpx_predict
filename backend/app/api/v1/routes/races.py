"""
Races API Routes

Endpoints for race catalog, results, search, and predictions.
Data reads from PostgreSQL via RaceRepository.
GPX file access via RaceCatalog (file system).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import CONTENT_DIR
from app.db.session import get_async_db, get_db
from app.features.races.catalog import RaceCatalog
from app.features.races.repository import RaceRepository
from app.features.races.service import RaceService
from app.features.races.stats import calculate_stats, format_time, get_percentile
from app.features.trail_run.repository import TrailRunProfileRepository
from app.features.users.repository import UserRepository

router = APIRouter()

# RaceCatalog — only for GPX file paths
_catalog = RaceCatalog(CONTENT_DIR)

# Non-running distance keywords — hide from results until discipline field in DB
_NON_RUNNING_KEYWORDS = [
    "ski ", "ski-", "ски-альп", "splitboard", "skitour",
    "bike", "mtb", "velo", "gravel",
]

# Backyard Ultra: winner = longest time. Reverse sort + recalculate places.
_BACKYARD_RACE_IDS = {"backyard_ultra_kz"}


def _is_running_distance(name: str) -> bool:
    """Return False for non-running disciplines (bike, ski, etc.)."""
    lower = name.lower()
    return not any(kw in lower for kw in _NON_RUNNING_KEYWORDS)


# === Pydantic schemas ===


class RaceDistanceSchema(BaseModel):
    id: str  # distance name used as ID
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
    total_finishers: Optional[int] = None  # latest year, all distances


class PercentileBucketSchema(BaseModel):
    label: str  # "top-10%"
    level: str  # "elite" | "good" | "mid" | "below" | "low"
    min_pct: int
    max_pct: int
    count: int
    percent: float


class RaceStatsSchema(BaseModel):
    finishers: int
    best_time: str
    worst_time: str
    median_time: str
    p25_time: str
    p75_time: str
    time_buckets: list[dict] = []
    percentile_buckets: list[PercentileBucketSchema] = []
    gender_distribution: list[dict] = []
    category_distribution: list[dict] = []
    club_stats: list[dict] = []
    total_participants: int = 0
    dnf_count: int = 0
    dns_count: int = 0
    dnf_rate: Optional[float] = None


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
    name_normalized: Optional[str] = None
    runner_id: Optional[int] = None
    bib: Optional[str] = None
    status: str = "finished"


class DistanceResultsSchema(BaseModel):
    distance_name: str
    distance_km: Optional[float] = None
    year: int
    stats: RaceStatsSchema
    results: list[RaceResultSchema] = []


class SearchResultSchema(BaseModel):
    year: int
    result: Optional[RaceResultSchema] = None
    percentile: Optional[float] = None
    total_finishers: Optional[int] = None
    gender_percentile: Optional[float] = None
    category_rank: Optional[int] = None
    category_total: Optional[int] = None


class PredictRequest(BaseModel):
    distance_id: str
    flat_pace_min_km: float = Field(ge=3.0, le=15.0)
    mode: str = "trail_run"  # "trail_run" or "hiking"
    telegram_id: Optional[int] = None


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


# === Helpers ===


def _stats_to_schema(stats, dnf_rate=None) -> RaceStatsSchema:
    """Convert RaceStats dataclass to Pydantic schema."""
    return RaceStatsSchema(
        finishers=stats.finishers,
        best_time=format_time(stats.best_time_s),
        worst_time=format_time(stats.worst_time_s),
        median_time=format_time(stats.median_time_s),
        p25_time=format_time(stats.p25_time_s),
        p75_time=format_time(stats.p75_time_s),
        time_buckets=[
            {"label": b.label, "count": b.count, "percent": b.percent}
            for b in stats.time_buckets
        ],
        percentile_buckets=[
            PercentileBucketSchema(
                label=b.label, level=b.level,
                min_pct=b.min_pct, max_pct=b.max_pct,
                count=b.count, percent=b.percent,
            )
            for b in stats.percentile_buckets
        ],
        gender_distribution=[
            {"gender": g.gender, "count": g.count, "percent": g.percent}
            for g in stats.gender_distribution
        ],
        category_distribution=[
            {"category": c.category, "count": c.count, "percent": c.percent}
            for c in stats.category_distribution
        ],
        club_stats=[
            {
                "club": c.club,
                "count": c.count,
                "best_time_s": c.best_time_s,
                "best_time": c.best_time,
                "avg_percentile": c.avg_percentile,
            }
            for c in stats.club_stats
        ],
        total_participants=stats.total_participants,
        dnf_count=stats.dnf_count,
        dns_count=stats.dns_count,
        dnf_rate=dnf_rate,
    )


# === Endpoints ===


@router.get("", response_model=list[RaceSchema])
async def list_races(db: Session = Depends(get_db)):
    """Get race catalog (all races with distances and editions)."""
    repo = RaceRepository(db)
    races = repo.list_races()
    result = []

    # Hide Almaty Marathon races for now (dirty data — cities instead of clubs)
    HIDDEN_SOURCES = {"_am_kz"}
    races = [r for r in races if not any(r.id.endswith(s) for s in HIDDEN_SOURCES)]

    for race in races:
        # Build editions from DB
        editions = []
        for ed in sorted(race.editions, key=lambda e: e.year):
            editions.append(
                RaceEditionSchema(
                    year=ed.year,
                    date=ed.date,
                    has_results=True,  # all DB editions have results
                )
            )

        # Build distances from the latest edition
        distances = []
        if race.editions:
            latest_ed = max(race.editions, key=lambda e: e.year)
            for dist in latest_ed.distances:
                if not _is_running_distance(dist.name):
                    continue
                # Check if GPX exists via catalog
                has_gpx = _catalog.get_gpx_path(race.id, dist.name) is not None
                distances.append(
                    RaceDistanceSchema(
                        id=dist.name,
                        name=dist.name,
                        distance_km=dist.distance_km,
                        elevation_gain_m=dist.elevation_gain_m,
                        has_gpx=has_gpx,
                    )
                )

        # Total finishers from latest edition
        total_finishers = None
        if race.editions:
            latest_year = max(ed.year for ed in race.editions)
            total_finishers = repo.count_finishers(race.id, latest_year)

        result.append(
            RaceSchema(
                id=race.id,
                name=race.name,
                type=race.type,
                location=race.location,
                distances=distances,
                editions=editions,
                total_finishers=total_finishers,
            )
        )

    return result


@router.get("/{race_id}", response_model=RaceSchema)
async def get_race(race_id: str, db: Session = Depends(get_db)):
    """Get single race details."""
    repo = RaceRepository(db)
    race = repo.get_race(race_id)
    if not race:
        raise HTTPException(status_code=404, detail=f"Race not found: {race_id}")

    editions = [
        RaceEditionSchema(
            year=ed.year,
            date=ed.date,
            has_results=True,
        )
        for ed in sorted(race.editions, key=lambda e: e.year)
    ]

    distances = []
    total_finishers = None
    if race.editions:
        latest_ed = max(race.editions, key=lambda e: e.year)
        total_finishers = repo.count_finishers(race_id, latest_ed.year)
        for dist in latest_ed.distances:
            if not _is_running_distance(dist.name):
                continue
            has_gpx = _catalog.get_gpx_path(race_id, dist.name) is not None
            distances.append(
                RaceDistanceSchema(
                    id=dist.name,
                    name=dist.name,
                    distance_km=dist.distance_km,
                    elevation_gain_m=dist.elevation_gain_m,
                    has_gpx=has_gpx,
                )
            )

    return RaceSchema(
        id=race.id,
        name=race.name,
        type=race.type,
        location=race.location,
        distances=distances,
        editions=editions,
        total_finishers=total_finishers,
    )


@router.get("/{race_id}/{year}/results", response_model=list[DistanceResultsSchema])
async def get_results(race_id: str, year: int, db: Session = Depends(get_db)):
    """Get race results for a specific year (all distances)."""
    repo = RaceRepository(db)
    data = repo.load_results(race_id, year)
    if not data:
        raise HTTPException(
            status_code=404, detail=f"No results for {race_id} {year}"
        )

    is_backyard = race_id in _BACKYARD_RACE_IDS

    result = []
    for dist in data.distances:
        if not _is_running_distance(dist.distance_name):
            continue

        race_results = list(dist.results)

        # Backyard Ultra: reverse finisher order (longest time = 1st place)
        if is_backyard:
            _FINISHED = ("finished", "over_time_limit")
            finishers = [r for r in race_results if r.status in _FINISHED]
            non_finishers = [r for r in race_results if r.status not in _FINISHED]
            finishers.sort(key=lambda r: r.time_seconds, reverse=True)
            for i, r in enumerate(finishers, 1):
                r.place = i
            race_results = finishers + non_finishers

        stats = calculate_stats(race_results)
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
                name_normalized=r.name_normalized,
                runner_id=r.runner_id,
                bib=r.bib,
                status=r.status,
            )
            for r in race_results
        ]

        # DNF rate: dnf / (total - dns)
        starters = stats.total_participants - stats.dns_count
        dnf_rate = (
            round(stats.dnf_count / starters * 100, 1) if starters > 0 else None
        )

        result.append(
            DistanceResultsSchema(
                distance_name=dist.distance_name,
                distance_km=dist.distance_km,
                year=year,
                stats=_stats_to_schema(stats, dnf_rate),
                results=results_out,
            )
        )

    return result


@router.get("/{race_id}/search", response_model=list[SearchResultSchema])
async def search_results(
    race_id: str,
    name: str = Query(..., min_length=2),
    distance_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Search participant by name across all years.

    Uses normalized name matching — order and case don't matter.
    "Baikashev Shyngys" == "Shyngys Baikashev" == "BAIKASHEV Shyngys"
    """
    repo = RaceRepository(db)
    race = repo.get_race(race_id)
    if not race:
        raise HTTPException(status_code=404, detail=f"Race not found: {race_id}")

    results_by_year = repo.search_by_name(race_id, name, distance_name=distance_id)
    is_backyard = race_id in _BACKYARD_RACE_IDS

    output = []
    for year in sorted(results_by_year.keys(), reverse=True):
        r = results_by_year[year]
        if not r:
            output.append(SearchResultSchema(year=year))
            continue

        result_schema = RaceResultSchema(
            name=r.name,
            name_local=r.name_local,
            time_s=r.time_seconds,
            time_formatted=format_time(r.time_seconds),
            place=r.place,
            category=r.category,
            gender=r.gender,
            club=r.club,
            pace=r.pace,
            name_normalized=r.name_normalized,
            runner_id=r.runner_id,
            bib=r.bib,
            status=r.status,
        )

        # Compute percentiles for finishers
        percentile = None
        total_finishers = None
        gender_percentile = None
        category_rank = None
        category_total = None

        if r.status in ("finished", "over_time_limit"):
            edition_data = repo.load_results(race_id, year)
            if edition_data:
                for d in edition_data.distances:
                    # Match: either explicit distance_id, or find by name_normalized
                    if distance_id and d.distance_name != distance_id:
                        continue
                    if not distance_id and not any(
                        res.name_normalized == r.name_normalized
                        for res in d.results
                    ):
                        continue

                    finishers = [
                        res for res in d.results
                        if res.status in ("finished", "over_time_limit")
                    ]
                    total_finishers = len(finishers)
                    percentile = get_percentile(finishers, r.time_seconds)
                    # Backyard Ultra: longer = better, invert percentile
                    if is_backyard:
                        percentile = round(100.0 - percentile, 1)

                    # Gender percentile
                    if r.gender:
                        same_gender = [
                            res for res in finishers if res.gender == r.gender
                        ]
                        if same_gender:
                            gender_percentile = get_percentile(
                                same_gender, r.time_seconds
                            )
                            if is_backyard:
                                gender_percentile = round(100.0 - gender_percentile, 1)

                    # Category rank
                    if r.category:
                        same_cat = [
                            res for res in finishers
                            if res.category == r.category
                        ]
                        if same_cat:
                            category_total = len(same_cat)
                            if is_backyard:
                                # Backyard: longer time = better rank
                                category_rank = (
                                    sum(
                                        1 for res in same_cat
                                        if res.time_seconds > r.time_seconds
                                    )
                                    + 1
                                )
                            else:
                                category_rank = (
                                    sum(
                                        1 for res in same_cat
                                        if res.time_seconds < r.time_seconds
                                    )
                                    + 1
                                )
                    break

        output.append(
            SearchResultSchema(
                year=year,
                result=result_schema,
                percentile=percentile,
                total_finishers=total_finishers,
                gender_percentile=gender_percentile,
                category_rank=category_rank,
                category_total=category_total,
            )
        )

    return output


@router.post("/{race_id}/predict", response_model=PredictResponse)
async def predict_race(
    race_id: str,
    request: PredictRequest,
    db: AsyncSession = Depends(get_async_db),
    sync_db: Session = Depends(get_db),
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

    service = RaceService(_catalog, sync_db)
    try:
        prediction = service.predict_by_pace(
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
        stats_schema = _stats_to_schema(s)

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
