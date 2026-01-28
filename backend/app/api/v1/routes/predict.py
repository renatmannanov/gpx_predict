"""
Prediction Routes

Endpoints for time predictions.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_async_db
from app.schemas.prediction import (
    HikePredictRequest,
    HikePrediction,
    GroupPredictRequest,
    GroupPrediction,
    RouteComparisonResponse,
    MacroSegmentSchema,
    ExperienceLevel,
    BackpackWeight,
    TrailRunCompareRequest,
    TrailRunCompareResponse,
    TrailRunSegmentSchema,
    TrailRunSummarySchema,
    SegmentMovementInfo,
    GAPModeEnum,
)
from app.services.prediction import PredictionService
from app.services.calculators import ComparisonService
from app.features.trail_run import TrailRunService
from app.features.trail_run.calculators import GAPMode
from app.repositories.gpx import GPXRepository
from app.services.gpx_parser import GPXParserService
from app.services.naismith import get_total_multiplier, estimate_rest_time, HikerProfile
from app.services.sun import get_sun_times
from app.features.users import UserRepository
from app.features.hiking import HikingProfileRepository
from app.features.trail_run import TrailRunProfileRepository

router = APIRouter()


class CompareRequest(BaseModel):
    """Request for method comparison."""
    gpx_id: str
    experience: ExperienceLevel = ExperienceLevel.REGULAR
    backpack: BackpackWeight = BackpackWeight.LIGHT
    group_size: int = Field(default=1, ge=1, le=50)
    telegram_id: Optional[str] = None  # For personalization
    # Extended gradient system (7 categories vs legacy 3)
    use_extended_gradients: bool = False
    # Fatigue modeling (slowdown on long hikes)
    apply_fatigue: bool = False


@router.post("/hike", response_model=HikePrediction)
async def predict_hike(
    request: HikePredictRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Predict hiking time for a route.

    Uses Naismith's rule with profile-based adjustments.
    If telegram_id is provided, uses personalized data from Strava history.
    """
    # Load user profile if telegram_id provided
    user_profile = None
    if request.telegram_id:
        user_repo = UserRepository(db)
        hiking_repo = HikingProfileRepository(db)

        user = await user_repo.get_by_telegram_id(request.telegram_id)
        if user:
            user_profile = await hiking_repo.get_by_user_id(user.id)

    try:
        prediction = PredictionService.predict_hike(
            gpx_id=request.gpx_id,
            experience=request.experience,
            backpack=request.backpack,
            group_size=request.group_size,
            has_children=request.has_children,
            has_elderly=request.has_elderly,
            is_round_trip=request.is_round_trip,
            db=db,
            user_profile=user_profile
        )
        return prediction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group", response_model=GroupPrediction)
