"""
Hiking profile repository.

Data access layer for UserHikingProfile model.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.repository import BaseRepository
from .models import UserHikingProfile


class HikingProfileRepository(BaseRepository[UserHikingProfile]):
    """Repository for hiking profile operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, UserHikingProfile)

    async def get_by_user_id(self, user_id: str) -> UserHikingProfile | None:
        """
        Get hiking profile for user.

        Args:
            user_id: User's ID

        Returns:
            UserHikingProfile if found, None otherwise
        """
        return await self.get_by(user_id=user_id)

    async def get_or_create(self, user_id: str) -> UserHikingProfile:
        """
        Get existing or create empty profile.

        Args:
            user_id: User's ID

        Returns:
            Hiking profile for user
        """
        profile = await self.get_by_user_id(user_id)
        if not profile:
            profile = await self.create(user_id=user_id)
        return profile

    async def update_paces(
        self,
        profile: UserHikingProfile,
        flat_pace: float | None = None,
        uphill_pace: float | None = None,
        downhill_pace: float | None = None,
        **extended_paces
    ) -> UserHikingProfile:
        """
        Update pace metrics.

        Args:
            profile: Profile to update
            flat_pace: Flat terrain pace (min/km)
            uphill_pace: Uphill pace (min/km)
            downhill_pace: Downhill pace (min/km)
            **extended_paces: Extended gradient paces (7-category system)

        Returns:
            Updated profile
        """
        update_data = {"last_calculated_at": datetime.utcnow()}

        if flat_pace is not None:
            update_data["avg_flat_pace_min_km"] = flat_pace
        if uphill_pace is not None:
            update_data["avg_uphill_pace_min_km"] = uphill_pace
        if downhill_pace is not None:
            update_data["avg_downhill_pace_min_km"] = downhill_pace

        # Extended gradient paces
        extended_fields = [
            "avg_steep_downhill_pace_min_km",
            "avg_moderate_downhill_pace_min_km",
            "avg_gentle_downhill_pace_min_km",
            "avg_gentle_uphill_pace_min_km",
            "avg_moderate_uphill_pace_min_km",
            "avg_steep_uphill_pace_min_km",
        ]
        for field in extended_fields:
            if field in extended_paces and extended_paces[field] is not None:
                update_data[field] = extended_paces[field]

        return await self.update(profile, **update_data)

    async def update_stats(
        self,
        profile: UserHikingProfile,
        total_activities: int,
        hike_activities: int,
        total_distance_km: float,
        total_elevation_m: float
    ) -> UserHikingProfile:
        """
        Update profile statistics.

        Args:
            profile: Profile to update
            total_activities: Total activities analyzed
            hike_activities: Hike activities analyzed
            total_distance_km: Total distance in km
            total_elevation_m: Total elevation gain in meters

        Returns:
            Updated profile
        """
        return await self.update(
            profile,
            total_activities_analyzed=total_activities,
            total_hike_activities=hike_activities,
            total_distance_km=total_distance_km,
            total_elevation_m=total_elevation_m,
            last_calculated_at=datetime.utcnow()
        )

    async def update_vertical_ability(
        self,
        profile: UserHikingProfile,
        vertical_ability: float
    ) -> UserHikingProfile:
        """
        Update vertical ability coefficient.

        Args:
            profile: Profile to update
            vertical_ability: Vertical ability coefficient

        Returns:
            Updated profile
        """
        return await self.update(
            profile,
            vertical_ability=vertical_ability,
            last_calculated_at=datetime.utcnow()
        )
