"""
Trail run profile repository.

Data access layer for UserRunProfile model.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.repository import BaseRepository
from .models import UserRunProfile


class TrailRunProfileRepository(BaseRepository[UserRunProfile]):
    """Repository for trail run profile operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, UserRunProfile)

    async def get_by_user_id(self, user_id: str) -> UserRunProfile | None:
        """
        Get run profile for user.

        Args:
            user_id: User's ID

        Returns:
            UserRunProfile if found, None otherwise
        """
        return await self.get_by(user_id=user_id)

    async def get_or_create(self, user_id: str) -> UserRunProfile:
        """
        Get existing or create empty profile.

        Args:
            user_id: User's ID

        Returns:
            Run profile for user
        """
        profile = await self.get_by_user_id(user_id)
        if not profile:
            profile = await self.create(user_id=user_id)
        return profile

    async def update_paces(
        self,
        profile: UserRunProfile,
        flat_pace: float | None = None,
        **gradient_paces
    ) -> UserRunProfile:
        """
        Update pace metrics.

        Args:
            profile: Profile to update
            flat_pace: Flat terrain pace (min/km)
            **gradient_paces: Gradient-specific paces

        Returns:
            Updated profile
        """
        update_data = {"last_calculated_at": datetime.utcnow()}

        if flat_pace is not None:
            update_data["avg_flat_pace_min_km"] = flat_pace

        # Gradient paces
        gradient_fields = [
            "avg_gentle_uphill_pace_min_km",
            "avg_moderate_uphill_pace_min_km",
            "avg_steep_uphill_pace_min_km",
            "avg_gentle_downhill_pace_min_km",
            "avg_moderate_downhill_pace_min_km",
            "avg_steep_downhill_pace_min_km",
        ]
        for field in gradient_fields:
            if field in gradient_paces and gradient_paces[field] is not None:
                update_data[field] = gradient_paces[field]

        return await self.update(profile, **update_data)

    async def update_sample_counts(
        self,
        profile: UserRunProfile,
        **counts
    ) -> UserRunProfile:
        """
        Update sample counts for gradient categories.

        Args:
            profile: Profile to update
            **counts: Sample counts per category

        Returns:
            Updated profile
        """
        count_fields = [
            "flat_sample_count",
            "gentle_uphill_sample_count",
            "moderate_uphill_sample_count",
            "steep_uphill_sample_count",
            "gentle_downhill_sample_count",
            "moderate_downhill_sample_count",
            "steep_downhill_sample_count",
        ]
        update_data = {}
        for field in count_fields:
            if field in counts and counts[field] is not None:
                update_data[field] = counts[field]

        if update_data:
            return await self.update(profile, **update_data)
        return profile

    async def update_stats(
        self,
        profile: UserRunProfile,
        total_activities: int,
        total_distance_km: float,
        total_elevation_m: float
    ) -> UserRunProfile:
        """
        Update profile statistics.

        Args:
            profile: Profile to update
            total_activities: Total activities analyzed
            total_distance_km: Total distance in km
            total_elevation_m: Total elevation gain in meters

        Returns:
            Updated profile
        """
        return await self.update(
            profile,
            total_activities=total_activities,
            total_distance_km=total_distance_km,
            total_elevation_m=total_elevation_m,
            last_calculated_at=datetime.utcnow()
        )

    async def update_walk_threshold(
        self,
        profile: UserRunProfile,
        walk_threshold_percent: float
    ) -> UserRunProfile:
        """
        Update walk threshold.

        Args:
            profile: Profile to update
            walk_threshold_percent: Walk threshold percentage

        Returns:
            Updated profile
        """
        return await self.update(
            profile,
            walk_threshold_percent=walk_threshold_percent,
            last_calculated_at=datetime.utcnow()
        )
