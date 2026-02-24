"""Statistics and search for race results."""

from __future__ import annotations

import math
from typing import Sequence

from .models import RaceResult, RaceStats, TimeBucket


def calculate_stats(results: Sequence[RaceResult]) -> RaceStats:
    """Calculate aggregate statistics for a list of race results.

    Args:
        results: Sorted by time (place order).

    Returns:
        RaceStats with percentiles and time distribution buckets.
    """
    if not results:
        return RaceStats(
            finishers=0,
            best_time_s=0,
            worst_time_s=0,
            median_time_s=0,
            p25_time_s=0,
            p75_time_s=0,
        )

    times = [r.time_seconds for r in results]
    n = len(times)

    return RaceStats(
        finishers=n,
        best_time_s=times[0],
        worst_time_s=times[-1],
        median_time_s=_percentile(times, 50),
        p25_time_s=_percentile(times, 25),
        p75_time_s=_percentile(times, 75),
        time_buckets=_build_buckets(times),
    )


def search_by_name(
    results: Sequence[RaceResult], query: str
) -> list[RaceResult]:
    """Fuzzy search by name (case-insensitive, partial match).

    Searches both `name` (Latin) and `name_local` (Cyrillic) fields.
    """
    query_lower = query.lower()
    found = []
    for r in results:
        if query_lower in r.name.lower():
            found.append(r)
        elif r.name_local and query_lower in r.name_local.lower():
            found.append(r)
    return found


def get_percentile(
    results: Sequence[RaceResult], time_seconds: int
) -> float:
    """What percentile a given time falls in (0 = best, 100 = worst).

    Returns the percentage of finishers that are slower than this time.
    Lower percentile = better result (top-10% means faster than 90%).
    """
    if not results:
        return 0.0
    faster = sum(1 for r in results if r.time_seconds < time_seconds)
    return round(faster / len(results) * 100, 1)


def format_time(seconds: int) -> str:
    """Format seconds as human-readable time string.

    553   → "9:13"
    3125  → "52:05"
    3760  → "1:02:40"
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _percentile(sorted_values: list[int], pct: int) -> int:
    """Get percentile value from sorted list."""
    n = len(sorted_values)
    if n == 0:
        return 0
    idx = (pct / 100) * (n - 1)
    lower = int(math.floor(idx))
    upper = min(lower + 1, n - 1)
    weight = idx - lower
    return int(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight)


def _build_buckets(times: list[int]) -> list[TimeBucket]:
    """Build ~5 time distribution buckets automatically.

    Strategy: divide into 5 equal-width buckets between best and worst time.
    """
    if not times:
        return []

    best = times[0]
    worst = times[-1]
    span = worst - best

    if span == 0:
        return [
            TimeBucket(
                label=format_time(best),
                min_s=best,
                max_s=worst,
                count=len(times),
                percent=100.0,
            )
        ]

    n_buckets = 5
    bucket_width = span / n_buckets
    n_total = len(times)

    buckets: list[TimeBucket] = []
    for i in range(n_buckets):
        b_min = best + int(i * bucket_width)
        b_max = best + int((i + 1) * bucket_width) if i < n_buckets - 1 else worst + 1
        count = sum(1 for t in times if b_min <= t < b_max)
        # Last bucket includes the worst time
        if i == n_buckets - 1:
            count = sum(1 for t in times if t >= b_min)

        label = f"{format_time(b_min)} - {format_time(b_max - 1)}"
        if i == 0:
            label = f"< {format_time(b_max)}"
        elif i == n_buckets - 1:
            label = f"> {format_time(b_min)}"

        buckets.append(
            TimeBucket(
                label=label,
                min_s=b_min,
                max_s=b_max,
                count=count,
                percent=round(count / n_total * 100, 1) if n_total else 0,
            )
        )

    return buckets
