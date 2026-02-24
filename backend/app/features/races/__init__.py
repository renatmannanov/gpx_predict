"""Races feature module — race results parsing, statistics, predictions."""

from .models import (
    RaceResult,
    RaceDistanceResults,
    RaceEditionData,
    RaceStats,
    TimeBucket,
)
from .clax_parser import ClaxParser
from .stats import calculate_stats, search_by_name, get_percentile, format_time
from .catalog import RaceCatalog, Race, RaceDistance, RaceEdition

__all__ = [
    "RaceResult",
    "RaceDistanceResults",
    "RaceEditionData",
    "RaceStats",
    "TimeBucket",
    "ClaxParser",
    "calculate_stats",
    "search_by_name",
    "get_percentile",
    "format_time",
    "RaceCatalog",
    "Race",
    "RaceDistance",
    "RaceEdition",
]
