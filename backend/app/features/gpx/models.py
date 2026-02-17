"""
GPX file model.

Stores uploaded GPX files and their metadata.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, Text, LargeBinary
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base


class GPXFile(Base):
    """
    Model for storing GPX file information.

    Stores both the raw GPX content and extracted metadata
    for quick access without re-parsing.
    """

    __tablename__ = "gpx_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # File info
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)  # Local storage path (not used)
    file_size = Column(Integer, nullable=True)
    gpx_content = Column(LargeBinary, nullable=True)  # Raw GPX file content

    # Route metadata (extracted from GPX)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Calculated metrics
    distance_km = Column(Float, nullable=True)
    elevation_gain_m = Column(Float, nullable=True)
    elevation_loss_m = Column(Float, nullable=True)
    max_elevation_m = Column(Float, nullable=True)
    min_elevation_m = Column(Float, nullable=True)

    # Start/end coordinates
    start_lat = Column(Float, nullable=True)
    start_lon = Column(Float, nullable=True)
    end_lat = Column(Float, nullable=True)
    end_lon = Column(Float, nullable=True)

    # Owner
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    predictions = relationship("Prediction", back_populates="gpx_file")

    def __repr__(self):
        return f"<GPXFile {self.id} ({self.filename})>"
