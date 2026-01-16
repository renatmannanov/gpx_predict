"""
Prediction Schemas

Pydantic models for prediction requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


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


class GroupRole(str, Enum):
    """Role in group by speed."""
    FAST = "fast"
    AVERAGE = "average"
    SLOW = "slow"


class WarningLevel(str, Enum):
    """Warning severity."""
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


# === Request Models ===

class HikePredictRequest(BaseModel):
    """Request for hike prediction."""
    gpx_id: str

    experience: ExperienceLevel = ExperienceLevel.CASUAL
    backpack: BackpackWeight = BackpackWeight.MEDIUM
    group_size: int = Field(default=1, ge=1, le=50)
    has_children: bool = False
    has_elderly: bool = False

    is_round_trip: bool = True
    sunrise: str = "06:00"
    sunset: str = "20:00"


class GroupMemberInput(BaseModel):
    """Input for a group member."""
    name: str
    experience: ExperienceLevel
    backpack: BackpackWeight
    has_children: bool = False


class GroupPredictRequest(BaseModel):
    """Request for group prediction."""
    gpx_id: str
    members: List[GroupMemberInput]
    is_round_trip: bool = True


# === Response Models ===

class Warning(BaseModel):
    """Warning in prediction."""
    level: WarningLevel
    code: str
    message: str


class SegmentPrediction(BaseModel):
    """Prediction for a route segment."""
    start_km: float
    end_km: float
    distance_km: float
    elevation_change_m: float
    gradient_percent: float
    predicted_minutes: float


class TimeBreakdown(BaseModel):
    """Breakdown of estimated time."""
    moving_time_hours: float
    rest_time_hours: float
    lunch_time_hours: float


class HikePrediction(BaseModel):
    """Response for hike prediction."""
    estimated_time_hours: float
    safe_time_hours: float
    recommended_start: str
    recommended_turnaround: Optional[str] = None

    # Time breakdown
    time_breakdown: Optional[TimeBreakdown] = None

    warnings: List[Warning] = []
    segments: List[SegmentPrediction] = []

    # Multipliers applied
    experience_multiplier: float = 1.0
    backpack_multiplier: float = 1.0
    group_multiplier: float = 1.0
    altitude_multiplier: float = 1.0
    total_multiplier: float = 1.0


class GroupMemberPrediction(BaseModel):
    """Prediction for a group member."""
    name: str
    individual_time_hours: float
    role: GroupRole


class MeetingPoint(BaseModel):
    """Suggested meeting point."""
    km: float
    name: str
    fast_group_arrival: str
    slow_group_arrival: str
    wait_time_minutes: int


class GroupPrediction(BaseModel):
    """Response for group prediction."""
    members: List[GroupMemberPrediction]
    group_time_hours: float
    spread_hours: float

    split_recommended: bool
    subgroups: Optional[List[List[str]]] = None

    recommendations: List[str] = []
    meeting_points: List[MeetingPoint] = []


# === Comparison Models (new) ===

class MethodResultSchema(BaseModel):
    """Result from a single calculation method."""
    method_name: str
    speed_kmh: float
    time_hours: float
    formula_used: str


class MacroSegmentSchema(BaseModel):
    """A major route segment (ascent/descent section)."""
    segment_number: int
    segment_type: str  # "ascent", "descent", "flat"
    distance_km: float
    elevation_change_m: float
    gradient_percent: float
    gradient_degrees: float
    start_elevation_m: float
    end_elevation_m: float

    # Results by method name
    methods: dict  # {"naismith": MethodResultSchema, "tobler": MethodResultSchema}


class RouteComparisonResponse(BaseModel):
    """Response for route comparison with multiple methods."""
    # Route summary
    total_distance_km: float
    total_ascent_m: float
    total_descent_m: float
    ascent_distance_km: float
    descent_distance_km: float
    max_elevation_m: float = 0

    # Segment breakdown
    segments: List[MacroSegmentSchema]

    # Totals by method (hours)
    totals: dict  # {"naismith": 8.2, "tobler": 5.7}

    # Rest/lunch time
    rest_time_hours: float = 0
    lunch_time_hours: float = 0

    # Method descriptions
    method_descriptions: dict  # {"naismith": "Naismith's Rule...", ...}

    # Sun times
    sunrise: Optional[str] = None  # HH:MM
    sunset: Optional[str] = None   # HH:MM

    # Formatted text output (for bot/debugging)
    formatted_text: Optional[str] = None
