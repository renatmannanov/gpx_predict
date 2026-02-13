"""
User Profile Service

Calculates and manages user performance profiles from Strava activity data.
"""

import logging
import statistics
from datetime import datetime
from statistics import mean
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.hiking import UserHikingProfile as UserPerformanceProfile
from app.features.trail_run import UserRunProfile
from app.features.strava import StravaActivity
from app.shared.constants import DEFAULT_HIKE_THRESHOLD_PERCENT
from app.shared.gradients import (
    GRADIENT_THRESHOLDS,
    LEGACY_GRADIENT_THRESHOLDS,
    LEGACY_CATEGORY_MAPPING,
    FLAT_GRADIENT_MIN,
    FLAT_GRADIENT_MAX,
    classify_gradient,
    classify_gradient_legacy,
)

logger = logging.getLogger(__name__)


# Note: GRADIENT_THRESHOLDS (11-cat) is imported from shared.gradients
# LEGACY_GRADIENT_THRESHOLDS (7-cat) also imported for backward compatibility

# Outlier filtering thresholds for pace data
# Paces outside this range are considered stops/errors, not actual hiking
PACE_MIN_THRESHOLD_HIKE = 4.0   # min/km - faster than this is likely running/error
PACE_MAX_THRESHOLD_HIKE = 25.0  # min/km - slower than this is likely a stop

# Pace thresholds for running (more permissive on fast end)
PACE_MIN_THRESHOLD_RUN = 2.5    # min/km - faster than this is likely GPS error
PACE_MAX_THRESHOLD_RUN = 30.0   # min/km - sanity threshold (GPS errors, stops)


def filter_outliers_iqr(paces: list[float]) -> list[float]:
    """
    Remove outliers using IQR method.

    Interquartile Range (IQR) = Q3 - Q1.
    Outliers: values below Q1 - 1.5*IQR or above Q3 + 1.5*IQR.
    Applied per gradient category — each category has its own distribution.
    """
    if len(paces) < 4:
        return paces  # too few data points for IQR

    q1, _, q3 = statistics.quantiles(paces, n=4)
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return [p for p in paces if lower <= p <= upper]


