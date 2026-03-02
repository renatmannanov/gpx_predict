"""RaceRepository — read race data from the database.

Replaces JSON file reads from RaceCatalog for all results/search/stats operations.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import datetime

from .db_models import Club, Race, RaceDistance, RaceEdition, RaceResultDB, Runner
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
                    status=r.status or "finished",
                    name_normalized=r.name_normalized,
                    runner_id=r.runner_id,
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
        Supports partial match: "Baikashev" finds "baikashev shyngys".

        Returns: {year: RaceResult | None}
        """
        norm = normalize_name(name)
        years = self.get_years_with_results(race_id)
        results_by_year: dict[int, RaceResult | None] = {}

        # Build filter: all words in the query must appear in name_normalized
        norm_words = norm.split()
        name_filters = [
            RaceResultDB.name_normalized.contains(word) for word in norm_words
        ]

        for year in years:
            query = (
                select(RaceResultDB, RaceDistance)
                .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
                .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
                .where(
                    RaceEdition.race_id == race_id,
                    RaceEdition.year == year,
                    *name_filters,
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
                    status=r.status or "finished",
                    name_normalized=r.name_normalized,
                    runner_id=r.runner_id,
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

    def count_finishers(self, race_id: str, year: int) -> int:
        """Count total finishers (finished + over_time_limit) across all distances."""
        return self.db.execute(
            select(func.count(RaceResultDB.id))
            .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
            .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
            .where(
                RaceEdition.race_id == race_id,
                RaceEdition.year == year,
                RaceResultDB.status.in_(("finished", "over_time_limit")),
            )
        ).scalar() or 0

    # --- Runner management ---

    def get_or_create_runner(
        self,
        name_normalized: str,
        name: str,
        club: str | None = None,
        gender: str | None = None,
        category: str | None = None,
        birth_year: int | None = None,
    ) -> Runner:
        """Find or create a runner by normalized name.

        If found, updates mutable fields (club, category, gender) from latest data.
        """
        runner = self.db.execute(
            select(Runner).where(Runner.name_normalized == name_normalized)
        ).scalar_one_or_none()

        if runner:
            # Update with latest known data
            if club:
                runner.club = club
            if gender:
                runner.gender = gender
            if category:
                runner.category = category
            if birth_year:
                runner.birth_year = birth_year
            runner.name = name
            runner.updated_at = datetime.utcnow()
        else:
            runner = Runner(
                name=name,
                name_normalized=name_normalized,
                club=club,
                gender=gender,
                category=category,
                birth_year=birth_year,
                races_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(runner)
            self.db.flush()  # get the id

        return runner

    def get_runner_by_id(self, runner_id: int) -> Runner | None:
        """Get runner by ID."""
        return self.db.get(Runner, runner_id)

    def get_runner_results(self, runner_id: int) -> list[tuple]:
        """Get all results for a runner across all races.

        Returns list of (RaceResultDB, RaceDistance, RaceEdition, Race) tuples,
        ordered by year DESC, race name ASC.
        """
        rows = self.db.execute(
            select(RaceResultDB, RaceDistance, RaceEdition, Race)
            .join(RaceDistance, RaceResultDB.distance_id == RaceDistance.id)
            .join(RaceEdition, RaceDistance.edition_id == RaceEdition.id)
            .join(Race, RaceEdition.race_id == Race.id)
            .where(RaceResultDB.runner_id == runner_id)
            .order_by(RaceEdition.year.desc(), Race.name)
        ).all()
        return rows

    def count_finishers_for_distance(self, distance_id: int) -> int:
        """Count finishers (finished + over_time_limit) for a specific distance."""
        return self.db.execute(
            select(func.count(RaceResultDB.id))
            .where(
                RaceResultDB.distance_id == distance_id,
                RaceResultDB.status.in_(("finished", "over_time_limit")),
            )
        ).scalar() or 0

    def get_finisher_times_for_distance(self, distance_id: int) -> list[int]:
        """Get sorted list of finish times for a distance (only finishers)."""
        rows = self.db.execute(
            select(RaceResultDB.time_seconds)
            .where(
                RaceResultDB.distance_id == distance_id,
                RaceResultDB.status.in_(("finished", "over_time_limit")),
            )
            .order_by(RaceResultDB.time_seconds)
        ).scalars().all()
        return list(rows)

    def search_runners(self, name: str, limit: int = 10) -> list[Runner]:
        """Search runners by normalized name (partial match).

        Returns runners sorted by races_count DESC.
        """
        norm = normalize_name(name)
        norm_words = norm.split()
        filters = [Runner.name_normalized.contains(word) for word in norm_words]

        return self.db.execute(
            select(Runner)
            .where(*filters)
            .order_by(Runner.races_count.desc())
            .limit(limit)
        ).scalars().all()

    def get_runner_last_race(self, runner_id: int) -> tuple[str, int] | None:
        """Get the last race name and year for a runner."""
        row = self.db.execute(
            select(Race.name, RaceEdition.year)
            .join(RaceEdition, Race.id == RaceEdition.race_id)
            .join(RaceDistance, RaceDistance.edition_id == RaceEdition.id)
            .join(RaceResultDB, RaceResultDB.distance_id == RaceDistance.id)
            .where(RaceResultDB.runner_id == runner_id)
            .order_by(RaceEdition.year.desc())
            .limit(1)
        ).first()
        return row if row else None

    # --- Club management ---

    def get_or_create_club(self, club_name: str) -> Club:
        """Find or create a club by name."""
        normalized = club_name.strip().lower()
        club = self.db.execute(
            select(Club).where(Club.name_normalized == normalized)
        ).scalar_one_or_none()

        if not club:
            club = Club(
                name=club_name.strip(),
                name_normalized=normalized,
                runners_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(club)
            self.db.flush()

        return club

    def get_club_by_id(self, club_id: int) -> Club | None:
        """Get club by ID."""
        return self.db.get(Club, club_id)
