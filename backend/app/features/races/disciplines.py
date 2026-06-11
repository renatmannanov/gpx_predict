"""Distance discipline detection.

Race results include non-running disciplines (bike, ski-alp, splitboard).
Until a proper discipline field exists in the DB, detect them by distance name.
Single source of truth for API routes (hide distances) and repository
(exclude from finisher counts).
"""

from sqlalchemy import func, not_, or_

NON_RUNNING_KEYWORDS = [
    "ski ", "ski-", "ски-альп", "splitboard", "skitour",
    "bike", "mtb", "velo", "gravel",
]


def is_running_distance(name: str) -> bool:
    """Return False for non-running disciplines (bike, ski, etc.)."""
    lower = name.lower()
    return not any(kw in lower for kw in NON_RUNNING_KEYWORDS)


def running_distance_filter(name_column):
    """SQLAlchemy condition: distance name is a running discipline."""
    return not_(
        or_(*[func.lower(name_column).like(f"%{kw}%") for kw in NON_RUNNING_KEYWORDS])
    )
