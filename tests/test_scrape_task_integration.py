"""End-to-end test for :func:`src.tasks.scrape.run_all_sync`.

Uses a mock httpx transport via monkeypatch so no network calls happen,
and a fresh in-memory SQLite database so the persistence path is exercised.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings as settings_mod
from src.db import models  # noqa: F401
from src.db.base import Base
from src.db.models import Job


@pytest.fixture
def sources_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "sources.yaml"
    p.write_text(
        """
defaults:
  locations: ["United States", "Remote"]
companies:
  - name: "Acme"
    ats: greenhouse
    board_id: "acme"
    enabled: true
  - name: "Zeta"
    ats: greenhouse
    board_id: "zeta"
    enabled: false
""",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def patched_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point ``src.db.base.engine`` and ``SessionLocal`` at a tmp SQLite DB."""

    db_path = tmp_path / "e2e.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_mod.get_settings.cache_clear()

    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    from src.db import base as db_base

    monkeypatch.setattr(db_base, "engine", engine)
    monkeypatch.setattr(
        db_base,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True),
    )
    yield engine
    engine.dispose()


@pytest.fixture
def mock_greenhouse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch :class:`GreenhouseScraper` so its internal client uses a MockTransport."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "jobs": [
                {
                    "id": 1,
                    "title": "Software Engineer New Grad",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                    "location": {"name": "New York, NY"},
                    "content": "<p>JD</p>",
                },
                {
                    "id": 2,
                    "title": "Senior Staff Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                    "location": {"name": "London, UK"},  # Will be filtered out.
                    "content": "<p>JD</p>",
                },
            ]
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)

    # Monkeypatch the scraper's client factory to always use our transport.
    from src.scrapers import greenhouse as gh

    original_init = gh.GreenhouseScraper.__init__

    def patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("http_client", None)
        original_init(self, *args, **kwargs)
        self._client = httpx.AsyncClient(transport=transport)
        self._own_client = True  # will be closed after fetch

    monkeypatch.setattr(gh.GreenhouseScraper, "__init__", patched_init)


def test_run_all_sync_persists_filtered_results(
    sources_yaml: Path,
    patched_engine,
    mock_greenhouse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCES_CONFIG_PATH", str(sources_yaml))
    settings_mod.get_settings.cache_clear()

    from src.tasks.scrape import run_all_sync

    results = run_all_sync()
    assert len(results) == 1
    r = results[0]
    assert r.source == "greenhouse:acme"
    assert r.fetched == 2
    assert r.filtered == 1  # London dropped
    assert r.persisted == 1  # only NYC one saved
    assert r.errors == 0

    # Dedup: running again should persist zero new rows.
    results_2 = run_all_sync()
    assert results_2[0].persisted == 0

    Session = sessionmaker(bind=patched_engine, future=True)
    with Session() as s:
        jobs = s.query(Job).all()
        assert len(jobs) == 1
        assert jobs[0].company == "Acme"
        assert jobs[0].title.endswith("New Grad")
