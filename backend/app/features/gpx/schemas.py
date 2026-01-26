"""
GPX-related schemas.

Pydantic models for GPX file operations.
"""

from pydantic import BaseModel
from typing import Optional


class GPXInfo(BaseModel):
    """GPX file metadata."""

    filename: str
    name: Optional[str] = None
    description: Optional[str] = None

    # Metrics
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_elevation_m: float
    min_elevation_m: float

    # Coordinates
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None

    # Points count
    points_count: int = 0

    # Route type
    is_loop: bool = False  # True if start and end points are close (< 500m)


class GPXUploadResponse(BaseModel):
    """Response for GPX upload."""

    success: bool
    gpx_id: str
    info: GPXInfo


class GPXPoint(BaseModel):
    """Single point in GPX track."""

    lat: float
    lon: float
    elevation: float
