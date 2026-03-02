"""
Runners API Routes

Endpoints for runner profiles and global runner search.
"""

from statistics import median
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.races.repository import RaceRepository
from app.features.races.stats import format_time, get_percentile
from app.features.races.models import RaceResult

router = APIRouter()

_FINISHED_STATUSES = ("finished", "over_time_limit")

# Backyard Ultra: winner = longest time. Invert percentiles & recalculate place.
_BACKYARD_RACE_IDS = {"backyard_ultra_kz"}


# === Pydantic schemas ===


class RunnerProfileSchema(BaseModel):
    id: int
    name: str
    name_normalized: str
    club: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None


class RunnerRaceResultSchema(BaseModel):
    race_id: str
    race_name: str
    distance_name: str
    distance_km: Optional[float] = None
    year: int
    race_date: Optional[str] = None
    time_s: int
    time_formatted: str
    place: int
    total_finishers: int
    percentile: float
    category: Optional[str] = None
    club: Optional[str] = None
    status: str = "finished"


class SeasonSummary(BaseModel):
    year: int
    median_percentile: float
    races_count: int
    best_race: Optional[str] = None


class RunnerProfileResponse(BaseModel):
    profile: RunnerProfileSchema
    results: list[RunnerRaceResultSchema]
    total_races: int
    years_active: int
    median_percentile: Optional[float] = None
    seasons: list[SeasonSummary] = []


class RunnerSearchResult(BaseModel):
    id: int
    name: str
    name_normalized: str
    club: Optional[str] = None
    races_count: int
    last_race: Optional[str] = None
    last_year: Optional[int] = None


# === Endpoints ===


@router.get("/search", response_model=list[RunnerSearchResult])
async def search_runners(
    name: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    """Global search: find runners by name across all races."""
    repo = RaceRepository(db)
    runners = repo.search_runners(name, limit=10)

    results = []
    for runner in runners:
        last_race = None
        last_year = None
        last = repo.get_runner_last_race(runner.id)
        if last:
            last_race, last_year = last

        results.append(
            RunnerSearchResult(
                id=runner.id,
                name=runner.name,
                name_normalized=runner.name_normalized,
                club=runner.club,
                races_count=runner.races_count,
                last_race=last_race,
                last_year=last_year,
            )
        )

    return results


@router.get("/{runner_id}", response_model=RunnerProfileResponse)
async def get_runner_profile(
    runner_id: int,
    db: Session = Depends(get_db),
):
    """Get runner profile with all race results across all races."""
    repo = RaceRepository(db)
    runner = repo.get_runner_by_id(runner_id)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Runner not found: {runner_id}")

    profile = RunnerProfileSchema(
        id=runner.id,
        name=runner.name,
        name_normalized=runner.name_normalized,
        club=runner.club,
        category=runner.category,
        gender=runner.gender,
    )

    rows = repo.get_runner_results(runner_id)

    results = []
    percentiles_for_median = []
    years_set = set()

    for result_db, distance, edition, race in rows:
        total_finishers = repo.count_finishers_for_distance(distance.id)
        times = repo.get_finisher_times_for_distance(distance.id)
        is_backyard = race.id in _BACKYARD_RACE_IDS

        # Compute percentile for finishers only
        percentile = 0.0
        if result_db.status in _FINISHED_STATUSES and times:
            # Build lightweight RaceResult list for get_percentile
            fake_results = [
                RaceResult(
                    name="", name_local=None, time_seconds=t, place=0,
                    category=None, gender=None, club=None, bib=None,
                    pace=None, birth_year=None, nationality=None,
                )
                for t in times
            ]
            percentile = get_percentile(fake_results, result_db.time_seconds)
            # Backyard Ultra: longer time = better, invert percentile
            if is_backyard:
                percentile = round(100.0 - percentile, 1)
            percentiles_for_median.append(percentile)

        # Backyard Ultra: recalculate place (longest time = 1st)
        place = result_db.place
        if is_backyard and result_db.status in _FINISHED_STATUSES and total_finishers > 0:
            place = total_finishers - result_db.place + 1

        years_set.add(edition.year)

        results.append(
            RunnerRaceResultSchema(
                race_id=race.id,
                race_name=race.name,
                distance_name=distance.name,
                distance_km=distance.distance_km,
                year=edition.year,
                race_date=edition.date,
                time_s=result_db.time_seconds,
                time_formatted=format_time(result_db.time_seconds) if result_db.time_seconds else "0:00",
                place=place,
                total_finishers=total_finishers,
                percentile=percentile,
                category=result_db.category,
                club=result_db.club,
                status=result_db.status or "finished",
            )
        )

    median_percentile = None
    if percentiles_for_median:
        median_percentile = round(median(percentiles_for_median), 1)

    # Build season summaries from collected results
    seasons_map: dict[int, list[tuple[float, str]]] = {}  # year → [(percentile, race_name)]
    for r in results:
        if r.status in _FINISHED_STATUSES:
            seasons_map.setdefault(r.year, []).append((r.percentile, r.race_name))

    seasons = []
    for year in sorted(seasons_map):
        entries = seasons_map[year]
        pcts = [e[0] for e in entries]
        # Best race = lowest percentile (best placement)
        best_entry = min(entries, key=lambda e: e[0])
        seasons.append(
            SeasonSummary(
                year=year,
                median_percentile=round(median(pcts), 1),
                races_count=len(entries),
                best_race=best_entry[1],
            )
        )

    return RunnerProfileResponse(
        profile=profile,
        results=results,
        total_races=len(results),
        years_active=len(years_set),
        median_percentile=median_percentile,
        seasons=seasons,
    )
