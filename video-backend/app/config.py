"""Application configuration.

Values come from environment variables (and, in production, Modal Secrets).
Never hard-code the approved account, client ID, or any secret in source.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # --- Upload / validation limits (all cost guardrails) ----------------
    max_upload_bytes: int = Field(default=300 * MB)
    max_duration_seconds: float = Field(default=90.0)
    # Per-frame pixel ceiling, ~1080p in either orientation.
    max_input_pixels: int = Field(default=2_100_000)
    # Slow-motion sources (120/240 fps) multiply GPU cost; cap at 60 fps
    # (61 tolerates 59.94-NTSC rounding).
    max_fps: float = Field(default=61.0)

    # --- Storage / retention --------------------------------------------
    data_dir: str = Field(default="./video-backend/.data")
    retention_hours: int = Field(default=24)

    # --- Misc ------------------------------------------------------------
    api_version: str = Field(default="1.0.0")


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the env is read once per process."""
    return Settings()
