"""
Formatters for bot display.

Single source of truth - DO NOT duplicate in handlers!
"""


def format_time(hours: float) -> str:
    """
    Format hours as 'Xч Yмин'.

    Args:
        hours: Time in hours (e.g., 2.5)

    Returns:
        Formatted string (e.g., '2ч 30мин')
    """
    if hours < 0:
        return "—"

    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60

    if h == 0:
        return f"{m}мин"
    elif m == 0:
        return f"{h}ч"
    else:
        return f"{h}ч {m:02d}мин"


def format_pace(pace_min_km: float | None) -> str:
    """
    Format pace as 'M:SS мин/км'.

    Args:
        pace_min_km: Pace in minutes per km (e.g., 6.5)

    Returns:
        Formatted string (e.g., '6:30 мин/км')
    """
    if pace_min_km is None:
        return "—"

    minutes = int(pace_min_km)
    seconds = int((pace_min_km - minutes) * 60)

    return f"{minutes}:{seconds:02d}"


def format_distance(km: float) -> str:
    """
    Format distance in km.

    Args:
        km: Distance in kilometers

    Returns:
        Formatted string (e.g., '12.5 км')
    """
    if km < 1:
        return f"{int(km * 1000)} м"
    return f"{km:.1f} км"


def format_elevation(meters: float) -> str:
    """
    Format elevation in meters.

    Args:
        meters: Elevation in meters

    Returns:
        Formatted string (e.g., '+850 м' or '-120 м')
    """
    if meters >= 0:
        return f"+{int(meters)} м"
    return f"{int(meters)} м"
