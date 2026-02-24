"""Race catalog loader — reads races.yaml and provides access to race data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import RaceDistanceResults, RaceEditionData, RaceResult


@dataclass
class RaceDistance:
    """A single distance within a race."""

    id: str
    name: str
    distance_km: float | None = None
    elevation_gain_m: int | None = None
    start_altitude_m: int | None = None
    finish_altitude_m: int | None = None
    gpx_file: str | None = None
    grade: str | None = None


@dataclass
class RaceEdition:
    """One year/edition of a race."""

    year: int
    date: str | None = None
    results_file: str | None = None
    registration_url: str | None = None


@dataclass
class Race:
    """A race definition from the catalog."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    distances: list[RaceDistance] = field(default_factory=list)
    editions: list[RaceEdition] = field(default_factory=list)


class RaceCatalog:
    """Loads and provides access to race catalog from YAML."""

    def __init__(self, content_dir: Path):
        self.content_dir = content_dir
        self._races: list[Race] | None = None

    def load(self) -> list[Race]:
        """Load catalog from races.yaml."""
        yaml_path = self.content_dir / "races" / "races.yaml"
        if not yaml_path.exists():
            return []

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        races = []
        for r in data.get("races", []):
            distances = [
                RaceDistance(
                    id=d["id"],
                    name=d["name"],
                    distance_km=d.get("distance_km"),
                    elevation_gain_m=d.get("elevation_gain_m"),
                    start_altitude_m=d.get("start_altitude_m"),
                    finish_altitude_m=d.get("finish_altitude_m"),
                    gpx_file=d.get("gpx_file"),
                    grade=d.get("grade"),
                )
                for d in r.get("distances", [])
            ]
            editions = [
                RaceEdition(
                    year=e["year"],
                    date=e.get("date"),
                    results_file=e.get("results_file"),
                    registration_url=e.get("registration_url"),
                )
                for e in r.get("editions", [])
            ]
            races.append(
                Race(
                    id=r["id"],
                    name=r["name"],
                    type=r.get("type"),
                    location=r.get("location"),
                    distances=distances,
                    editions=editions,
                )
            )

        self._races = races
        return races

    @property
    def races(self) -> list[Race]:
        if self._races is None:
            self.load()
        return self._races or []

    def get_race(self, race_id: str) -> Race | None:
        return next((r for r in self.races if r.id == race_id), None)

    def get_distance(self, race_id: str, distance_id: str) -> RaceDistance | None:
        race = self.get_race(race_id)
        if not race:
            return None
        return next((d for d in race.distances if d.id == distance_id), None)

    def get_gpx_path(self, race_id: str, distance_id: str) -> Path | None:
        """Full path to distance GPX file."""
        dist = self.get_distance(race_id, distance_id)
        if not dist or not dist.gpx_file:
            return None
        path = self.content_dir / "races" / "gpx" / dist.gpx_file
        return path if path.exists() else None

    def get_results_path(self, race_id: str, year: int) -> Path | None:
        """Full path to results JSON for a specific year."""
        race = self.get_race(race_id)
        if not race:
            return None
        edition = next((e for e in race.editions if e.year == year), None)
        if not edition or not edition.results_file:
            return None
        path = self.content_dir / "races" / "results" / edition.results_file
        return path if path.exists() else None

    def get_latest_results_path(self, race_id: str) -> tuple[int, Path] | None:
        """Get the most recent results file. Returns (year, path) or None."""
        race = self.get_race(race_id)
        if not race:
            return None
        for edition in sorted(race.editions, key=lambda e: e.year, reverse=True):
            if edition.results_file:
                path = self.content_dir / "races" / "results" / edition.results_file
                if path.exists():
                    return (edition.year, path)
        return None

    def load_results(self, race_id: str, year: int) -> RaceEditionData | None:
        """Load parsed results from JSON file."""
        path = self.get_results_path(race_id, year)
        if not path:
            return None
        return _load_results_json(path)

    def get_years_with_results(self, race_id: str) -> list[int]:
        """Get list of years that have results files."""
        race = self.get_race(race_id)
        if not race:
            return []
        years = []
        for edition in race.editions:
            if edition.results_file:
                path = self.content_dir / "races" / "results" / edition.results_file
                if path.exists():
                    years.append(edition.year)
        return sorted(years)


def _load_results_json(path: Path) -> RaceEditionData:
    """Load RaceEditionData from JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))

    distances = []
    for d in raw["distances"]:
        results = [
            RaceResult(
                name=r["name"],
                name_local=r.get("name_local"),
                time_seconds=r["time_s"],
                place=r["place"],
                category=r.get("category"),
                gender=r.get("gender"),
                club=r.get("club"),
                bib=r.get("bib"),
                pace=r.get("pace"),
                birth_year=r.get("birth_year"),
                nationality=r.get("nationality"),
                over_time_limit=r.get("over_time_limit", False),
            )
            for r in d["results"]
        ]
        distances.append(
            RaceDistanceResults(
                distance_name=d["name"],
                distance_km=d.get("distance_km"),
                elevation_gain_m=d.get("elevation_gain_m"),
                results=results,
            )
        )

    return RaceEditionData(
        race_name=raw["race_name"],
        year=raw["year"],
        date=raw.get("date"),
        source_url=raw.get("source_url"),
        distances=distances,
    )


def find_distance_results(
    data: RaceEditionData,
    dist_info: RaceDistance | None,
) -> RaceDistanceResults | None:
    """Find matching distance results by name (handles Russian/English variants)."""
    if not dist_info:
        return None

    target_name = dist_info.name.lower()
    for d in data.distances:
        if d.distance_name.lower() == target_name:
            return d
        # Match Russian variants
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
