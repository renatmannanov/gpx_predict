"""
Prediction Schemas

Pydantic models for prediction requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class ActivityType(str, Enum):
    """Type of activity for prediction."""
    HIKE = "hike"
    TRAIL_RUN = "trail_run"


class GAPModeEnum(str, Enum):
    """GAP calculation mode for trail running."""
    STRAVA = "strava_gap"
    MINETTI = "minetti_gap"
    STRAVA_MINETTI = "strava_minetti_gap"


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

    # Optional: for personalized predictions
    telegram_id: Optional[str] = None


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

    # Personalization info
    personalized: bool = False
    activities_used: int = 0


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
    # Can include: naismith, tobler, naismith_personalized, tobler_personalized
    totals: dict

    # Rest/lunch time
    rest_time_hours: float = 0
    lunch_time_hours: float = 0

    # Method descriptions
    method_descriptions: dict

    # Sun times
    sunrise: Optional[str] = None  # HH:MM
    sunset: Optional[str] = None   # HH:MM

    # Formatted text output (for bot/debugging)
    formatted_text: Optional[str] = None

    # Personalization info
    personalized: bool = False
    activities_used: int = 0

    # Fatigue model info
    fatigue_applied: bool = False
    fatigue_info: Optional[dict] = None


# === Trail Run Models ===

class TrailRunCompareRequest(BaseModel):
    """Request for trail run method comparison."""
    gpx_id: str
    telegram_id: Optional[str] = None

    # Activity type
    activity_type: ActivityType = ActivityType.TRAIL_RUN

    # GAP mode
    gap_mode: GAPModeEnum = GAPModeEnum.STRAVA

    # Manual flat pace (if no Strava profile)
    flat_pace_min_km: Optional[float] = Field(
        default=None,
        ge=2.5,
        le=15.0,
        description="Base flat pace in min/km (default 6:00/km if not provided)"
    )

    # Threshold options
    apply_dynamic_threshold: bool = False
    walk_threshold_override: Optional[float] = Field(
        default=None,
        ge=10.0,
        le=40.0,
        description="Manual override for walk threshold (%)"
    )

    # Fatigue
    apply_fatigue: bool = False

    # Extended gradients
    use_extended_gradients: bool = True


class SegmentMovementInfo(BaseModel):
    """Movement info for a segment (trail run only)."""
    mode: str              # "run" | "hike"
    reason: str
    threshold_used: float
    confidence: float


class TrailRunSegmentSchema(BaseModel):
    """Segment prediction for trail running."""
    segment_number: int
    start_km: float
    end_km: float
    distance_km: float
    elevation_change_m: float
    gradient_percent: float

    # Movement mode
    movement: SegmentMovementInfo

    # Time predictions by method
    times: Dict[str, float]  # method_name → time_hours

    # Fatigue info
    fatigue_multiplier: float = 1.0


class TrailRunSummarySchema(BaseModel):
    """Summary statistics for trail run prediction."""
    total_distance_km: float
    total_elevation_gain_m: float
    total_elevation_loss_m: float

    # Time breakdown
    running_time_hours: float
    hiking_time_hours: float
    running_distance_km: float
    hiking_distance_km: float

    # Flat equivalent
    flat_equivalent_hours: float
    elevation_impact_percent: float


class TrailRunCompareResponse(BaseModel):
    """Response for trail run comparison."""
    # Activity type
    activity_type: str = "trail_run"

    # Segment breakdown
    segments: List[TrailRunSegmentSchema]

    # Totals by method (hours)
    totals: Dict[str, float]

    # Summary
    summary: TrailRunSummarySchema

    # Personalization info
    personalized: bool = False
    total_activities_used: int = 0
    hike_activities_used: int = 0
    run_activities_used: int = 0

    # Threshold info
    walk_threshold_used: float = 25.0
    dynamic_threshold_applied: bool = False

    # GAP mode used
    gap_mode: str = "strava_gap"

    # Fatigue model info
    fatigue_applied: bool = False
    fatigue_info: Optional[Dict] = None

    # Formatted text output (for bot/debugging)
    formatted_text: Optional[str] = None
