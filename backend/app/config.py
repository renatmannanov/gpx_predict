"""
Application Configuration

Uses Pydantic Settings for type-safe configuration.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    # === Core ===
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # === Database ===
    database_url: str = Field(
        default="sqlite:///./app.db",
        description="Database connection URL"
    )

    # === CORS ===
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins"
    )

    # === Elevation API ===
    elevation_api_url: str = Field(
        default="https://api.open-elevation.com/api/v1/lookup",
        description="Elevation API endpoint"
    )

    # === Rate Limiting ===
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100)
    rate_limit_period: int = Field(default=60)

    # === Strava ===
    strava_client_id: Optional[str] = Field(default=None)
    strava_client_secret: Optional[str] = Field(
        default=None,
        validation_alias="strava_secret"  # Also accept STRAVA_SECRET
    )
    strava_webhook_verify_token: Optional[str] = Field(default=None)

    @field_validator('database_url')
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        """Fix Render/Railway postgres:// URL to postgresql://"""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
