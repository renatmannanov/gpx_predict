"""
User Profile Service

Calculates and manages user performance profiles from Strava activity data.
"""

import logging
from datetime import datetime
from statistics import mean
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import UserPerformanceProfile
from app.models.strava_activity import StravaActivity

logger = logging.getLogger(__name__)


# Gradient thresholds for classifying terrain
FLAT_GRADIENT_MIN = -3.0  # %
FLAT_GRADIENT_MAX = 3.0   # %


class UserProfileService:
    """
    Service for calculating and managing user performance profiles.

    Provides methods to:
    - Calculate basic profile from activity aggregates
    - Calculate detailed profile from activity splits (when available)
    - Get/update profile for a user
    """

    # Minimum activities required for reliable profile
    MIN_ACTIVITIES_FOR_PROFILE = 1
    MIN_SPLITS_FOR_DETAILED_PROFILE = 5

    # Activity types to include in profile calculation
    # Only hiking activities for accurate hiking pace
    HIKING_ACTIVITY_TYPES = ["Hike", "Walk"]

    @staticmethod
    async def get_profile(
        user_id: str,
        db: AsyncSession
    ) -> Optional[UserPerformanceProfile]:
        """
        Get user's performance profile.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            UserPerformanceProfile or None if not exists
        """
        result = await db.execute(
            select(UserPerformanceProfile)
            .where(UserPerformanceProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def calculate_profile(
        user_id: str,
        db: AsyncSession
    ) -> Optional[UserPerformanceProfile]:
        """
        Calculate user's performance profile from their Strava activities.

        This is the basic version that uses activity-level aggregates
        (without splits). For more accurate profiles, use calculate_profile_with_splits()
        after syncing split data.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            UserPerformanceProfile or None if insufficient data
        """
        # Get user's hiking/walking activities
        result = await db.execute(
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(UserProfileService.HIKING_ACTIVITY_TYPES))
            .where(StravaActivity.distance_m > 0)
            .where(StravaActivity.moving_time_s > 0)
            .order_by(StravaActivity.start_date.desc())
            .limit(50)
        )
        activities = result.scalars().all()

        if len(activities) < UserProfileService.MIN_ACTIVITIES_FOR_PROFILE:
            logger.info(
                f"Insufficient activities for profile: {len(activities)} < "
                f"{UserProfileService.MIN_ACTIVITIES_FOR_PROFILE}"
            )
            return None

        # Calculate basic metrics
        avg_pace = UserProfileService._calculate_average_pace(activities)
        total_distance = sum(a.distance_m / 1000 for a in activities)
        total_elevation = sum(a.elevation_gain_m or 0 for a in activities)
        hike_count = len([a for a in activities if a.activity_type == "Hike"])

        # Get or create profile
        profile = await UserProfileService.get_profile(user_id, db)

        if profile:
            # Update existing profile
            profile.avg_flat_pace_min_km = avg_pace
            profile.total_activities_analyzed = len(activities)
            profile.total_hike_activities = hike_count
            profile.total_distance_km = total_distance
            profile.total_elevation_m = total_elevation
            profile.last_calculated_at = datetime.utcnow()
            profile.updated_at = datetime.utcnow()
        else:
            # Create new profile
            profile = UserPerformanceProfile(
                user_id=user_id,
                avg_flat_pace_min_km=avg_pace,
                total_activities_analyzed=len(activities),
                total_hike_activities=hike_count,
                total_distance_km=total_distance,
                total_elevation_m=total_elevation,
                last_calculated_at=datetime.utcnow()
            )
            db.add(profile)

        await db.commit()
        await db.refresh(profile)

        logger.info(
            f"Calculated profile for user {user_id}: "
            f"pace={avg_pace} min/km, activities={len(activities)}"
        )

        return profile

    @staticmethod
    async def calculate_profile_with_splits(
        user_id: str,
        db: AsyncSession
    ) -> Optional[UserPerformanceProfile]:
        """
        Calculate detailed profile using activity splits.

        This provides more accurate pace data by terrain type:
        - Flat pace (gradient -3% to +3%)
        - Uphill pace (gradient > +3%)
        - Downhill pace (gradient < -3%)

        Requires StravaActivitySplit data to be synced first.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            UserPerformanceProfile or None if insufficient data
        """
        # Import here to avoid circular dependency
        from app.models.strava_activity import StravaActivitySplit

        # Get all splits for user's hiking activities
        result = await db.execute(
            select(StravaActivitySplit)
            .join(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(UserProfileService.HIKING_ACTIVITY_TYPES))
        )
        splits = result.scalars().all()

        if len(splits) < UserProfileService.MIN_SPLITS_FOR_DETAILED_PROFILE:
            logger.info(
                f"Insufficient splits for detailed profile: {len(splits)} < "
                f"{UserProfileService.MIN_SPLITS_FOR_DETAILED_PROFILE}, "
                f"falling back to basic profile"
            )
            return await UserProfileService.calculate_profile(user_id, db)

        # Classify splits by gradient
        flat_splits = []
        uphill_splits = []
        downhill_splits = []

        for split in splits:
            gradient = split.gradient_percent
            pace = split.pace_min_km

            if gradient is None or pace is None:
                continue

            if FLAT_GRADIENT_MIN <= gradient <= FLAT_GRADIENT_MAX:
                flat_splits.append(pace)
            elif gradient > FLAT_GRADIENT_MAX:
                uphill_splits.append(pace)
            else:
                downhill_splits.append(pace)

        # Calculate average paces
        avg_flat_pace = mean(flat_splits) if flat_splits else None
        avg_uphill_pace = mean(uphill_splits) if uphill_splits else None
        avg_downhill_pace = mean(downhill_splits) if downhill_splits else None

        # Calculate vertical ability coefficient
        vertical_ability = UserProfileService._calculate_vertical_ability(
            avg_flat_pace, avg_uphill_pace
        )

        # Get activity statistics
        result = await db.execute(
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(UserProfileService.HIKING_ACTIVITY_TYPES))
        )
        activities = result.scalars().all()

        total_distance = sum(a.distance_m / 1000 for a in activities)
        total_elevation = sum(a.elevation_gain_m or 0 for a in activities)
        hike_count = len([a for a in activities if a.activity_type == "Hike"])

        # Get unique activity IDs from splits
        activity_ids = set(s.activity_id for s in splits)

        # Get or create profile
        profile = await UserProfileService.get_profile(user_id, db)

        if profile:
            # Update existing profile
            profile.avg_flat_pace_min_km = avg_flat_pace
            profile.avg_uphill_pace_min_km = avg_uphill_pace
            profile.avg_downhill_pace_min_km = avg_downhill_pace
            profile.vertical_ability = vertical_ability
            profile.total_activities_analyzed = len(activity_ids)
            profile.total_hike_activities = hike_count
            profile.total_distance_km = total_distance
            profile.total_elevation_m = total_elevation
            profile.last_calculated_at = datetime.utcnow()
            profile.updated_at = datetime.utcnow()
        else:
            # Create new profile
            profile = UserPerformanceProfile(
                user_id=user_id,
                avg_flat_pace_min_km=avg_flat_pace,
                avg_uphill_pace_min_km=avg_uphill_pace,
                avg_downhill_pace_min_km=avg_downhill_pace,
                vertical_ability=vertical_ability,
                total_activities_analyzed=len(activity_ids),
                total_hike_activities=hike_count,
                total_distance_km=total_distance,
                total_elevation_m=total_elevation,
                last_calculated_at=datetime.utcnow()
            )
            db.add(profile)

        await db.commit()
        await db.refresh(profile)

        logger.info(
            f"Calculated detailed profile for user {user_id}: "
            f"flat={avg_flat_pace}, uphill={avg_uphill_pace}, "
            f"downhill={avg_downhill_pace}, vertical_ability={vertical_ability}"
        )

        return profile

    @staticmethod
    def _calculate_average_pace(activities: list[StravaActivity]) -> Optional[float]:
        """
        Calculate average pace from activities in min/km.

        Args:
            activities: List of activities

        Returns:
            Average pace in min/km or None
        """
        total_time = sum(a.moving_time_s for a in activities if a.moving_time_s)
        total_distance = sum(a.distance_m for a in activities if a.distance_m)

        if total_distance == 0:
            return None

        pace_min_km = (total_time / 60) / (total_distance / 1000)
        return round(pace_min_km, 2)

    @staticmethod
    def _calculate_vertical_ability(
        flat_pace: Optional[float],
        uphill_pace: Optional[float]
    ) -> float:
        """
        Calculate vertical ability coefficient.

        Compares actual uphill slowdown to Naismith standard.
        Naismith assumes ~1.5x slowdown on uphills.

        Args:
            flat_pace: Average flat pace (min/km)
            uphill_pace: Average uphill pace (min/km)

        Returns:
            Vertical ability coefficient:
            - 1.0 = standard (matches Naismith)
            - <1.0 = faster than standard on uphills
            - >1.0 = slower than standard on uphills
        """
        if not flat_pace or not uphill_pace or flat_pace == 0:
            return 1.0

        # Expected slowdown according to Naismith
        expected_ratio = 1.5

        # Actual slowdown
        actual_ratio = uphill_pace / flat_pace

        # Vertical ability = actual / expected
        vertical_ability = actual_ratio / expected_ratio

        return round(vertical_ability, 2)

    @staticmethod
    async def delete_profile(user_id: str, db: AsyncSession) -> bool:
        """
        Delete user's performance profile.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            True if deleted, False if not found
        """
        profile = await UserProfileService.get_profile(user_id, db)

        if profile:
            await db.delete(profile)
            await db.commit()
            logger.info(f"Deleted profile for user {user_id}")
            return True

        return False
