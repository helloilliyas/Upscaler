"""Application configuration.

Values come from environment variables (and, in production, Modal Secrets).
Never hard-code the approved account, client ID, or any secret in source.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Formats the backend is willing to decode and process.
ALLOWED_FORMATS: frozenset[str] = frozenset({"JPEG", "PNG", "WEBP"})

MB = 1024 * 1024


class Settings(BaseSettings):
    """Runtime configuration, populated from the environment."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # --- Identity / auth -------------------------------------------------
    google_web_client_id: str = Field(
        default="",
        description="Web OAuth client ID; the audience the Android ID token targets.",
    )
    allowed_google_email: str = Field(
        default="",
        description="The single approved personal Google account email.",
    )
    allowed_google_sub: str = Field(
        default="",
        description="Stable Google subject id of the approved account (set after first sign-in).",
    )

    # --- Upload / validation limits -------------------------------------
    max_upload_bytes: int = Field(default=40 * MB)
    max_input_pixels: int = Field(default=50_000_000)  # 50 megapixels

    # --- Storage / retention --------------------------------------------
    data_dir: str = Field(default="./backend/.data")
    retention_hours: int = Field(default=24)

    # --- Cost / concurrency controls ------------------------------------
    max_concurrent_standard: int = Field(default=2)
    max_concurrent_ultra: int = Field(default=1)
    max_batch_photos: int = Field(default=50)

    # --- Misc ------------------------------------------------------------
    api_version: str = Field(default="1.0.0")

    @property
    def allowed_formats(self) -> frozenset[str]:
        return ALLOWED_FORMATS


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the env is read once per process."""
    return Settings()
