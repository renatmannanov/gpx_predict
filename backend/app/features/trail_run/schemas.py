"""
Trail run prediction schemas.

Pydantic schemas for API request/response serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.shared.constants import DEFAULT_HIKE_THRESHOLD_PERCENT


class GAPMethod(str, Enum):
    """GAP calculation method."""
    STRAVA = "strava"
    MINETTI = "minetti"


class TrailRunRequest(BaseModel):
    """Request for trail run prediction."""
    gpx_id: str
    telegram_id: str
    flat_pace_min_km: float = 6.0
    gap_method: GAPMethod = GAPMethod.STRAVA
    enable_fatigue: bool = True
    uphill_threshold_percent: float = DEFAULT_HIKE_THRESHOLD_PERCENT


class TrailRunSegment(BaseModel):
    """Single segment result."""
    start_km: float
    end_km: float
    distance_km: float
    elevation_diff_m: float
    gradient_percent: float
    mode: str  # "run" or "hike"
    time_hours: float
    pace_min_km: float


class TrailRunPrediction(BaseModel):
    """Trail run prediction result."""
    estimated_time: float = Field(..., description="Time in hours")
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    run_distance_km: float
    hike_distance_km: float
    run_time_hours: float
    hike_time_hours: float
    gap_method: GAPMethod
    fatigue_applied: bool
    segments: Optional[List[TrailRunSegment]] = None
