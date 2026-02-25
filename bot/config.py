"""
Bot Configuration

Settings loaded from environment variables.
"""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Bot settings."""

    bot_token: str
    backend_url: str = "http://localhost:8000"

    debug: bool = False
    log_level: str = "INFO"

    # File limits
    max_file_size_mb: int = 20

    # Cross-service integration (Strava OAuth proxy via ayda_run)
    ayda_run_api_url: Optional[str] = None
    cross_service_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
