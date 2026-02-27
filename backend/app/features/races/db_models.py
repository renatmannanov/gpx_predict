"""SQLAlchemy models for race data.

Tables:
- races: Race definitions (alpine_race_kz, tengri_ultra_kz, etc.)
- race_editions: One year/edition of a race
- race_distances: Distance within an edition (Skyrunning, VK 1000, etc.)
- race_results: Individual participant results
- user_race_results: Links our users to their race results
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class Race(Base):
    """A race series (e.g. Alpine Race, Tengri Ultra)."""

    __tablename__ = "races"

    id = Column(String(64), primary_key=True)  # "alpine_race_kz"
    name = Column(String(255), nullable=False)  # "Alpine Race"
    name_aliases = Column(JSON, nullable=True)  # ["Alpine Race", "Almaty Alpine Race"]
    type = Column(String(64), nullable=True)  # "trail_sky"
    location = Column(String(255), nullable=True)  # "Шымбулак"
    created_at = Column(DateTime, default=datetime.utcnow)

    editions = relationship("RaceEdition", back_populates="race", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Race {self.id} '{self.name}'>"


class RaceEdition(Base):
    """One year/edition of a race."""

    __tablename__ = "race_editions"
    __table_args__ = (UniqueConstraint("race_id", "year", name="uq_race_edition_year"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(String(64), ForeignKey("races.id"), nullable=False)
    year = Column(Integer, nullable=False)
    date = Column(String(16), nullable=True)  # "2025-03-09"
    source_url = Column(String(512), nullable=True)
    parsed_at = Column(DateTime, nullable=True)

    race = relationship("Race", back_populates="editions")
    distances = relationship(
        "RaceDistance", back_populates="edition", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<RaceEdition {self.race_id} {self.year}>"


class RaceDistance(Base):
    """A distance within a race edition (e.g. Skyrunning, VK 1000)."""

    __tablename__ = "race_distances"
    __table_args__ = (
        UniqueConstraint("edition_id", "name", name="uq_race_distance_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    edition_id = Column(Integer, ForeignKey("race_editions.id"), nullable=False)
    name = Column(String(255), nullable=False)  # "Skyrunning"
    distance_km = Column(Float, nullable=True)
    elevation_gain_m = Column(Integer, nullable=True)

    edition = relationship("RaceEdition", back_populates="distances")
    results = relationship(
        "RaceResultDB", back_populates="distance", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<RaceDistance {self.name} ({self.distance_km} km)>"


class RaceResultDB(Base):
    """Individual participant result.

    Named RaceResultDB to avoid collision with the dataclass RaceResult
    used by the parser.
    """

    __tablename__ = "race_results"
    __table_args__ = (
        Index("ix_race_results_name", "name"),
        Index("ix_race_results_distance_id", "distance_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    distance_id = Column(Integer, ForeignKey("race_distances.id"), nullable=False)
    name = Column(String(255), nullable=False)  # "Iyemberdiyev Diyas"
    time_seconds = Column(Integer, nullable=False)
    place = Column(Integer, nullable=False)
    category = Column(String(32), nullable=True)  # "M_30-39"
    gender = Column(String(4), nullable=True)  # "M" / "F"
    club = Column(String(255), nullable=True)
    bib = Column(String(16), nullable=True)
    birth_year = Column(Integer, nullable=True)
    nationality = Column(String(8), nullable=True)  # "KAZ"
    over_time_limit = Column(Boolean, default=False)

    distance = relationship("RaceDistance", back_populates="results")
    user_links = relationship("UserRaceResult", back_populates="race_result")

    def __repr__(self):
        return f"<RaceResultDB #{self.place} {self.name} {self.time_seconds}s>"


class UserRaceResult(Base):
    """Links a platform user to their race result."""

    __tablename__ = "user_race_results"
    __table_args__ = (
        UniqueConstraint("user_id", "race_result_id", name="uq_user_race_result"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    race_result_id = Column(Integer, ForeignKey("race_results.id"), nullable=False)
    matched_by = Column(String(16), nullable=False)  # "auto" | "manual"
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="race_results")
    race_result = relationship("RaceResultDB", back_populates="user_links")

    def __repr__(self):
        return f"<UserRaceResult user={self.user_id} result={self.race_result_id}>"