async def predict_group(
    request: GroupPredictRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Predict hiking time for a group.

    Analyzes each member and provides recommendations
    for splitting, meeting points, etc.
    """
    try:
        prediction = PredictionService.predict_group(
            gpx_id=request.gpx_id,
            members=request.members,
            is_round_trip=request.is_round_trip,
            db=db
        )
        return prediction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compare", response_model=RouteComparisonResponse)
async def compare_methods(
    request: CompareRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Compare different prediction methods on a route.

    Returns segment-by-segment breakdown with Naismith and Tobler calculations.
    If telegram_id is provided and user has a profile, includes personalized methods.
    """
    # Get GPX file
    gpx_repo = GPXRepository(db)
    gpx_file = await gpx_repo.get_by_id(request.gpx_id)

    if not gpx_file:
        raise HTTPException(status_code=404, detail=f"GPX file not found: {request.gpx_id}")

    if not gpx_file.gpx_content:
        raise HTTPException(status_code=400, detail="GPX file has no content")

    # Load user profile if telegram_id provided
    user_profile = None
    if request.telegram_id:
        user_repo = UserRepository(db)
        hiking_repo = HikingProfileRepository(db)

        user = await user_repo.get_by_telegram_id(request.telegram_id)
        if user:
            user_profile = await hiking_repo.get_by_user_id(user.id)

    # Extract points
    try:
        points = GPXParserService.extract_points(gpx_file.gpx_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse GPX: {e}")

    # Calculate profile multiplier
    profile = HikerProfile(
        experience=request.experience,
        backpack=request.backpack,
        group_size=request.group_size,
        max_altitude_m=gpx_file.max_elevation_m or 0
    )
    multiplier = get_total_multiplier(profile)

    # Run comparison with optional personalization and fatigue
    comparison_service = ComparisonService()
    comparison = comparison_service.compare_route(
        points,
        multiplier,
        user_profile=user_profile,
        use_extended_gradients=request.use_extended_gradients,
        apply_fatigue=request.apply_fatigue
    )

    # Format as text
    formatted = comparison_service.format_comparison(comparison)

    # Convert to response schema
    segments = []
    for seg in comparison.segments:
        methods_dict = {}
        for method_name, result in seg.methods.items():
            methods_dict[method_name] = {
                "method_name": result.method_name,
                "speed_kmh": result.speed_kmh,
                "time_hours": result.time_hours,
                "formula_used": result.formula_used
            }

        segments.append(MacroSegmentSchema(
            segment_number=seg.segment_number,
            segment_type=seg.segment_type,
            distance_km=seg.distance_km,
            elevation_change_m=seg.elevation_change_m,
            gradient_percent=seg.gradient_percent,
            gradient_degrees=seg.gradient_degrees,
            start_elevation_m=seg.start_elevation_m,
            end_elevation_m=seg.end_elevation_m,
            methods=methods_dict
        ))

    # Get sun times
    sunrise = None
    sunset = None
    if gpx_file.start_lat and gpx_file.start_lon:
        sun_times = get_sun_times(gpx_file.start_lat, gpx_file.start_lon)
        sunrise = sun_times.sunrise
        sunset = sun_times.sunset

    # Calculate rest/lunch time based on Tobler estimate
    tobler_hours = comparison.totals.get("tobler", 0)
    rest_time = estimate_rest_time(tobler_hours, request.experience)
    lunch_time = 0.5 if tobler_hours > 4 else 0.0

    return RouteComparisonResponse(
        total_distance_km=comparison.total_distance_km,
        total_ascent_m=comparison.total_ascent_m,
        total_descent_m=comparison.total_descent_m,
        ascent_distance_km=comparison.ascent_distance_km,
        descent_distance_km=comparison.descent_distance_km,
        max_elevation_m=gpx_file.max_elevation_m or 0,
        segments=segments,
        totals=comparison.totals,
        rest_time_hours=rest_time,
        lunch_time_hours=lunch_time,
        method_descriptions=comparison.method_descriptions,
        sunrise=sunrise,
        sunset=sunset,
        formatted_text=formatted,
        personalized=comparison.personalized,
        activities_used=comparison.activities_used,
        fatigue_applied=comparison.fatigue_applied,
        fatigue_info=comparison.fatigue_info if comparison.fatigue_applied else None
    )


@router.post("/trail-run/compare", response_model=TrailRunCompareResponse)
async def compare_trail_run_methods(
    request: TrailRunCompareRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Compare trail running prediction methods on a route.

    Trail running uses different methods than hiking:
    - GAP (Grade Adjusted Pace) for running segments
    - Tobler for hiking segments (steep uphills/technical terrain)
    - Automatic run/hike threshold detection
    - Runner-specific fatigue model (earlier onset, downhill penalty)

    If telegram_id is provided and user has profiles:
    - Run profile: personalized running paces
    - Hike profile: personalized hiking paces (for walking segments)
    """
    # Get GPX file
    gpx_repo = GPXRepository(db)
    gpx_file = await gpx_repo.get_by_id(request.gpx_id)

    if not gpx_file:
        raise HTTPException(status_code=404, detail=f"GPX file not found: {request.gpx_id}")

    if not gpx_file.gpx_content:
        raise HTTPException(status_code=400, detail="GPX file has no content")

    # Load user profiles if telegram_id provided
    hike_profile = None
    run_profile = None

    if request.telegram_id:
        user_repo = UserRepository(db)
        hiking_repo = HikingProfileRepository(db)
        run_repo = TrailRunProfileRepository(db)

        user = await user_repo.get_by_telegram_id(request.telegram_id)
        if user:
            hike_profile = await hiking_repo.get_by_user_id(user.id)
            run_profile = await run_repo.get_by_user_id(user.id)

    # Extract points
    try:
        points = GPXParserService.extract_points(gpx_file.gpx_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse GPX: {e}")

    # Determine flat pace
    flat_pace = request.flat_pace_min_km
    if flat_pace is None:
        if run_profile and run_profile.avg_flat_pace_min_km:
            flat_pace = run_profile.avg_flat_pace_min_km
        else:
            flat_pace = 6.0  # Default 10 km/h

    # Map GAP mode enum
    gap_mode = GAPMode.STRAVA if request.gap_mode == GAPModeEnum.STRAVA else GAPMode.MINETTI

    # Create trail run service
    service = TrailRunService(
        gap_mode=gap_mode,
        flat_pace_min_km=flat_pace,
        hike_profile=hike_profile,
        run_profile=run_profile,
        apply_fatigue=request.apply_fatigue,
        apply_dynamic_threshold=request.apply_dynamic_threshold,
        walk_threshold_override=request.walk_threshold_override,
        use_extended_gradients=request.use_extended_gradients,
    )

    # Calculate
    result = service.calculate_route(points)

    # Convert segments to response schema
    segments = []
    for seg_result in result.segments:
        segments.append(TrailRunSegmentSchema(
            segment_number=seg_result.segment.segment_number,
            start_km=0,  # Not tracked in MacroSegment
            end_km=0,
            distance_km=round(seg_result.segment.distance_km, 2),
            elevation_change_m=round(seg_result.segment.elevation_change_m, 0),
            gradient_percent=round(seg_result.segment.gradient_percent, 1),
            movement=SegmentMovementInfo(
                mode=seg_result.movement.mode.value,
                reason=seg_result.movement.reason,
                threshold_used=seg_result.movement.threshold_used,
                confidence=seg_result.movement.confidence,
            ),
            times=seg_result.times,
            fatigue_multiplier=round(seg_result.fatigue_multiplier, 3),
        ))

    # Build summary
    summary = TrailRunSummarySchema(
        total_distance_km=result.summary.total_distance_km,
        total_elevation_gain_m=result.summary.total_elevation_gain_m,
        total_elevation_loss_m=result.summary.total_elevation_loss_m,
        running_time_hours=result.summary.running_time_hours,
        hiking_time_hours=result.summary.hiking_time_hours,
        running_distance_km=result.summary.running_distance_km,
        hiking_distance_km=result.summary.hiking_distance_km,
        flat_equivalent_hours=result.summary.flat_equivalent_hours,
        elevation_impact_percent=result.summary.elevation_impact_percent,
    )

    # Format as text for bot
    formatted = _format_trail_run_result(result, flat_pace)

    return TrailRunCompareResponse(
        activity_type="trail_run",
        segments=segments,
        totals=result.totals,
        summary=summary,
        personalized=result.personalized,
        total_activities_used=result.total_activities_used,
        hike_activities_used=result.hike_activities_used,
        run_activities_used=result.run_activities_used,
        walk_threshold_used=result.walk_threshold_used,
        dynamic_threshold_applied=request.apply_dynamic_threshold,
        gap_mode=result.gap_mode,
        fatigue_applied=result.fatigue_applied,
        fatigue_info=result.fatigue_info,
        formatted_text=formatted,
    )


def _format_trail_run_result(result, flat_pace: float) -> str:
    """Format trail run result as text for bot/debugging."""
    lines = []

    # Header
    lines.append("🏃 TRAIL RUN PREDICTION")
    lines.append("=" * 40)

    # Summary
    s = result.summary
    lines.append(f"Distance: {s.total_distance_km:.1f} km")
    lines.append(f"Elevation: +{s.total_elevation_gain_m:.0f}m / -{s.total_elevation_loss_m:.0f}m")
    lines.append(f"Base pace: {int(flat_pace)}:{int((flat_pace % 1) * 60):02d}/km")
    lines.append("")

    # Time totals
    lines.append("⏱ TIME ESTIMATES:")
    for method, hours in sorted(result.totals.items()):
        h = int(hours)
        m = int((hours - h) * 60)
        lines.append(f"  {method}: {h}h {m:02d}min")
    lines.append("")

    # Run/Hike breakdown
    run_pct = (s.running_distance_km / s.total_distance_km * 100) if s.total_distance_km > 0 else 0
    lines.append("🏃/🚶 BREAKDOWN:")
    lines.append(f"  Running: {s.running_distance_km:.1f} km ({run_pct:.0f}%)")
    lines.append(f"  Hiking:  {s.hiking_distance_km:.1f} km ({100-run_pct:.0f}%)")
    lines.append(f"  Threshold: {result.walk_threshold_used:.0f}%")
    lines.append("")

    # Elevation impact
    lines.append(f"📈 Elevation impact: +{s.elevation_impact_percent:.0f}%")

    # Fatigue
    if result.fatigue_applied:
        lines.append(f"😓 Fatigue model: enabled")

    # Personalization
    if result.personalized:
        lines.append(f"👤 Personalized: {result.total_activities_used} activities")

    return "\n".join(lines)
