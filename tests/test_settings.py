from __future__ import annotations

import pytest
from src.config import get_settings
from src.config.settings import AppEnv


def test_defaults_load(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    assert s.app_env is AppEnv.DEVELOPMENT
    assert s.database_url.startswith("sqlite:///")
    assert s.redis_url.startswith("redis://")


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import settings as settings_mod

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@c/d")
    settings_mod.get_settings.cache_clear()

    s = get_settings()
    assert s.is_production
    assert s.database_url == "postgresql+psycopg://a:b@c/d"


def test_secrets_are_secretstr() -> None:
    s = get_settings()
    # A default empty secret should still be a SecretStr, not bare str.
    assert s.discord_bot_token.get_secret_value() == ""
    assert "SecretStr" in type(s.discord_bot_token).__name__
