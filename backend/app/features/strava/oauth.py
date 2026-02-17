"""
Strava OAuth flow.

Handles:
- Authorization URL generation
- Code exchange for tokens
- Token refresh
- Token revocation (deauthorization)
"""

import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class StravaOAuthError(Exception):
    """OAuth-related error."""
    pass


class StravaOAuth:
    """
    Strava OAuth handler.

    Usage:
        oauth = StravaOAuth()
        auth_url = oauth.get_authorization_url(
            redirect_uri="https://example.com/callback",
            state="user_123"
        )
        tokens = await oauth.exchange_code(code)
        tokens = await oauth.refresh_token(refresh_token)
    """

    BASE_URL = "https://www.strava.com"
    AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
    TOKEN_URL = "https://www.strava.com/oauth/token"
    DEAUTHORIZE_URL = "https://www.strava.com/oauth/deauthorize"

    def __init__(self):
        self.client_id = settings.strava_client_id
        self.client_secret = settings.strava_client_secret

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        scope: str = "activity:read"
    ) -> str:
        """
        Generate Strava OAuth authorization URL.

        Args:
            redirect_uri: URL to redirect after authorization
            state: Optional state parameter for CSRF protection
            scope: OAuth scope (default: activity:read)

        Scopes:
        - activity:read - View activities (excluding private)
        - activity:read_all - View all activities (including private)
        - profile:read_all - View complete profile

        We only request activity:read for privacy.

        Returns:
            Authorization URL string
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "approval_prompt": "auto"  # "force" to always show consent
        }
        if state:
            params["state"] = state

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from Strava callback

        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "expires_at": 1234567890,
                "athlete": {"id": 123, "firstname": "...", ...}
            }

        Raises:
            StravaOAuthError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code"
                }
            )

            if response.status_code != 200:
                logger.error(f"Strava token exchange failed: {response.text}")
                raise StravaOAuthError(
                    f"Token exchange failed: {response.status_code}"
                )

            return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        """
        Refresh an expired access token.

        Args:
            refresh_token: Current refresh token

        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "expires_at": 1234567890
            }

        Raises:
            StravaOAuthError: If token refresh fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )

            if response.status_code != 200:
                logger.error(f"Strava token refresh failed: {response.text}")
                raise StravaOAuthError(
                    f"Token refresh failed: {response.status_code}"
                )

            return response.json()

    async def deauthorize(self, access_token: str) -> bool:
        """
        Revoke Strava access (user disconnect).

        Args:
            access_token: Current access token to revoke

        Returns:
            True if deauthorization was successful
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.DEAUTHORIZE_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.status_code == 200


# =============================================================================
# Standalone Functions (for backward compatibility)
# =============================================================================

async def exchange_authorization_code(code: str) -> dict:
    """
    Exchange authorization code for tokens.

    Standalone function that doesn't require instantiation.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "...",
            "expires_at": 1234567890,
            "athlete": {"id": 123, "firstname": "...", ...}
        }
    """
    oauth = StravaOAuth()
    return await oauth.exchange_code(code)


async def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh an expired access token.

    Standalone function that doesn't require instantiation.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "...",
            "expires_at": 1234567890
        }
    """
    oauth = StravaOAuth()
    return await oauth.refresh_token(refresh_token)


async def revoke_access(access_token: str) -> bool:
    """
    Revoke Strava access.

    Standalone function that doesn't require instantiation.
    """
    oauth = StravaOAuth()
    return await oauth.deauthorize(access_token)
