"""
GPX file handling module.

Usage:
    from app.features.gpx import GPXFile, GPXParserService, GPXRepository

Components:
- GPXFile: SQLAlchemy model for stored GPX files
- GPXParserService: Parse GPX files, extract points and metadata
- GPXRepository: CRUD operations for GPX files
- GPXInfo: Pydantic schema for GPX metadata
"""

from .models import GPXFile
from .parser import GPXParserService, GPXSegment
from .repository import GPXRepository
from .schemas import GPXInfo, GPXPoint, GPXUploadResponse

__all__ = [
    # Model
    "GPXFile",
    # Services
    "GPXParserService",
    "GPXSegment",
    "GPXRepository",
    # Schemas
    "GPXInfo",
    "GPXPoint",
    "GPXUploadResponse",
]
