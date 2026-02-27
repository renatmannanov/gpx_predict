"""RaceRepository — read race data from the database.

Replaces JSON file reads from RaceCatalog for all results/search/stats operations.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db_models import Race, RaceDistance, RaceEdition, RaceResultDB
from .models import RaceDistanceResults, RaceEditionData, RaceResult, RaceStats
from .name_utils import normalize_name
from .stats import calculate_stats


class RaceRepository:
    """Read-only access to race data in the database."""

    def __init__(self, db: Session):
        self.db = db

    def list_races(self) -> list[Race]:
        """Get all races with editions."""
        return self.db.execute(
            select(Race).order_by(Race.name)
        ).scalars().all()

    def get_race(self, race_id: str) -> Race | None:
        """Get a race by ID."""
        return self.db.get(Race, race_id)

    def get_years_with_results(self, race_id: str) -> list[int]:
        """Get list of years that have results for a race."""
        rows = self.db.execute(
            select(RaceEdition.year)
            .where(RaceEdition.race_id == race_id)
            .order_by(RaceEdition.year)
        ).scalars().all()
        return list(rows)

    def get_latest_year(self, race_id: str) -> int | None:
        """Get the most recent year with results."""
        return self.db.execute(
            select(RaceEdition.year)
            .where(RaceEdition.race_id == race_id)
            .order_by(RaceEdition.year.desc())
            .limit(1)
        ).scalar_one_or_none()

    def load_results(self, race_id: str, year: int) -> RaceEditionData | None:
        """Load results for a specific race edition from DB.

        Returns the same RaceEditionData dataclass that the old JSON loader returned,
        so existing code (stats, API schemas) works without changes.
        """
        edition = self.db.execute(
            select(RaceEdition).where(
                RaceEdition.race_id == race_id,
                RaceEdition.year == year,
            )
        ).scalar_one_or_none()
        if not edition:
            return None

        race = self.db.get(Race, race_id)

        distances_data = []
        db_distances = self.db.execute(
            select(RaceDistance)
            .where(RaceDistance.edition_id == edition.id)
            .order_by(RaceDistance.name)
        ).scalars().all()

        for dist in db_distances:
            db_results = self.db.execute(
                select(RaceResultDB)
                .where(RaceResultDB.distance_id == dist.id)
                .order_by(RaceResultDB.place)
            ).scalars().all()

            results = [
                RaceResult(
                    name=r.name,
                    name_local=None,
                    time_seconds=r.time_seconds,
                    place=r.place,
                    category=r.category,
                    gender=r.gender,
                    club=r.club,
                    bib=r.bib,
                    pace=None,
                    birth_year=r.birth_year,
                    nationality=r.nationality,
                    over_time_limit=r.over_time_limit or False,
                )
                for r in db_results
            ]

            distances_data.append(
                RaceDistanceResults(
                    distance_name=dist.name,
                    distance_km=dist.distance_km,
                    elevation_gain_m=dist.elevation_gain_m,
                    results=results,
                )
            )

        return RaceEditionData(
            race_name=race.name if race else race_id,
            year=year,
            date=edition.date,
            source_url=edition.source_url,
            distances=distances_data,
        )

    def search_by_name(
        self,
        race_id: str,
        name: str,
        distance_name: str | None = None,
    ) -> dict[int, RaceResult | None]:
        """Search participant by name across all years.

        Uses name_normalized for consistent matching regardless of
        name order or case in CLAX data.

        Returns: {year: RaceResult | None}
        """
        norm = normalize_name(name)
        years = self.get_years_with_results(race_id)
        results_by_year: dict[int, RaceResult | None] = {}

        for year in years:
            query = (
                select(RaceResultDB, RaceDistance)
                .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
                .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
                .where(
                    RaceEdition.race_id == race_id,
                    RaceEdition.year == year,
                    RaceResultDB.name_normalized == norm,
                )
            )
            if distance_name:
                query = query.where(RaceDistance.name == distance_name)

            # Take first match
            row = self.db.execute(query.limit(1)).first()
            if row:
                r, dist = row
                results_by_year[year] = RaceResult(
                    name=r.name,
                    name_local=None,
                    time_seconds=r.time_seconds,
                    place=r.place,
                    category=r.category,
                    gender=r.gender,
                    club=r.club,
                    bib=r.bib,
                    pace=None,
                    birth_year=r.birth_year,
                    nationality=r.nationality,
                    over_time_limit=r.over_time_limit or False,
                )
            else:
                results_by_year[year] = None

        return results_by_year

    def get_distance_stats(
        self, race_id: str, year: int, distance_name: str,
    ) -> tuple[RaceStats, list[RaceResult]] | None:
        """Get stats and results for a specific distance.

        Returns (stats, results) or None if not found.
        """
        data = self.load_results(race_id, year)
        if not data:
            return None

        for dist in data.distances:
            if dist.distance_name == distance_name:
                stats = calculate_stats(dist.results)
                return stats, dist.results

        return None
