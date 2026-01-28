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

from app.features.hiking import UserHikingProfile as UserPerformanceProfile
from app.features.trail_run import UserRunProfile
from app.models.strava_activity import StravaActivity

logger = logging.getLogger(__name__)


# Gradient thresholds for classifying terrain (3-category legacy system)
FLAT_GRADIENT_MIN = -3.0  # %
FLAT_GRADIENT_MAX = 3.0   # %

# Extended 7-category gradient thresholds (based on Tobler's hiking function)
# See docs/todo/ACCURACY_IMPROVEMENTS_PLAN.md for research
GRADIENT_THRESHOLDS = {
    'steep_downhill': (-100.0, -15.0),      # < -15%
    'moderate_downhill': (-15.0, -8.0),     # -15% to -8%
    'gentle_downhill': (-8.0, -3.0),        # -8% to -3%
    'flat': (-3.0, 3.0),                    # -3% to +3%
    'gentle_uphill': (3.0, 8.0),            # +3% to +8%
    'moderate_uphill': (8.0, 15.0),         # +8% to +15%
    'steep_uphill': (15.0, 100.0),          # > +15%
}

# Outlier filtering thresholds for pace data
# Paces outside this range are considered stops/errors, not actual hiking
PACE_MIN_THRESHOLD_HIKE = 4.0   # min/km - faster than this is likely running/error
PACE_MAX_THRESHOLD_HIKE = 25.0  # min/km - slower than this is likely a stop