def calculate_percentiles(filtered_paces: list[float]) -> dict | None:
    """
    Calculate P25, P50 (median), P75 from already IQR-filtered data.

    Takes pre-filtered paces. IQR is already applied once in the main flow.
    """
    if not filtered_paces:
        return None

    if len(filtered_paces) < 3:
        median = statistics.median(filtered_paces)
        return {'p25': median, 'p50': median, 'p75': median}

    q1, q2, q3 = statistics.quantiles(filtered_paces, n=4)
    return {
        'p25': round(q1, 2),
        'p50': round(q2, 2),
        'p75': round(q3, 2),
    }


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
        from app.features.strava import StravaActivitySplit

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
        Classify gradient into one of 7 legacy categories.

        Delegates to shared.gradients.classify_gradient_legacy().
        """
        return classify_gradient_legacy(gradient_percent)

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

        Uses 11-category gradient system with IQR filtering and percentiles.
        Legacy 7-category fields filled via weighted average for backward compatibility.

        Args:
            user_id: User ID
            db: Database session

        Returns:
            UserRunProfile or None if insufficient data
        """
        from app.features.strava import StravaActivitySplit

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

        # 11-category classification (new)
        splits_by_category_11 = {cat: [] for cat in GRADIENT_THRESHOLDS}

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

            # Classify into 11 categories
            category = classify_gradient(gradient)
            splits_by_category_11[category].append(pace)

            # Collect uphill splits for threshold detection
            if gradient > 5:
                uphill_splits_for_threshold.append({
                    'gradient_percent': gradient,
                    'pace_min_km': pace
                })

        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} outlier run splits (pace outside {PACE_MIN_THRESHOLD_RUN}-{PACE_MAX_THRESHOLD_RUN} min/km)")

        # Calculate 11-category paces + percentiles with IQR filtering
        gradient_paces_json = {}
        gradient_percentiles_json = {}

        for category, paces in splits_by_category_11.items():
            if not paces:
                continue
            filtered = filter_outliers_iqr(paces)
            if not filtered:
                continue

            avg_pace = mean(filtered)
            percentiles = calculate_percentiles(filtered)

            gradient_paces_json[category] = {
                'avg': round(avg_pace, 2),
                'samples': len(filtered),
            }
            if percentiles:
                gradient_percentiles_json[category] = percentiles

            removed = len(paces) - len(filtered)
            if removed > 0:
                logger.info(
                    f"IQR {category}: {len(paces)} → {len(filtered)} samples "
                    f"({removed} outliers removed)"
                )

        # Build legacy 7-category paces (weighted average from 11-cat)
        legacy_paces = {}  # {legacy_name: [(avg, samples), ...]}
        for new_cat, data in gradient_paces_json.items():
            legacy_name = LEGACY_CATEGORY_MAPPING.get(new_cat)
            if legacy_name:
                legacy_paces.setdefault(legacy_name, []).append(
                    (data['avg'], data['samples'])
                )

        extended_paces = {}
        legacy_sample_counts = {}
        for legacy_name, entries in legacy_paces.items():
            total_samples = sum(s for _, s in entries)
            if total_samples > 0:
                weighted_avg = sum(avg * s for avg, s in entries) / total_samples
                extended_paces[legacy_name] = round(weighted_avg, 2)
                legacy_sample_counts[legacy_name] = total_samples
            else:
                extended_paces[legacy_name] = None
                legacy_sample_counts[legacy_name] = 0

        # Fill missing legacy categories with None
        for legacy_name in LEGACY_CATEGORY_MAPPING.values():
            extended_paces.setdefault(legacy_name, None)
            legacy_sample_counts.setdefault(legacy_name, 0)

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

        # Common profile data dict
        profile_data = dict(
            # Legacy 7-category avg paces (weighted from 11-cat)
            avg_flat_pace_min_km=extended_paces.get('flat'),
            avg_gentle_uphill_pace_min_km=extended_paces.get('gentle_uphill'),
            avg_moderate_uphill_pace_min_km=extended_paces.get('moderate_uphill'),
            avg_steep_uphill_pace_min_km=extended_paces.get('steep_uphill'),
            avg_gentle_downhill_pace_min_km=extended_paces.get('gentle_downhill'),
            avg_moderate_downhill_pace_min_km=extended_paces.get('moderate_downhill'),
            avg_steep_downhill_pace_min_km=extended_paces.get('steep_downhill'),
            # Legacy sample counts
            flat_sample_count=legacy_sample_counts.get('flat', 0),
            gentle_uphill_sample_count=legacy_sample_counts.get('gentle_uphill', 0),
            moderate_uphill_sample_count=legacy_sample_counts.get('moderate_uphill', 0),
            steep_uphill_sample_count=legacy_sample_counts.get('steep_uphill', 0),
            gentle_downhill_sample_count=legacy_sample_counts.get('gentle_downhill', 0),
            moderate_downhill_sample_count=legacy_sample_counts.get('moderate_downhill', 0),
            steep_downhill_sample_count=legacy_sample_counts.get('steep_downhill', 0),
            # 11-category JSON fields
            gradient_paces=gradient_paces_json,
            gradient_percentiles=gradient_percentiles_json,
            # Other fields
            walk_threshold_percent=walk_threshold,
            total_activities=len(activity_ids),
            total_distance_km=total_distance,
            total_elevation_m=total_elevation,
            last_calculated_at=datetime.utcnow(),
        )

        if profile:
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.updated_at = datetime.utcnow()
        else:
            profile = UserRunProfile(user_id=user_id, **profile_data)
            db.add(profile)

        await db.commit()
        await db.refresh(profile)

        logger.info(
            f"Calculated run profile for user {user_id}: "
            f"flat_pace={extended_paces.get('flat')}, "
            f"walk_threshold={walk_threshold}%, "
            f"activities={len(activity_ids)}, "
            f"11-cat categories={len(gradient_paces_json)}"
        )

        return profile

    @staticmethod
    def _detect_walk_threshold(uphill_splits: list[dict]) -> Optional[float]:
        """
        Detect walk threshold from uphill splits.

        Looks for gradient where pace suddenly jumps (indicating transition to walking).

        Args:
            uphill_splits: List of dicts with gradient_percent and pace_min_km

        Returns:
            Detected threshold (%) or None if not enough data to detect.
            When None, the service will use DEFAULT_HIKE_THRESHOLD_PERCENT.
        """
        MIN_THRESHOLD = DEFAULT_HIKE_THRESHOLD_PERCENT
        MAX_THRESHOLD = 35.0

        # Not enough data to detect - return None (will use constant default)
        if len(uphill_splits) < 10:
            return None

        # Sort by gradient
        sorted_splits = sorted(uphill_splits, key=lambda x: x['gradient_percent'])

        # Find steepest pace derivative (where pace jumps most)
        max_derivative = 0
        detected_threshold = None

        for i in range(1, len(sorted_splits)):
            prev = sorted_splits[i - 1]
            curr = sorted_splits[i]

            pace_change = curr['pace_min_km'] - prev['pace_min_km']
            gradient_change = curr['gradient_percent'] - prev['gradient_percent']

            if gradient_change > 0 and pace_change > 0:
                derivative = pace_change / gradient_change
                if derivative > max_derivative:
                    max_derivative = derivative
                    detected_threshold = (prev['gradient_percent'] + curr['gradient_percent']) / 2

        # If no clear threshold found, return None
        if detected_threshold is None:
            return None

        # Clamp to reasonable range
        detected_threshold = max(MIN_THRESHOLD, min(MAX_THRESHOLD, detected_threshold))
        return round(detected_threshold, 1)

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
