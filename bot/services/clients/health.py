"""Health check API client."""
import logging

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class HealthClient(BaseAPIClient):
    """Client for health check endpoints."""

    async def check(self) -> bool:
        """Check if backend is healthy."""
        try:
            session = await self._get_session()
            url = f"{self.base_url}/health"

            async with session.get(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
