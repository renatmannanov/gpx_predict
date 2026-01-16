"""
Prediction Routes

Endpoints for time predictions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.schemas.prediction import (
    HikePredictRequest,
    HikePrediction,
    GroupPredictRequest,
    GroupPrediction,
    RouteComparisonResponse,
    MacroSegmentSchema,
    ExperienceLevel,
    BackpackWeight
)
from app.services.prediction import PredictionService
from app.services.calculators import ComparisonService
from app.repositories.gpx import GPXRepository
from app.services.gpx_parser import GPXParserService
from app.services.naismith import get_total_multiplier, estimate_rest_time, HikerProfile
from app.services.sun import get_sun_times

router = APIRouter()


class CompareRequest(BaseModel):
    """Request for method comparison."""
    gpx_id: str
    experience: ExperienceLevel = ExperienceLevel.REGULAR
    backpack: BackpackWeight = BackpackWeight.LIGHT
    group_size: int = Field(default=1, ge=1, le=50)


@router.post("/hike", response_model=HikePrediction)
async def predict_hike(
    request: HikePredictRequest,
    db: Session = Depends(get_db)
):
    """
    Predict hiking time for a route.

    Uses Naismith's rule with profile-based adjustments.
    """
    try:
        prediction = PredictionService.predict_hike(
            gpx_id=request.gpx_id,
            experience=request.experience,
            backpack=request.backpack,
            group_size=request.group_size,
            has_children=request.has_children,
            has_elderly=request.has_elderly,
            is_round_trip=request.is_round_trip,
            db=db
        )
        return prediction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group", response_model=GroupPrediction)
async def predict_group(
    request: GroupPredictRequest,
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
):
    """
    Compare different prediction methods on a route.

    Returns segment-by-segment breakdown with both
    Naismith and Tobler calculations.
    """
    # Get GPX file
    gpx_repo = GPXRepository(db)
    gpx_file = gpx_repo.get_by_id(request.gpx_id)

    if not gpx_file:
        raise HTTPException(status_code=404, detail=f"GPX file not found: {request.gpx_id}")

    if not gpx_file.gpx_content:
        raise HTTPException(status_code=400, detail="GPX file has no content")

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

    # Run comparison
    comparison_service = ComparisonService()
    comparison = comparison_service.compare_route(points, multiplier)

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
        formatted_text=formatted
    )


# Future: Running prediction
# @router.post("/run", response_model=RunPrediction)
# async def predict_run(request: RunPredictRequest, db: Session = Depends(get_db)):
#     pass
