"""
Hiking prediction service.

Main entry point for hiking time predictions.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import HikePredictRequest, HikePrediction


class HikingPredictionService:
    """
    Service for hiking time predictions.

    Usage:
        service = HikingPredictionService(db)
        prediction = await service.predict(request)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def predict(self, request: HikePredictRequest) -> HikePrediction:
        """
        Make hiking time prediction.

        TODO: Extract logic from services/prediction.py
        """
        # Placeholder - will be implemented by extracting from prediction.py
        raise NotImplementedError("Will be implemented in Phase 6")
