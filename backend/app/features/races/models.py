"""Data models for race results (dataclasses, no DB dependency)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RaceResult:
    """Single participant result."""

    name: str  # Latin: "Kenzhin Arman"
    name_local: str | None  # Cyrillic if available: "Кенжин Арман"
    time_seconds: int  # 3125
    place: int  # 1-based, computed per distance
    category: str | None  # "M_30-39"
    gender: str | None  # "M" / "F"
    club: str | None  # "TRC ALMATY"
    bib: str | None  # "107"
    pace: str | None  # "05:47" min/km (from CLAX)
    birth_year: int | None  # 1988
    nationality: str | None  # "KAZ"
    over_time_limit: bool = False  # hd="1" in CLAX


@dataclass
class TimeBucket:
    """Time distribution bucket for statistics."""

    label: str  # "< 40 мин"
    min_s: int
    max_s: int
    count: int
    percent: float


@dataclass
class RaceStats:
    """Aggregate statistics for a distance."""

    finishers: int
    best_time_s: int
    worst_time_s: int
    median_time_s: int
    p25_time_s: int  # top-25% (fast)
    p75_time_s: int  # top-75% (slow)
    time_buckets: list[TimeBucket] = field(default_factory=list)


@dataclass
class RaceDistanceResults:
    """Results for one distance within a race edition."""

    distance_name: str  # "Skyrunning"
    distance_km: float | None
    elevation_gain_m: int | None
    results: list[RaceResult] = field(default_factory=list)


@dataclass
class RaceEditionData:
    """Full parsed data for one race edition (one year)."""

    race_name: str  # "Alpine Race"
    year: int  # 2025
    date: str | None  # "2025-03-01"
    source_url: str | None  # original CLAX URL
    distances: list[RaceDistanceResults] = field(default_factory=list)
