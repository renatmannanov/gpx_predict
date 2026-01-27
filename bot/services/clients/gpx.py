"""GPX file API client."""
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from .base import BaseAPIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class GPXInfo:
    """GPX file information."""

    gpx_id: str
    filename: str
    name: Optional[str]
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_elevation_m: float
    min_elevation_m: float
    is_loop: bool = False


class GPXClient(BaseAPIClient):
    """Client for GPX file endpoints."""

    async def upload(self, filename: str, content: bytes) -> GPXInfo:
        """
        Upload a GPX file to the backend.

        Args:
            filename: Original filename
            content: File content as bytes

        Returns:
            GPXInfo with file metadata

        Raises:
            APIError: If upload fails
        """
        form = aiohttp.FormData()
        form.add_field(
            "file",
            content,
            filename=filename,
            content_type="application/gpx+xml"
        )

        logger.info(f"Uploading GPX: {filename}")

        data = await self._post_form("/api/v1/gpx/upload", form)

        info = data["info"]
        return GPXInfo(
            gpx_id=data["gpx_id"],
            filename=info["filename"],
            name=info.get("name"),
            distance_km=info["distance_km"],
            elevation_gain_m=info["elevation_gain_m"],
            elevation_loss_m=info["elevation_loss_m"],
            max_elevation_m=info["max_elevation_m"],
            min_elevation_m=info["min_elevation_m"],
            is_loop=info.get("is_loop", False),
        )
