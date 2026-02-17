"""
Bot formatters - re-export from shared with bot-specific adjustments.

Single source of truth is backend/app/shared/formatters.py.
Bot overrides only what needs different format for compact display.
"""

import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Import from shared (single source of truth)
from app.shared.formatters import (
    format_time_hours,
    format_distance_km,
    format_elevation,
)

# Re-export with bot naming conventions
format_time = format_time_hours
format_distance = format_distance_km

# Note: format_elevation is the same, just re-export
__all__ = ["format_time", "format_pace", "format_distance", "format_elevation"]


def format_pace(pace_min_km: float | None) -> str:
    """
    Format pace as 'M:SS' (without 'мин/км' suffix for compact display).

    This is a bot-specific override. Backend version includes the suffix.

    Args:
        pace_min_km: Pace in minutes per km (e.g., 6.5)

    Returns:
        Formatted string (e.g., '6:30')
    """
    if pace_min_km is None:
        return "—"

    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)

    return f"{minutes}:{seconds:02d}"
