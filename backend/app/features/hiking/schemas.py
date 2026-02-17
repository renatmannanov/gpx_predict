"""
Hiking prediction schemas.

Pydantic models for API request/response.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class HikePredictRequest(BaseModel):
    """Request for hiking prediction."""
    gpx_id: str
    telegram_id: str
    experience: str = "intermediate"
    backpack: str = "light"
    group_size: int = 1
    altitude_acclimatized: bool = False
    start_time: Optional[datetime] = None


class HikeSegment(BaseModel):
    """Single segment of a hiking route."""
    start_km: float
    end_km: float
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    gradient_percent: float
    time_hours: float


class HikePrediction(BaseModel):
    """Hiking time prediction result."""
    estimated_time: float = Field(..., description="Time in hours")
    safe_time: float = Field(..., description="Time with safety margin")
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    method: str = "tobler"
    personalized: bool = False
    segments: Optional[List[HikeSegment]] = None
    warnings: List[str] = []


class MethodComparison(BaseModel):
    """Comparison of different calculation methods."""
    tobler: float
    naismith: float
    tobler_personalized: Optional[float] = None
    naismith_personalized: Optional[float] = None
    recommended: str
    personalized: bool = False
