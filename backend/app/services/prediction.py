"""
Prediction Service

Main service for calculating hike/run predictions.
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.schemas.prediction import (
    HikePrediction,
    GroupPrediction,
    GroupMemberInput,
    GroupMemberPrediction,
    GroupRole,
    Warning,
    WarningLevel,
    SegmentPrediction,
    MeetingPoint,
    ExperienceLevel,
    BackpackWeight,
    TimeBreakdown
)
from app.services.naismith import (
    naismith_with_descent,
    get_experience_multiplier,
    get_backpack_multiplier,
    get_group_multiplier,
    get_altitude_multiplier,
    get_total_multiplier,
    estimate_rest_time,
    calculate_start_time,
    HikerProfile
)
from app.repositories.gpx import GPXRepository
from app.services.gpx_parser import GPXParserService, GPXSegment
from app.services.sun import get_sun_times

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for time predictions."""

    @staticmethod
    def predict_hike(
        gpx_id: str,
        experience: ExperienceLevel,
        backpack: BackpackWeight,
        group_size: int,
        has_children: bool,
        has_elderly: bool,
        is_round_trip: bool,
        db: Session,
        sunrise: str = "06:00",
        sunset: str = "20:00"
    ) -> HikePrediction:
        """
        Calculate hike time prediction.

        Args:
            gpx_id: ID of uploaded GPX file
            experience: Hiker experience level
            backpack: Backpack weight category
            group_size: Number of people in group
            has_children: Group includes children
            has_elderly: Group includes elderly
            is_round_trip: If route is out-and-back
            db: Database session
            sunrise: Sunrise time for calculations
            sunset: Sunset time for calculations

        Returns:
            HikePrediction with estimated times and warnings

        Raises:
            ValueError: If GPX file not found
        """
        # Fetch GPX data from database
        gpx_repo = GPXRepository(db)
        gpx_file = gpx_repo.get_by_id(gpx_id)

        if not gpx_file:
            raise ValueError(f"GPX file not found: {gpx_id}")

        distance_km = gpx_file.distance_km or 0.0
        elevation_gain_m = gpx_file.elevation_gain_m or 0.0
        elevation_loss_m = gpx_file.elevation_loss_m or 0.0
        max_altitude_m = gpx_file.max_elevation_m or 0.0

        # Get sun times from route coordinates
        if gpx_file.start_lat and gpx_file.start_lon:
            sun_times = get_sun_times(gpx_file.start_lat, gpx_file.start_lon)
            sunrise = sun_times.sunrise
            sunset = sun_times.sunset

        # Create hiker profile
        profile = HikerProfile(
            experience=experience,
            backpack=backpack,
            group_size=group_size,
            max_altitude_m=max_altitude_m,
            has_children=has_children,
            has_elderly=has_elderly
        )

        # Base time (Naismith)
        base_time = naismith_with_descent(
            distance_km,
            elevation_gain_m,
            elevation_loss_m
        )

        # If round trip, add return time
        if is_round_trip:
            return_time = naismith_with_descent(
                distance_km,
                elevation_loss_m,  # Swap gain/loss
                elevation_gain_m
            )
            return_time *= 0.9  # 10% faster on return (familiar trail)
            base_time += return_time

        # Apply profile multipliers
        total_multiplier = get_total_multiplier(profile)
        moving_time = base_time * total_multiplier

        # Add rest time
        rest_time = estimate_rest_time(moving_time, experience)

        # Add lunch break for long hikes
        lunch_time = 0.5 if moving_time > 4 else 0.0

        # Total adjusted time
        adjusted_time = moving_time + rest_time + lunch_time

        # Safe time (+20%)
        safe_time = adjusted_time * 1.2

        # Create time breakdown
        time_breakdown = TimeBreakdown(
            moving_time_hours=round(moving_time, 2),
            rest_time_hours=round(rest_time, 2),
            lunch_time_hours=round(lunch_time, 2)
        )

        # Recommended start
        recommended_start = calculate_start_time(safe_time, sunset)

        # Generate warnings
        warnings = PredictionService._generate_warnings(
            adjusted_time,
            max_altitude_m,
            sunset
        )

        # Calculate segment breakdown
        segments = PredictionService._calculate_segments(
            gpx_file.gpx_content,
            total_multiplier
        )

        return HikePrediction(
            estimated_time_hours=round(adjusted_time, 1),
            safe_time_hours=round(safe_time, 1),
            recommended_start=recommended_start,
            time_breakdown=time_breakdown,
            warnings=warnings,
            segments=segments,
            experience_multiplier=get_experience_multiplier(experience),
            backpack_multiplier=get_backpack_multiplier(backpack),
            group_multiplier=get_group_multiplier(group_size),
            altitude_multiplier=get_altitude_multiplier(max_altitude_m),
            total_multiplier=total_multiplier
        )

    @staticmethod
    def predict_group(
        gpx_id: str,
        members: List[GroupMemberInput],
        is_round_trip: bool,
        db: Session
    ) -> GroupPrediction:
        """
        Calculate group hike prediction.

        Analyzes each member and provides recommendations.
        """
        # Calculate individual predictions
        member_predictions = []

        for member in members:
            # Simple prediction for each member
            prediction = PredictionService.predict_hike(
                gpx_id=gpx_id,
                experience=member.experience,
                backpack=member.backpack,
                group_size=1,  # Individual time
                has_children=member.has_children,
                has_elderly=False,
                is_round_trip=is_round_trip,
                db=db
            )

            member_predictions.append({
                "name": member.name,
                "time": prediction.estimated_time_hours
            })

        # Sort by time
        member_predictions.sort(key=lambda x: x["time"])

        # Calculate spread
        fastest = member_predictions[0]["time"]
        slowest = member_predictions[-1]["time"]
        spread = slowest - fastest

        # Assign roles
        n = len(members)
        member_results = []
        for i, mp in enumerate(member_predictions):
            if i < n * 0.25:
                role = GroupRole.FAST
            elif i >= n * 0.75:
                role = GroupRole.SLOW
            else:
                role = GroupRole.AVERAGE

            member_results.append(GroupMemberPrediction(
                name=mp["name"],
                individual_time_hours=mp["time"],
                role=role
            ))

        # Group time = slowest + waiting overhead
        waiting_overhead = spread * 0.15
        group_time = slowest + waiting_overhead

        # Should split?
        split_recommended = spread > 2.0 or (spread / slowest > 0.4)

        # Subgroups
        subgroups = None
        if split_recommended and n >= 4:
            fast_group = [m.name for m in member_results if m.role == GroupRole.FAST]
            slow_group = [m.name for m in member_results if m.role == GroupRole.SLOW]
            avg_group = [m.name for m in member_results if m.role == GroupRole.AVERAGE]

            # Distribute average members
            half = len(avg_group) // 2
            subgroups = [
                fast_group + avg_group[:half],
                slow_group + avg_group[half:]
            ]

        # Recommendations
        recommendations = []
        if split_recommended:
            recommendations.append(
                "Consider splitting into two groups for a better experience"
            )
        if spread > 3:
            recommendations.append(
                "Large speed difference - fast hikers will wait significantly"
            )

        return GroupPrediction(
            members=member_results,
            group_time_hours=round(group_time, 1),
            spread_hours=round(spread, 1),
            split_recommended=split_recommended,
            subgroups=subgroups,
            recommendations=recommendations,
            meeting_points=[]  # TODO: calculate meeting points
        )

    @staticmethod
    def _generate_warnings(
        duration_hours: float,
        max_altitude_m: float,
        sunset: str
    ) -> List[Warning]:
        """Generate safety warnings based on prediction."""
        warnings = []

        # Long hike warning
        if duration_hours > 8:
            warnings.append(Warning(
                level=WarningLevel.INFO,
                code="long_hike",
                message="Long hike (8+ hours). Bring enough water and food."
            ))

        # High altitude warning
        if max_altitude_m > 3000:
            warnings.append(Warning(
                level=WarningLevel.WARNING,
                code="high_altitude",
                message=f"Route reaches {int(max_altitude_m)}m. Watch for altitude sickness symptoms."
            ))

        # Late return warning
        sunset_hour = int(sunset.split(":")[0])
        if duration_hours > sunset_hour - 6:  # Starting at 6 AM
            warnings.append(Warning(
                level=WarningLevel.DANGER,
                code="late_return",
                message="Risk of returning after dark. Start early or choose shorter route."
            ))

        return warnings

    @staticmethod
    def _calculate_segments(
        gpx_content: bytes,
        multiplier: float
    ) -> List[SegmentPrediction]:
        """
        Calculate time predictions for each route segment.

        Args:
            gpx_content: Raw GPX file content
            multiplier: Total time multiplier from profile

        Returns:
            List of SegmentPrediction with times
        """
        if not gpx_content:
            return []

        try:
            points = GPXParserService.extract_points(gpx_content)
            gpx_segments = GPXParserService.segment_route(points)
        except Exception as e:
            logger.warning(f"Failed to segment route: {e}")
            return []

        segment_predictions = []
        for seg in gpx_segments:
            # Calculate base time using Naismith
            base_minutes = naismith_with_descent(
                seg.distance_km,
                seg.elevation_gain_m,
                seg.elevation_loss_m
            ) * 60  # Convert hours to minutes

            # Apply profile multiplier
            predicted_minutes = base_minutes * multiplier

            segment_predictions.append(SegmentPrediction(
                start_km=seg.start_km,
                end_km=seg.end_km,
                distance_km=seg.distance_km,
                elevation_change_m=seg.end_elevation_m - seg.start_elevation_m,
                gradient_percent=seg.gradient_percent,
                predicted_minutes=round(predicted_minutes, 0)
            ))

        return segment_predictions
