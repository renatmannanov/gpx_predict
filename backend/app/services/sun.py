"""
Sun Times Service

Calculate sunrise and sunset times based on location.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from astral import LocationInfo
from astral.sun import sun

logger = logging.getLogger(__name__)


@dataclass
class SunTimes:
    """Sunrise and sunset times."""
    sunrise: str  # HH:MM format
    sunset: str   # HH:MM format
    daylight_hours: float


def get_sun_times(
    lat: float,
    lon: float,
    date_: Optional[date] = None
) -> SunTimes:
    """
    Calculate sunrise and sunset times for a location.

    Args:
        lat: Latitude
        lon: Longitude
        date_: Date for calculation (defaults to today)

    Returns:
        SunTimes with sunrise/sunset in HH:MM format
    """
    if date_ is None:
        date_ = date.today()

    # Create location without timezone (astral handles UTC)
    location = LocationInfo(
        name="Route",
        region="",
        timezone="UTC",
        latitude=lat,
        longitude=lon
    )

    try:
        s = sun(location.observer, date=date_)

        sunrise_utc = s["sunrise"]
        sunset_utc = s["sunset"]

        # Convert to local time estimate
        # For Kazakhstan (Almaty) UTC+5, adjust manually
        # In production, use proper timezone from coordinates
        utc_offset_hours = _estimate_utc_offset(lon)

        sunrise_local = sunrise_utc.hour + utc_offset_hours
        sunset_local = sunset_utc.hour + utc_offset_hours

        # Handle day wraparound
        sunrise_local = sunrise_local % 24
        sunset_local = sunset_local % 24

        sunrise_str = f"{int(sunrise_local):02d}:{sunrise_utc.minute:02d}"
        sunset_str = f"{int(sunset_local):02d}:{sunset_utc.minute:02d}"

        # Calculate daylight hours
        daylight = (sunset_utc - sunrise_utc).total_seconds() / 3600

        return SunTimes(
            sunrise=sunrise_str,
            sunset=sunset_str,
            daylight_hours=round(daylight, 1)
        )

    except Exception as e:
        logger.warning(f"Failed to calculate sun times: {e}")
        # Return reasonable defaults for Kazakhstan
        return SunTimes(
            sunrise="06:00",
            sunset="20:00",
            daylight_hours=14.0
        )


def _estimate_utc_offset(longitude: float) -> int:
    """
    Estimate UTC offset from longitude.

    Simple approximation: 15 degrees per hour.
    """
    return round(longitude / 15)
