"""Shared pytest fixtures.

Every test gets a fresh in-memory SQLite database so model changes and
migration-equivalent schema writes don't leak between tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate each test from the developer's real .env."""

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("PERSONAL_INFO_PATH", str(tmp_path / "personal.yaml"))
    # Clear the lru_cache on Settings so each test re-reads env
    from src.config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    yield
    settings_mod.get_settings.cache_clear()


@pytest.fixture
def db_session() -> Iterator[Session]:  # type: ignore[name-defined]  # noqa: F821
    """Provide a transactional SQLAlchemy session against a fresh schema."""

    # Import lazily so the env-var monkeypatch above takes effect before
    # the engine is built.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.db import models  # noqa: F401  — register mappers
    from src.db.base import Base

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def personal_yaml(tmp_path: Path) -> Path:
    """Write a minimal valid personal.yaml and return its path."""

    content = """
full_name: "Jane Doe"
email: "jane@example.com"
phone: "+1-555-000-0000"
location: "New York, NY"
work_authorization: us_citizen

education:
  university: "Example University"
  degree: "B.S."
  major: "Mathematics"
  gpa: 3.9
  graduation_date: 2026-05-15

resume_variants:
  - name: quant
    file_path: "resumes/quant.pdf"
    description: "Quant-focused."
  - name: tech
    file_path: "resumes/tech.pdf"
    description: "Tech-focused."
"""
    p = tmp_path / "personal.yaml"
    p.write_text(content, encoding="utf-8")
    return p
