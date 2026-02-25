"""Races API client."""

import logging
from typing import Optional

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class RacesClient(BaseAPIClient):
    """Client for races API endpoints."""

    async def list_races(self) -> Optional[list[dict]]:
        """Get all races from catalog."""
        return await self._get_optional("/api/v1/races")

    async def get_race(self, race_id: str) -> Optional[dict]:
        """Get single race details."""
        return await self._get_optional(f"/api/v1/races/{race_id}")

    async def get_results(self, race_id: str, year: int) -> Optional[list[dict]]:
        """Get race results for a specific year."""
        return await self._get_optional(f"/api/v1/races/{race_id}/{year}/results")

    async def search(
        self,
        race_id: str,
        name: str,
        distance_id: Optional[str] = None,
    ) -> Optional[list[dict]]:
        """Search participant by name across all years."""
        params = {"name": name}
        if distance_id:
            params["distance_id"] = distance_id
        return await self._get_optional(
            f"/api/v1/races/{race_id}/search", params=params
        )

    async def predict(
        self,
        race_id: str,
        distance_id: str,
        flat_pace_min_km: float,
        mode: str = "trail_run",
        telegram_id: Optional[int] = None,
    ) -> Optional[dict]:
        """Predict race time."""
        payload = {
            "distance_id": distance_id,
            "flat_pace_min_km": flat_pace_min_km,
            "mode": mode,
        }
        if telegram_id:
            payload["telegram_id"] = telegram_id
        return await self._post_optional(
            f"/api/v1/races/{race_id}/predict", json=payload
        )
