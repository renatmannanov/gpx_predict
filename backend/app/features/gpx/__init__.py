"""
GPX file handling module.

Usage:
    from app.features.gpx import GPXFile, GPXParserService, GPXRepository
    from app.features.gpx import RouteSegmenter  # For route segmentation

Components:
- GPXFile: SQLAlchemy model for stored GPX files
- GPXParserService: Parse GPX files, extract points and metadata
- GPXRepository: CRUD operations for GPX files
- RouteSegmenter: Segment route by gradient direction (for calculators)
- GPXInfo: Pydantic schema for GPX metadata
"""

from .models import GPXFile
from .parser import GPXParserService, GPXSegment
from .segmenter import RouteSegmenter
from .repository import GPXRepository
from .schemas import GPXInfo, GPXPoint, GPXUploadResponse

__all__ = [
    # Model
    "GPXFile",
    # Services
    "GPXParserService",
    "GPXSegment",
    "RouteSegmenter",
    "GPXRepository",
    # Schemas
    "GPXInfo",
    "GPXPoint",
    "GPXUploadResponse",
]
