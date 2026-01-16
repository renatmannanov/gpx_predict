"""
GPX Repository

Data access layer for GPX files.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.gpx import GPXFile
from app.schemas.gpx import GPXInfo


class GPXRepository:
    """Repository for GPX file operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        filename: str,
        content: bytes,
        info: GPXInfo
    ) -> GPXFile:
        """
        Create a new GPX file record.

        Args:
            filename: Original filename
            content: Raw GPX file content
            info: Parsed GPX metadata

        Returns:
            Created GPXFile model
        """
        gpx_file = GPXFile(
            filename=filename,
            file_size=len(content),
            gpx_content=content,
            name=info.name,
            description=info.description,
            distance_km=info.distance_km,
            elevation_gain_m=info.elevation_gain_m,
            elevation_loss_m=info.elevation_loss_m,
            max_elevation_m=info.max_elevation_m,
            min_elevation_m=info.min_elevation_m,
            start_lat=info.start_lat,
            start_lon=info.start_lon,
            end_lat=info.end_lat,
            end_lon=info.end_lon,
        )

        self.db.add(gpx_file)
        self.db.commit()
        self.db.refresh(gpx_file)

        return gpx_file

    def get_by_id(self, gpx_id: str) -> Optional[GPXFile]:
        """
        Get GPX file by ID.

        Args:
            gpx_id: UUID of the GPX file

        Returns:
            GPXFile if found, None otherwise
        """
        return self.db.query(GPXFile).filter(GPXFile.id == gpx_id).first()

    def to_info(self, gpx_file: GPXFile) -> GPXInfo:
        """
        Convert GPXFile model to GPXInfo schema.

        Args:
            gpx_file: GPXFile model

        Returns:
            GPXInfo schema
        """
        return GPXInfo(
            filename=gpx_file.filename,
            name=gpx_file.name,
            description=gpx_file.description,
            distance_km=gpx_file.distance_km or 0,
            elevation_gain_m=gpx_file.elevation_gain_m or 0,
            elevation_loss_m=gpx_file.elevation_loss_m or 0,
            max_elevation_m=gpx_file.max_elevation_m or 0,
            min_elevation_m=gpx_file.min_elevation_m or 0,
            start_lat=gpx_file.start_lat,
            start_lon=gpx_file.start_lon,
            end_lat=gpx_file.end_lat,
            end_lon=gpx_file.end_lon,
            points_count=0,  # Not stored in DB
        )
