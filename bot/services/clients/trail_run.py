"""Trail run prediction API client."""
import logging
from typing import Optional

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class TrailRunClient(BaseAPIClient):
    """Client for trail run prediction endpoints."""

    async def predict(
        self,
        gpx_id: str,
        telegram_id: Optional[str] = None,
        gap_mode: str = "strava_gap",
        flat_pace_min_km: Optional[float] = None,
        apply_fatigue: bool = False,
        walk_threshold_override: Optional[float] = None,
    ) -> Optional[dict]:
        """
        Get trail run prediction.

        Args:
            gpx_id: ID of uploaded GPX file
            telegram_id: User's Telegram ID for personalization
            gap_mode: GAP calculation mode ("strava_gap" or "minetti_gap")
            flat_pace_min_km: Base flat pace (uses profile if not set)
            apply_fatigue: Whether to apply fatigue model
            walk_threshold_override: Override walk threshold %

        Returns:
            Prediction dict or None on error
        """
        payload = {
            "gpx_id": gpx_id,
            "gap_mode": gap_mode,
            "apply_fatigue": apply_fatigue,
            "use_extended_gradients": True,
        }

        if telegram_id:
            payload["telegram_id"] = telegram_id
        if flat_pace_min_km:
            payload["flat_pace_min_km"] = flat_pace_min_km
        if walk_threshold_override:
            payload["walk_threshold_override"] = walk_threshold_override

        logger.info(f"Requesting trail run prediction for GPX: {gpx_id}")

        return await self._post_optional("/api/v1/predict/trail-run/compare", json=payload)
