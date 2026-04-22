"""Runtime settings sourced from environment variables / ``.env``.

Only secrets and deployment-specific knobs live here. User profile data
(name, resume paths, experiences, etc.) is loaded separately from a YAML
file via :mod:`src.config.personal`.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Environment-backed configuration.

    All fields map to uppercase environment variables of the same name
    (e.g. ``DATABASE_URL``). Optional secrets default to empty
    :class:`SecretStr` values so the app can boot in phases where a
    given integration is not yet wired up.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_env: AppEnv = Field(default=AppEnv.DEVELOPMENT, alias="APP_ENV")

    # Profile
    personal_info_path: Path = Field(
        default=Path("config/personal.yaml"),
        alias="PERSONAL_INFO_PATH",
    )
    sources_config_path: Path = Field(
        default=Path("config/sources.yaml"),
        alias="SOURCES_CONFIG_PATH",
    )

    # Persistence
    database_url: str = Field(
        default="sqlite:///./data/app.db",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Discord (Phase 5)
    discord_bot_token: SecretStr = Field(default=SecretStr(""), alias="DISCORD_BOT_TOKEN")
    discord_guild_id: str = Field(default="", alias="DISCORD_GUILD_ID")
    discord_webhook_job_alerts: SecretStr = Field(
        default=SecretStr(""), alias="DISCORD_WEBHOOK_JOB_ALERTS"
    )
    discord_webhook_job_review: SecretStr = Field(
        default=SecretStr(""), alias="DISCORD_WEBHOOK_JOB_REVIEW"
    )
    discord_webhook_status_updates: SecretStr = Field(
        default=SecretStr(""), alias="DISCORD_WEBHOOK_STATUS_UPDATES"
    )
    discord_webhook_daily_digest: SecretStr = Field(
        default=SecretStr(""), alias="DISCORD_WEBHOOK_DAILY_DIGEST"
    )

    # LLM (Phase 4 — deferred)
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    anthropic_api_key: SecretStr = Field(default=SecretStr(""), alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")

    # Gmail (Phase 6)
    gmail_credentials_path: Path = Field(
        default=Path("config/gmail_credentials.json"),
        alias="GMAIL_CREDENTIALS_PATH",
    )
    gmail_token_path: Path = Field(
        default=Path("config/gmail_token.json"),
        alias="GMAIL_TOKEN_PATH",
    )

    # Scraping (Phase 1)
    proxy_url: str = Field(default="", alias="PROXY_URL")
    linkedin_storage_state_path: Path = Field(
        default=Path("config/linkedin_state.json"),
        alias="LINKEDIN_STORAGE_STATE_PATH",
    )
    handshake_storage_state_path: Path = Field(
        default=Path("config/handshake_state.json"),
        alias="HANDSHAKE_STORAGE_STATE_PATH",
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` instance.

    Cached so repeated imports do not re-read ``.env``. Call
    :func:`Settings.model_rebuild` or clear this cache in tests if you
    need to reload.
    """

    return Settings()
