"""User matching — find participant in race results across years."""

from __future__ import annotations

from .catalog import RaceCatalog, find_distance_results
from .models import RaceResult
from .stats import search_by_name


def find_user_in_results(
    results: list[RaceResult],
    name: str,
) -> list[RaceResult]:
    """Search by name (case-insensitive, partial match).

    Searches both `name` (Latin) and `name_local` (Cyrillic) fields.
    """
    return search_by_name(results, name)


def find_across_years(
    catalog: RaceCatalog,
    race_id: str,
    distance_id: str,
    name: str,
) -> dict[int, RaceResult | None]:
    """Find user's results across all years.

    Returns: {year: RaceResult | None}
    Example: {2023: None, 2024: RaceResult(...), 2025: RaceResult(...)}
    """
    years = catalog.get_years_with_results(race_id)
    dist_info = catalog.get_distance(race_id, distance_id)
    results_by_year: dict[int, RaceResult | None] = {}

    for year in years:
        data = catalog.load_results(race_id, year)
        if not data:
            results_by_year[year] = None
            continue

        dist_results = find_distance_results(data, dist_info)
        if not dist_results or not dist_results.results:
            results_by_year[year] = None
            continue

        found = search_by_name(dist_results.results, name)
        # Take first match (best match)
        results_by_year[year] = found[0] if found else None

    return results_by_year
