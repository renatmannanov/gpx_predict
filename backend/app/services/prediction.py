"""
Prediction Service

Main service for calculating hike/run predictions.
Supports personalization based on user's Strava activity history.
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
    HikerProfile,
    NAISMITH_BASE_SPEED_KMH
)
from app.features.gpx import GPXRepository, GPXParserService, GPXSegment
from app.services.sun import get_sun_times
from app.features.hiking import UserHikingProfile as UserPerformanceProfile

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for time predictions."""

    @staticmethod
    async def predict_hike(
        gpx_id: str,
        experience: ExperienceLevel,
        backpack: BackpackWeight,
        group_size: int,
        has_children: bool,
        has_elderly: bool,
        is_round_trip: bool,
        db,
        sunrise: str = "06:00",
        sunset: str = "20:00",
        user_profile: Optional[UserPerformanceProfile] = None
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
            user_profile: Optional UserPerformanceProfile for personalization

        Returns:
            HikePrediction with estimated times and warnings

        Raises:
            ValueError: If GPX file not found
        """
        # Fetch GPX data from database
        gpx_repo = GPXRepository(db)
        gpx_file = await gpx_repo.get_by_id(gpx_id)

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

        # Determine base speed - use personal data if available
        personalized = False
        personal_speed_kmh = None

        if user_profile and user_profile.avg_flat_pace_min_km:
            # Use personal pace from Strava data
            personal_speed_kmh = user_profile.flat_speed_kmh
            personalized = True
            logger.info(
                f"Using personalized speed: {personal_speed_kmh} km/h "
                f"(from profile with {user_profile.total_activities_analyzed} activities)"
            )

        # Base time calculation
        if personalized and personal_speed_kmh:
            # Personalized calculation
            base_time = PredictionService._calculate_personalized_time(
                distance_km=distance_km,
                elevation_gain_m=elevation_gain_m,
                elevation_loss_m=elevation_loss_m,
                user_profile=user_profile
            )
        else:
            # Standard Naismith calculation
            base_time = naismith_with_descent(
                distance_km,
                elevation_gain_m,
                elevation_loss_m
            )

        # If round trip, add return time
        if is_round_trip:
            if personalized and personal_speed_kmh:
                return_time = PredictionService._calculate_personalized_time(
                    distance_km=distance_km,
                    elevation_gain_m=elevation_loss_m,  # Swap gain/loss
                    elevation_loss_m=elevation_gain_m,
                    user_profile=user_profile
                )
            else:
                return_time = naismith_with_descent(
                    distance_km,
                    elevation_loss_m,  # Swap gain/loss
                    elevation_gain_m
                )
            return_time *= 0.9  # 10% faster on return (familiar trail)
            base_time += return_time

        # Apply profile multipliers
        # When personalized, reduce experience multiplier impact (data already reflects skill)
        total_multiplier = get_total_multiplier(profile)

        if personalized:
            # Reduce experience multiplier influence by 50% when we have real data
            exp_mult = get_experience_multiplier(experience)
            reduced_exp_mult = 1.0 + (exp_mult - 1.0) * 0.5

            # Recalculate total multiplier with reduced experience factor
            total_multiplier = (
                reduced_exp_mult *
                get_backpack_multiplier(backpack) *
                get_group_multiplier(group_size) *
                get_altitude_multiplier(max_altitude_m)
            )

            # Apply vertical ability adjustment if available
            if user_profile.vertical_ability and user_profile.vertical_ability != 1.0:
                # Adjust for personal climbing ability
                total_multiplier *= user_profile.vertical_ability

            logger.info(f"Personalized multiplier: {total_multiplier:.2f}")

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

        # Add personalization info to warnings if used
        if personalized:
            warnings.insert(0, Warning(
                level=WarningLevel.INFO,
                code="personalized",
                message=f"Prediction personalized based on {user_profile.total_activities_analyzed} activities"
            ))

        # Calculate segment breakdown
        segments = PredictionService._calculate_segments(
            gpx_file.gpx_content,
            total_multiplier,
            user_profile
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
            total_multiplier=total_multiplier,
            personalized=personalized,
            activities_used=user_profile.total_activities_analyzed if user_profile else 0
        )

    @staticmethod
    def _calculate_personalized_time(
        distance_km: float,
        elevation_gain_m: float,
        elevation_loss_m: float,
        user_profile: UserPerformanceProfile
    ) -> float:
        """
        Calculate time using personalized pace data.

        Uses user's actual pace for different terrain types when available,
        falls back to Naismith for missing data.

        Args:
            distance_km: Total distance
            elevation_gain_m: Total elevation gain
            elevation_loss_m: Total elevation loss
            user_profile: User's performance profile

        Returns:
            Estimated time in hours
        """
        # Estimate terrain distribution based on elevation
        # This is approximate - with splits we can be more accurate
        total_elevation_change = elevation_gain_m + elevation_loss_m

        if total_elevation_change > 0 and distance_km > 0:
            # Rough estimate of terrain breakdown
            avg_gradient = total_elevation_change / (distance_km * 1000) * 100

            if avg_gradient < 5:
                # Mostly flat terrain
                flat_ratio = 0.7
                uphill_ratio = elevation_gain_m / total_elevation_change * 0.3
                downhill_ratio = elevation_loss_m / total_elevation_change * 0.3
            else:
                # Hilly terrain
                flat_ratio = 0.3
                uphill_ratio = elevation_gain_m / total_elevation_change * 0.7
                downhill_ratio = elevation_loss_m / total_elevation_change * 0.7
        else:
            flat_ratio = 1.0
            uphill_ratio = 0.0
            downhill_ratio = 0.0

        # Calculate time for each terrain type
        time_hours = 0.0

        # Flat terrain
        if user_profile.avg_flat_pace_min_km:
            flat_speed = 60 / user_profile.avg_flat_pace_min_km  # km/h
        else:
            flat_speed = NAISMITH_BASE_SPEED_KMH

        time_hours += (distance_km * flat_ratio) / flat_speed

        # Uphill - use personal uphill pace or estimate
        if user_profile.avg_uphill_pace_min_km:
            uphill_speed = 60 / user_profile.avg_uphill_pace_min_km
        else:
            # Estimate: 50% slower than flat
            uphill_speed = flat_speed * 0.67

        time_hours += (distance_km * uphill_ratio) / uphill_speed

        # Downhill - use personal downhill pace or estimate
        if user_profile.avg_downhill_pace_min_km:
            downhill_speed = 60 / user_profile.avg_downhill_pace_min_km
        else:
            # Estimate: 20% faster than flat
            downhill_speed = flat_speed * 1.2

        time_hours += (distance_km * downhill_ratio) / downhill_speed

        return time_hours

    @staticmethod
    async def predict_group(
        gpx_id: str,
        members: List[GroupMemberInput],
        is_round_trip: bool,
        db
    ) -> GroupPrediction:
        """
        Calculate group hike prediction.

        Analyzes each member and provides recommendations.
        """
        # Calculate individual predictions
        member_predictions = []

        for member in members:
            # Simple prediction for each member
            prediction = await PredictionService.predict_hike(
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
        multiplier: float,
        user_profile: Optional[UserPerformanceProfile] = None
    ) -> List[SegmentPrediction]:
        """
        Calculate time predictions for each route segment.

        Args:
            gpx_content: Raw GPX file content
            multiplier: Total time multiplier from profile
            user_profile: Optional user profile for personalized segment times

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
            # Determine speed based on segment gradient and user profile
            if user_profile and user_profile.has_split_data:
                # Use personalized pace based on gradient
                gradient = seg.gradient_percent or 0

                if gradient > 3:
                    # Uphill
                    pace = user_profile.avg_uphill_pace_min_km
                elif gradient < -3:
                    # Downhill
                    pace = user_profile.avg_downhill_pace_min_km
                else:
                    # Flat
                    pace = user_profile.avg_flat_pace_min_km

                if pace:
                    base_minutes = seg.distance_km * pace
                else:
                    # Fallback to Naismith
                    base_minutes = naismith_with_descent(
                        seg.distance_km,
                        seg.elevation_gain_m,
                        seg.elevation_loss_m
                    ) * 60
            else:
                # Standard Naismith calculation
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
