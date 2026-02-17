"""
Trail running prediction module.

Usage:
    from app.features.trail_run import TrailRunService, UserRunProfile
    from app.features.trail_run.calculators import GAPCalculator

Components:
- TrailRunService: Main prediction service
- GAPCalculator: Grade Adjusted Pace
- HikeRunThresholdService: Run vs walk detection
- RunnerFatigueService: Fatigue modeling
"""

from .models import UserRunProfile
from .schemas import TrailRunRequest, TrailRunPrediction, GAPMethod
from .service import TrailRunService, TrailRunResult, TrailRunSummary, SegmentResult
from .repository import TrailRunProfileRepository

__all__ = [
    # Models
    "UserRunProfile",
    # Schemas
    "TrailRunRequest",
    "TrailRunPrediction",
    "GAPMethod",
    # Service
    "TrailRunService",
    "TrailRunResult",
    "TrailRunSummary",
    "SegmentResult",
    # Repository
    "TrailRunProfileRepository",
]
