"""
Prediction Model

Stores prediction results and input parameters.
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, JSON, Enum as SQLEnum
import uuid

from app.models.base import Base
from sqlalchemy.orm import relationship


class PredictionType(str, Enum):
    """Type of prediction."""
    HIKE = "hike"
    RUN = "run"


class ExperienceLevel(str, Enum):
    """Hiker experience level."""
    BEGINNER = "beginner"
    CASUAL = "casual"
    REGULAR = "regular"
    EXPERIENCED = "experienced"


class BackpackWeight(str, Enum):
    """Backpack weight category."""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class Prediction(Base):
    """Model for storing prediction results."""

    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Type
    prediction_type = Column(SQLEnum(PredictionType), default=PredictionType.HIKE)

    # Input: GPX
    gpx_file_id = Column(String(36), ForeignKey("gpx_files.id"), nullable=True)

    # Input: Hiker profile
    experience = Column(SQLEnum(ExperienceLevel), nullable=True)
    backpack = Column(SQLEnum(BackpackWeight), nullable=True)
    group_size = Column(Integer, default=1)
    has_children = Column(Integer, default=0)  # Boolean as int
    has_elderly = Column(Integer, default=0)

    # Input: Runner profile (for future)
    known_time_seconds = Column(Integer, nullable=True)  # e.g., 10K time
    known_distance_km = Column(Float, nullable=True)

    # Output: Prediction results
    estimated_time_hours = Column(Float, nullable=True)
    safe_time_hours = Column(Float, nullable=True)
    recommended_start = Column(String(10), nullable=True)

    # Detailed breakdown (JSON)
    segments = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)

    # User
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Actual result (for accuracy tracking)
    actual_time_hours = Column(Float, nullable=True)
    accuracy_percent = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    gpx_file = relationship("GPXFile", back_populates="predictions")

    def __repr__(self):
        return f"<Prediction {self.id} ({self.prediction_type})>"
