"""Base API client with common HTTP logic."""
import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API error."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"API error {status}: {detail}")


class BaseAPIClient:
    """Base class for API clients."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def _get(self, path: str, **kwargs) -> dict[str, Any]:
        """Make GET request."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        async with session.get(url, **kwargs) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                raise APIError(resp.status, detail)
            return data

    async def _get_optional(self, path: str, **kwargs) -> Optional[dict[str, Any]]:
        """Make GET request, return None on error."""
        try:
            return await self._get(path, **kwargs)
        except APIError:
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    async def _post(self, path: str, **kwargs) -> dict[str, Any]:
        """Make POST request."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        async with session.post(url, **kwargs) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                raise APIError(resp.status, detail)
            return data

    async def _post_optional(self, path: str, **kwargs) -> Optional[dict[str, Any]]:
        """Make POST request, return None on error."""
        try:
            return await self._post(path, **kwargs)
        except APIError:
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    async def _put(self, path: str, **kwargs) -> dict[str, Any]:
        """Make PUT request."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        async with session.put(url, **kwargs) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                raise APIError(resp.status, detail)
            return data

    async def _post_form(self, path: str, form: aiohttp.FormData) -> dict[str, Any]:
        """Make POST request with form data."""
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        async with session.post(url, data=form) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", "Unknown error")
                raise APIError(resp.status, detail)
            return data

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
