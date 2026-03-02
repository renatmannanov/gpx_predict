"""Statistics and search for race results."""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

from .models import (
    CategoryDistribution,
    ClubStats,
    GenderDistribution,
    RaceResult,
    RaceStats,
    TimeBucket,
)

_FINISHED_STATUSES = ("finished", "over_time_limit")


def calculate_stats(results: Sequence[RaceResult], is_backyard: bool = False) -> RaceStats:
    """Calculate aggregate statistics for a list of race results.

    Args:
        results: All results including DNF/DNS. Finishers should be sorted by place.
        is_backyard: If True, longest time = best (Backyard Ultra format).

    Returns:
        RaceStats with percentiles, time distribution, and demographic breakdowns.
    """
    all_results = list(results)
    total_participants = len(all_results)
    dns_count = sum(1 for r in all_results if r.status == "dns")
    dnf_count = sum(1 for r in all_results if r.status == "dnf")

    # Only finishers for time-based stats
    finishers = [r for r in all_results if r.status in _FINISHED_STATUSES]

    if not finishers:
        return RaceStats(
            finishers=0,
            best_time_s=0,
            worst_time_s=0,
            median_time_s=0,
            p25_time_s=0,
            p75_time_s=0,
            total_participants=total_participants,
            dnf_count=dnf_count,
            dns_count=dns_count,
        )

    # For Backyard: finishers are already sorted longest→shortest (place 1 = longest)
    # times[0] = longest (best), times[-1] = shortest (worst)
    times = [r.time_seconds for r in finishers]
    n = len(times)

    return RaceStats(
        finishers=n,
        best_time_s=times[0],
        worst_time_s=times[-1],
        median_time_s=_percentile(times, 50),
        p25_time_s=_percentile(times, 25),
        p75_time_s=_percentile(times, 75),
        time_buckets=_build_buckets(times, reverse=is_backyard),
        # NOTE: percentile_buckets disabled — see _build_percentile_buckets comment below
        # percentile_buckets=_build_percentile_buckets(times),
        gender_distribution=_gender_distribution(finishers),
        category_distribution=_category_distribution(finishers),
        club_stats=_club_stats(finishers, is_backyard=is_backyard),
        total_participants=total_participants,
        dnf_count=dnf_count,
        dns_count=dns_count,
    )


def search_by_name(
    results: Sequence[RaceResult], query: str
) -> list[RaceResult]:
    """Search by name (case-insensitive, all query words must match).

    Searches both `name` (Latin) and `name_local` (Cyrillic) fields.
    Handles reversed name order: "Renat Mannanov" matches "Mannanov Renat".
    """
    query_words = query.lower().split()
    if not query_words:
        return []

    found = []
    for r in results:
        name_lower = r.name.lower()
        if all(w in name_lower for w in query_words):
            found.append(r)
        elif r.name_local:
            name_local_lower = r.name_local.lower()
            if all(w in name_local_lower for w in query_words):
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


def _build_buckets(times: list[int], reverse: bool = False) -> list[TimeBucket]:
    """Build ~5 time distribution buckets automatically.

    Strategy: divide into 5 equal-width buckets between best and worst time.
    For Backyard Ultra (reverse=True), times are sorted longest→shortest,
    so we sort ascending for bucket math then reverse bucket order for display.
    """
    if not times:
        return []

    # Always work with ascending times for bucket math
    asc = sorted(times)
    best = asc[0]
    worst = asc[-1]
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
        count = sum(1 for t in asc if b_min <= t < b_max)
        # Last bucket includes the worst time
        if i == n_buckets - 1:
            count = sum(1 for t in asc if t >= b_min)

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

    # For Backyard Ultra: reverse bucket order so "longest time" buckets come first
    if reverse:
        buckets = list(reversed(buckets))

    return buckets


# --- Percentile histogram: DISABLED ---
# BUG: Percentile buckets are a tautology. Dividing N finishers into percentile
# bands (0-10%, 10-25%, 25-50%, 50-75%, 75-100%) always produces the same
# proportional distribution (~10/15/25/25/25%) regardless of the race, because
# percentile IS defined by place, and place divides evenly by definition.
# The histogram showed identical charts for every race — meaningless.
#
# Options for future:
# 1. Time-based histogram (equal time bins) with percentile-colored bars
# 2. Percentile scale/legend showing time thresholds per level (no bar chart)
# 3. Remove entirely — percentiles already shown per-participant in the table
#
# See backlog #28 in step_5_6_bugs.md
#
# _PERCENTILE_LEVELS = [
#     ("top-10%", "elite", 0, 10),
#     ("top-25%", "good", 10, 25),
#     ("top-50%", "mid", 25, 50),
#     ("top-75%", "below", 50, 75),
#     ("остальные", "low", 75, 100),
# ]
#
# def _build_percentile_buckets(sorted_times: list[int]) -> list[PercentileBucket]:
#     ...
# --- End disabled block ---


def _gender_distribution(finishers: list[RaceResult]) -> list[GenderDistribution]:
    """Gender breakdown of finishers."""
    counts = Counter(r.gender for r in finishers if r.gender)
    total = sum(counts.values())
    if not total:
        return []
    return sorted(
        [
            GenderDistribution(
                gender=g, count=c, percent=round(c / total * 100, 1)
            )
            for g, c in counts.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )


def _category_distribution(finishers: list[RaceResult]) -> list[CategoryDistribution]:
    """Category breakdown of finishers."""
    counts = Counter(r.category for r in finishers if r.category)
    total = sum(counts.values())
    if not total:
        return []
    return sorted(
        [
            CategoryDistribution(
                category=cat, count=c, percent=round(c / total * 100, 1)
            )
            for cat, c in counts.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )


def _club_stats(finishers: list[RaceResult], is_backyard: bool = False) -> list[ClubStats]:
    """Club performance stats. Minimum 2 finishers per club."""
    by_club: dict[str, list[RaceResult]] = {}
    for r in finishers:
        if r.club:
            by_club.setdefault(r.club, []).append(r)

    n_total = len(finishers)
    result = []
    for club, members in by_club.items():
        if len(members) < 2:
            continue
        # Backyard: best = longest time (max), standard: best = shortest time (min)
        best = max(m.time_seconds for m in members) if is_backyard else min(m.time_seconds for m in members)
        avg_pct = sum(
            _rank_percentile(m.place, n_total) for m in members
        ) / len(members)
        result.append(
            ClubStats(
                club=club,
                count=len(members),
                best_time_s=best,
                best_time=format_time(best),
                avg_percentile=round(avg_pct, 1),
            )
        )

    return sorted(result, key=lambda x: x.avg_percentile)


def _rank_percentile(place: int, total: int) -> float:
    """Convert place to percentile (0=best, 100=worst)."""
    if total <= 1:
        return 0.0
    return round((place - 1) / (total - 1) * 100, 1)
