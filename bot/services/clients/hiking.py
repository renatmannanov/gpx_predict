"""Hiking prediction API client."""
import logging
from dataclasses import dataclass
from typing import Optional

from .base import BaseAPIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class TimeBreakdown:
    """Breakdown of estimated time."""

    moving_time_hours: float
    rest_time_hours: float
    lunch_time_hours: float


@dataclass
class HikePrediction:
    """Hike prediction result."""

    estimated_time_hours: float
    safe_time_hours: float
    recommended_start: str
    recommended_turnaround: Optional[str]
    warnings: list
    experience_multiplier: float
    backpack_multiplier: float
    group_multiplier: float
    total_multiplier: float
    time_breakdown: Optional[TimeBreakdown] = None
    personalized: bool = False
    activities_used: int = 0


class HikingClient(BaseAPIClient):
    """Client for hiking prediction endpoints."""

    async def predict(
        self,
        gpx_id: str,
        experience: str = "casual",
        backpack: str = "medium",
        group_size: int = 1,
        has_children: bool = False,
        has_elderly: bool = False,
        is_round_trip: bool = False,
        telegram_id: Optional[int] = None,
    ) -> HikePrediction:
        """
        Get hike prediction from backend.

        Args:
            gpx_id: ID of uploaded GPX file
            experience: Experience level
            backpack: Backpack weight
            group_size: Number of people
            has_children: Has children in group
            has_elderly: Has elderly in group
            is_round_trip: If route is out-and-back
            telegram_id: Optional Telegram ID for personalized prediction

        Returns:
            HikePrediction with time estimates

        Raises:
            APIError: If prediction fails
        """
        payload = {
            "gpx_id": gpx_id,
            "experience": experience,
            "backpack": backpack,
            "group_size": group_size,
            "has_children": has_children,
            "has_elderly": has_elderly,
            "is_round_trip": is_round_trip,
        }

        if telegram_id:
            payload["telegram_id"] = telegram_id

        logger.info(f"Requesting prediction for GPX: {gpx_id}, personalized={telegram_id is not None}")

        data = await self._post("/api/v1/predict/hike", json=payload)

        # Parse time breakdown
        time_breakdown = None
        if data.get("time_breakdown"):
            tb = data["time_breakdown"]
            time_breakdown = TimeBreakdown(
                moving_time_hours=tb["moving_time_hours"],
                rest_time_hours=tb["rest_time_hours"],
                lunch_time_hours=tb["lunch_time_hours"],
            )

        return HikePrediction(
            estimated_time_hours=data["estimated_time_hours"],
            safe_time_hours=data["safe_time_hours"],
            recommended_start=data["recommended_start"],
            recommended_turnaround=data.get("recommended_turnaround"),
            warnings=data.get("warnings", []),
            experience_multiplier=data.get("experience_multiplier", 1.0),
            backpack_multiplier=data.get("backpack_multiplier", 1.0),
            group_multiplier=data.get("group_multiplier", 1.0),
            total_multiplier=data.get("total_multiplier", 1.0),
            time_breakdown=time_breakdown,
            personalized=data.get("personalized", False),
            activities_used=data.get("activities_used", 0),
        )

    async def compare_methods(
        self,
        gpx_id: str,
        experience: str = "regular",
        backpack: str = "light",
        group_size: int = 1,
        telegram_id: Optional[int] = None,
    ) -> dict:
        """
        Compare different prediction methods on a route.

        Args:
            gpx_id: ID of uploaded GPX file
            experience: Experience level
            backpack: Backpack weight
            group_size: Number of people
            telegram_id: Optional Telegram ID for personalized comparison

        Returns:
            RouteComparison with segment breakdown and totals

        Raises:
            APIError: If comparison fails
        """
        payload = {
            "gpx_id": gpx_id,
            "experience": experience,
            "backpack": backpack,
            "group_size": group_size,
        }

        if telegram_id:
            payload["telegram_id"] = telegram_id

        logger.info(f"Requesting comparison for GPX: {gpx_id}, personalized={telegram_id is not None}")

        return await self._post("/api/v1/predict/compare", json=payload)