# Pace thresholds for running (more permissive on fast end)
PACE_MIN_THRESHOLD_RUN = 2.5    # min/km - faster than this is likely GPS error
PACE_MAX_THRESHOLD_RUN = 15.0   # min/km - slower than this is walking


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

    # Running activity types for run profile
    RUNNING_ACTIVITY_TYPES = ["Run", "TrailRun", "VirtualRun"]

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

        This provides pace data by terrain type:
        - Legacy 3-category: flat, uphill, downhill
        - Extended 7-category: steep_downhill, moderate_downhill, gentle_downhill,
                               flat, gentle_uphill, moderate_uphill, steep_uphill

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

        # Classify splits by gradient (both 3-category and 7-category)
        # Legacy 3-category
        flat_splits = []
        uphill_splits = []
        downhill_splits = []

        # Extended 7-category
        splits_by_category = {
            'steep_downhill': [],
            'moderate_downhill': [],
            'gentle_downhill': [],
            'flat': [],
            'gentle_uphill': [],
            'moderate_uphill': [],
            'steep_uphill': [],
        }

        filtered_count = 0
        for split in splits:
            gradient = split.gradient_percent
            pace = split.pace_min_km

            if gradient is None or pace is None:
                continue

            # Filter outliers - paces that indicate stops or errors
            if pace < PACE_MIN_THRESHOLD_HIKE or pace > PACE_MAX_THRESHOLD_HIKE:
                filtered_count += 1
                logger.debug(f"Filtered outlier split: pace={pace:.1f} min/km (threshold: {PACE_MIN_THRESHOLD_HIKE}-{PACE_MAX_THRESHOLD_HIKE})")
                continue

            # Legacy 3-category classification
            if FLAT_GRADIENT_MIN <= gradient <= FLAT_GRADIENT_MAX:
                flat_splits.append(pace)
            elif gradient > FLAT_GRADIENT_MAX:
                uphill_splits.append(pace)
            else:
                downhill_splits.append(pace)

            # Extended 7-category classification
            category = UserProfileService._classify_gradient(gradient)
            splits_by_category[category].append(pace)

        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} outlier splits (pace outside {PACE_MIN_THRESHOLD_HIKE}-{PACE_MAX_THRESHOLD_HIKE} min/km)")

        # Calculate legacy average paces
        avg_flat_pace = mean(flat_splits) if flat_splits else None
        avg_uphill_pace = mean(uphill_splits) if uphill_splits else None
        avg_downhill_pace = mean(downhill_splits) if downhill_splits else None

        # Calculate extended 7-category average paces
        extended_paces = {}
        for category, paces in splits_by_category.items():
            extended_paces[category] = mean(paces) if paces else None

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
            # Update existing profile - legacy fields
            profile.avg_flat_pace_min_km = avg_flat_pace
            profile.avg_uphill_pace_min_km = avg_uphill_pace
            profile.avg_downhill_pace_min_km = avg_downhill_pace
            # Extended 7-category fields
            profile.avg_steep_downhill_pace_min_km = extended_paces['steep_downhill']
            profile.avg_moderate_downhill_pace_min_km = extended_paces['moderate_downhill']
            profile.avg_gentle_downhill_pace_min_km = extended_paces['gentle_downhill']
            profile.avg_gentle_uphill_pace_min_km = extended_paces['gentle_uphill']
            profile.avg_moderate_uphill_pace_min_km = extended_paces['moderate_uphill']
            profile.avg_steep_uphill_pace_min_km = extended_paces['steep_uphill']
            # Stats
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
                # Legacy fields
                avg_flat_pace_min_km=avg_flat_pace,
                avg_uphill_pace_min_km=avg_uphill_pace,
                avg_downhill_pace_min_km=avg_downhill_pace,
                # Extended 7-category fields
                avg_steep_downhill_pace_min_km=extended_paces['steep_downhill'],
                avg_moderate_downhill_pace_min_km=extended_paces['moderate_downhill'],
                avg_gentle_downhill_pace_min_km=extended_paces['gentle_downhill'],
                avg_gentle_uphill_pace_min_km=extended_paces['gentle_uphill'],
                avg_moderate_uphill_pace_min_km=extended_paces['moderate_uphill'],
                avg_steep_uphill_pace_min_km=extended_paces['steep_uphill'],
                # Stats
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

        # Log with extended info
        logger.info(
            f"Calculated detailed profile for user {user_id}: "
            f"flat={avg_flat_pace}, uphill={avg_uphill_pace}, downhill={avg_downhill_pace}, "
            f"vertical_ability={vertical_ability}"
        )
        logger.info(
            f"Extended gradients for user {user_id}: "
            f"steep_down={extended_paces['steep_downhill']}, "
            f"mod_down={extended_paces['moderate_downhill']}, "
            f"gentle_down={extended_paces['gentle_downhill']}, "
            f"gentle_up={extended_paces['gentle_uphill']}, "
            f"mod_up={extended_paces['moderate_uphill']}, "
            f"steep_up={extended_paces['steep_uphill']}"
        )

        return profile

    @staticmethod
    def _classify_gradient(gradient_percent: float) -> str:
        """
        Classify gradient into one of 7 categories.

        Args:
            gradient_percent: Gradient as percentage (e.g., 10.0 for 10%)

        Returns:
            Category name: steep_downhill, moderate_downhill, gentle_downhill,
                          flat, gentle_uphill, moderate_uphill, steep_uphill
        """
        for category, (min_grad, max_grad) in GRADIENT_THRESHOLDS.items():
            if min_grad <= gradient_percent < max_grad:
                return category
        # Edge case: exactly at max threshold
        if gradient_percent >= 15.0:
            return 'steep_uphill'
        if gradient_percent <= -15.0:
            return 'steep_downhill'
        return 'flat'

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

    # =========================================================================
    # Run Profile Methods
    # =========================================================================

    @staticmethod
    async def get_run_profile(
        user_id: str,
        db: AsyncSession
    ) -> Optional[UserRunProfile]:
        """
        Get user's running performance profile.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            UserRunProfile or None if not exists
        """
        result = await db.execute(
            select(UserRunProfile)
            .where(UserRunProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def calculate_run_profile_with_splits(
        user_id: str,
        db: AsyncSession
    ) -> Optional[UserRunProfile]:
        """
        Calculate run profile from Run/TrailRun activity splits.

        Uses 7-category gradient system (extended gradients only).
        Also detects walk threshold from pace jumps.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            UserRunProfile or None if insufficient data
        """
        from app.models.strava_activity import StravaActivitySplit

        # Get all splits for user's running activities
        result = await db.execute(
            select(StravaActivitySplit)
            .join(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(UserProfileService.RUNNING_ACTIVITY_TYPES))
        )
        splits = result.scalars().all()

        if len(splits) < UserProfileService.MIN_SPLITS_FOR_DETAILED_PROFILE:
            logger.info(
                f"Insufficient run splits for profile: {len(splits)} < "
                f"{UserProfileService.MIN_SPLITS_FOR_DETAILED_PROFILE}"
            )
            return None

        # Extended 7-category only for running
        splits_by_category = {
            'steep_downhill': [],
            'moderate_downhill': [],
            'gentle_downhill': [],
            'flat': [],
            'gentle_uphill': [],
            'moderate_uphill': [],
            'steep_uphill': [],
        }

        # For walk threshold detection
        uphill_splits_for_threshold = []

        filtered_count = 0
        for split in splits:
            gradient = split.gradient_percent
            pace = split.pace_min_km

            if gradient is None or pace is None:
                continue

            # Filter outliers for running
            if pace < PACE_MIN_THRESHOLD_RUN or pace > PACE_MAX_THRESHOLD_RUN:
                filtered_count += 1
                continue

            # Classify into 7 categories
            category = UserProfileService._classify_gradient(gradient)
            splits_by_category[category].append(pace)

            # Collect uphill splits for threshold detection
            if gradient > 5:
                uphill_splits_for_threshold.append({
                    'gradient_percent': gradient,
                    'pace_min_km': pace
                })

        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} outlier run splits (pace outside {PACE_MIN_THRESHOLD_RUN}-{PACE_MAX_THRESHOLD_RUN} min/km)")

        # Calculate 7-category average paces
        extended_paces = {}
        for category, paces in splits_by_category.items():
            extended_paces[category] = mean(paces) if paces else None

        # Detect walk threshold
        walk_threshold = UserProfileService._detect_walk_threshold(uphill_splits_for_threshold)

        # Get activity statistics
        result = await db.execute(
            select(StravaActivity)
            .where(StravaActivity.user_id == user_id)
            .where(StravaActivity.activity_type.in_(UserProfileService.RUNNING_ACTIVITY_TYPES))
        )
        activities = result.scalars().all()

        total_distance = sum(a.distance_m / 1000 for a in activities)
        total_elevation = sum(a.elevation_gain_m or 0 for a in activities)

        # Get unique activity IDs from splits
        activity_ids = set(s.activity_id for s in splits)

        # Get or create run profile
        profile = await UserProfileService.get_run_profile(user_id, db)

        if profile:
            # Update existing profile
            profile.avg_flat_pace_min_km = extended_paces['flat']
            profile.avg_gentle_uphill_pace_min_km = extended_paces['gentle_uphill']
            profile.avg_moderate_uphill_pace_min_km = extended_paces['moderate_uphill']
            profile.avg_steep_uphill_pace_min_km = extended_paces['steep_uphill']
            profile.avg_gentle_downhill_pace_min_km = extended_paces['gentle_downhill']
            profile.avg_moderate_downhill_pace_min_km = extended_paces['moderate_downhill']
            profile.avg_steep_downhill_pace_min_km = extended_paces['steep_downhill']
            profile.walk_threshold_percent = walk_threshold
            profile.total_activities = len(activity_ids)
            profile.total_distance_km = total_distance
            profile.total_elevation_m = total_elevation
            profile.last_calculated_at = datetime.utcnow()
            profile.updated_at = datetime.utcnow()
        else:
            # Create new run profile
            profile = UserRunProfile(
                user_id=user_id,
                avg_flat_pace_min_km=extended_paces['flat'],
                avg_gentle_uphill_pace_min_km=extended_paces['gentle_uphill'],
                avg_moderate_uphill_pace_min_km=extended_paces['moderate_uphill'],
                avg_steep_uphill_pace_min_km=extended_paces['steep_uphill'],
                avg_gentle_downhill_pace_min_km=extended_paces['gentle_downhill'],
                avg_moderate_downhill_pace_min_km=extended_paces['moderate_downhill'],
                avg_steep_downhill_pace_min_km=extended_paces['steep_downhill'],
                walk_threshold_percent=walk_threshold,
                total_activities=len(activity_ids),
                total_distance_km=total_distance,
                total_elevation_m=total_elevation,
                last_calculated_at=datetime.utcnow()
            )
            db.add(profile)

        await db.commit()
        await db.refresh(profile)

        logger.info(
            f"Calculated run profile for user {user_id}: "
            f"flat_pace={extended_paces['flat']}, "
            f"walk_threshold={walk_threshold}%, "
            f"activities={len(activity_ids)}"
        )

        return profile

    @staticmethod
    def _detect_walk_threshold(uphill_splits: list[dict]) -> float:
        """
        Detect walk threshold from uphill splits.

        Looks for gradient where pace suddenly jumps (indicating transition to walking).

        Args:
            uphill_splits: List of dicts with gradient_percent and pace_min_km

        Returns:
            Detected threshold (%) or default 25%
        """
        DEFAULT_THRESHOLD = 25.0
        MIN_THRESHOLD = 15.0
        MAX_THRESHOLD = 35.0

        if len(uphill_splits) < 10:
            return DEFAULT_THRESHOLD

        # Sort by gradient
        sorted_splits = sorted(uphill_splits, key=lambda x: x['gradient_percent'])

        # Find steepest pace derivative (where pace jumps most)
        max_derivative = 0
        threshold = DEFAULT_THRESHOLD

        for i in range(1, len(sorted_splits)):
            prev = sorted_splits[i - 1]
            curr = sorted_splits[i]

            pace_change = curr['pace_min_km'] - prev['pace_min_km']
            gradient_change = curr['gradient_percent'] - prev['gradient_percent']

            if gradient_change > 0 and pace_change > 0:
                derivative = pace_change / gradient_change
                if derivative > max_derivative:
                    max_derivative = derivative
                    threshold = (prev['gradient_percent'] + curr['gradient_percent']) / 2

        # Clamp to reasonable range
        threshold = max(MIN_THRESHOLD, min(MAX_THRESHOLD, threshold))
        return round(threshold, 1)

    @staticmethod
    async def delete_run_profile(user_id: str, db: AsyncSession) -> bool:
        """
        Delete user's run performance profile.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            True if deleted, False if not found
        """
        profile = await UserProfileService.get_run_profile(user_id, db)

        if profile:
            await db.delete(profile)
            await db.commit()
            logger.info(f"Deleted run profile for user {user_id}")
            return True

        return False
