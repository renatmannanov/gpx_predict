"""
Hiking module exports.

For predictions, use app.services.prediction.PredictionService
which orchestrates both hiking and trail_run calculations.
"""

# Re-export schemas for convenience
from .schemas import HikePredictRequest, HikePrediction

__all__ = ["HikePredictRequest", "HikePrediction"]
