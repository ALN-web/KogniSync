"""Application settings, read from environment variables and the repo-root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "KogniSync API"
    app_env: str = "local"
    version: str = "0.1.0"
    log_level: str = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # Secrets are SecretStr so they never appear in logs or reprs.
    gemini_api_key: SecretStr | None = None
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None
    # Signs TripPass QR tokens. Required in production; a random per-process key is used
    # locally if unset (passes then stop verifying after a restart).
    trippass_signing_key: SecretStr | None = None

    # Gemini model ids are configurable so they can follow new releases without code changes.
    gemini_model: str = "gemini-2.5-flash"
    gemini_omni_model: str = "gemini-2.5-flash"

    hold_ttl_seconds: int = 600
    # Lets the demo inject disruptions through the API. Turn off in production.
    enable_simulation: bool = True
    # Per-client requests per minute on the AI endpoints (protects Gemini spend).
    copilot_rate_limit_per_min: int = 20

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @field_validator(
        "gemini_api_key", "database_url", "redis_url", "trippass_signing_key", mode="before"
    )
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
