"""
Stats API Routes

Endpoints for aggregate season statistics.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, distinct
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.races.db_models import (
    Race,
    RaceDistance,
    RaceEdition,
    RaceResultDB,
    Runner,
)

router = APIRouter()

_FINISHED_STATUSES = ("finished", "over_time_limit")


# === Pydantic schemas ===


class TopRunnerSchema(BaseModel):
    runner_id: int
    name: str
    club: Optional[str] = None
    races_count: int
    avg_percentile: Optional[float] = None


class TopClubSchema(BaseModel):
    club: str
    runners_count: int
    avg_percentile: Optional[float] = None


class SeasonStatsResponse(BaseModel):
    year: int
    total_races: int
    total_finishers: int  # unique runners by runner_id
    total_clubs: int  # unique clubs
    top_runners: list[TopRunnerSchema]
    top_clubs: list[TopClubSchema]


# === Endpoints ===


@router.get("/season/{year}", response_model=SeasonStatsResponse)
async def get_season_stats(year: int, db: Session = Depends(get_db)):
    """Aggregate stats for a season: total runners, total clubs, top runners/clubs."""

    # Base filter: results for this year, only finishers
    base_filter = [
        RaceEdition.year == year,
        RaceResultDB.status.in_(_FINISHED_STATUSES),
    ]
    base_join = (
        select(RaceResultDB)
        .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
        .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
    )

    # Total unique races (editions) with results
    total_races = db.execute(
        select(func.count(distinct(RaceEdition.id)))
        .join(RaceDistance, RaceDistance.edition_id == RaceEdition.id)
        .join(RaceResultDB, RaceResultDB.distance_id == RaceDistance.id)
        .where(*base_filter)
    ).scalar() or 0

    if total_races == 0:
        raise HTTPException(
            status_code=404, detail=f"No race data for year {year}"
        )

    # Total unique finishers (by runner_id)
    total_finishers = db.execute(
        select(func.count(distinct(RaceResultDB.runner_id)))
        .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
        .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
        .where(*base_filter, RaceResultDB.runner_id.isnot(None))
    ).scalar() or 0

    # Total unique clubs
    total_clubs = db.execute(
        select(func.count(distinct(RaceResultDB.club)))
        .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
        .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
        .where(*base_filter, RaceResultDB.club.isnot(None), RaceResultDB.club != "")
    ).scalar() or 0

    # Top runners: by number of distinct race editions this year
    top_runners_rows = db.execute(
        select(
            RaceResultDB.runner_id,
            Runner.name,
            Runner.club,
            func.count(distinct(RaceEdition.id)).label("races_count"),
        )
        .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
        .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
        .join(Runner, RaceResultDB.runner_id == Runner.id)
        .where(*base_filter, RaceResultDB.runner_id.isnot(None))
        .group_by(RaceResultDB.runner_id, Runner.name, Runner.club)
        .order_by(func.count(distinct(RaceEdition.id)).desc())
        .limit(5)
    ).all()

    top_runners = [
        TopRunnerSchema(
            runner_id=row.runner_id,
            name=row.name,
            club=row.club,
            races_count=row.races_count,
        )
        for row in top_runners_rows
    ]

    # Top clubs: by number of unique runners this year
    top_clubs_rows = db.execute(
        select(
            RaceResultDB.club,
            func.count(distinct(RaceResultDB.runner_id)).label("runners_count"),
        )
        .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
        .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
        .where(
            *base_filter,
            RaceResultDB.club.isnot(None),
            RaceResultDB.club != "",
            RaceResultDB.runner_id.isnot(None),
        )
        .group_by(RaceResultDB.club)
        .order_by(func.count(distinct(RaceResultDB.runner_id)).desc())
        .limit(5)
    ).all()

    top_clubs = [
        TopClubSchema(
            club=row.club,
            runners_count=row.runners_count,
        )
        for row in top_clubs_rows
    ]

    return SeasonStatsResponse(
        year=year,
        total_races=total_races,
        total_finishers=total_finishers,
        total_clubs=total_clubs,
        top_runners=top_runners,
        top_clubs=top_clubs,
    )
