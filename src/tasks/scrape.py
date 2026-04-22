"""Scrape tasks.

- :func:`dispatch_api_scrapes` (beat: every 5 min) fans out one
  ``run_scraper`` task per enabled Greenhouse/Lever company.
- :func:`dispatch_browser_scrapes` (beat: every 15 min) fans out one
  task per enabled Workday / Custom company + LinkedIn/Handshake search.
- :func:`run_scraper` is the actual work: instantiate scraper, fetch,
  filter by location/department, upsert. Returns a serialized
  :class:`ScrapeResult`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import Task

from src.config import get_settings, load_sources_config
from src.config.sources import CompanyConfig, SourcesConfig
from src.db.base import SessionLocal
from src.scrapers.base import ScrapeResult
from src.scrapers.location import filter_by_departments, filter_by_locations
from src.scrapers.persistence import upsert_jobs
from src.scrapers.registry import (
    is_api_based,
    make_company_scraper,
    make_handshake_scrapers,
    make_linkedin_scrapers,
)
from src.tasks.app import celery_app

logger = logging.getLogger(__name__)


def _load_sources() -> SourcesConfig:
    return load_sources_config(get_settings().sources_config_path)


@celery_app.task(
    name="src.tasks.scrape.run_scraper",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    rate_limit="20/m",
)
def run_scraper(
    self: Task,
    *,
    kind: str,  # "company" | "linkedin" | "handshake"
    company_name: str | None = None,
    search_index: int | None = None,
) -> dict[str, Any]:
    """Run exactly one scraper and persist its output.

    Dispatching code addresses scrapers symbolically (company name or
    search index) so task arguments are JSON-serializable.
    """

    sources = _load_sources()

    if kind == "company":
        assert company_name is not None
        entry = _find_company(sources, company_name)
        scraper = make_company_scraper(entry)
        allowed_locs = sources.effective_locations_for(entry)
        allowed_depts = entry.departments
    elif kind == "linkedin":
        assert search_index is not None
        scrapers = make_linkedin_scrapers(sources.linkedin)
        scraper = scrapers[search_index]
        allowed_locs = (
            sources.linkedin.searches[search_index].locations or sources.defaults.locations
        )
        allowed_depts = []
    elif kind == "handshake":
        assert search_index is not None
        scrapers = make_handshake_scrapers(sources.handshake)
        scraper = scrapers[search_index]
        allowed_locs = (
            sources.handshake.searches[search_index].locations or sources.defaults.locations
        )
        allowed_depts = []
    else:
        raise ValueError(f"Unknown scraper kind {kind!r}")

    async def _run() -> ScrapeResult:
        result, payloads = await scraper.run()
        kept, dropped_loc = filter_by_locations(payloads, allowed_locs)
        kept, dropped_dept = filter_by_departments(kept, allowed_depts)
        result.filtered = dropped_loc + dropped_dept
        if kept:
            with SessionLocal.begin() as session:
                result.persisted = upsert_jobs(session, kept)
        return result

    result = asyncio.run(_run())
    logger.info(
        "scrape %s: fetched=%d filtered=%d persisted=%d errors=%d",
        result.source,
        result.fetched,
        result.filtered,
        result.persisted,
        result.errors,
    )
    return result.model_dump(mode="json")


@celery_app.task(name="src.tasks.scrape.dispatch_api_scrapes")
def dispatch_api_scrapes() -> list[str]:
    """Enqueue ``run_scraper`` for every enabled API-based company."""

    sources = _load_sources()
    task_ids: list[str] = []
    for entry in sources.companies:
        if not entry.enabled or not is_api_based(entry):
            continue
        r = run_scraper.delay(kind="company", company_name=entry.name)
        task_ids.append(r.id)
    logger.info("dispatch_api_scrapes: enqueued %d tasks", len(task_ids))
    return task_ids


@celery_app.task(name="src.tasks.scrape.dispatch_browser_scrapes")
def dispatch_browser_scrapes() -> list[str]:
    """Enqueue ``run_scraper`` for every browser-based source."""

    sources = _load_sources()
    task_ids: list[str] = []

    for entry in sources.companies:
        if not entry.enabled or is_api_based(entry):
            continue
        r = run_scraper.delay(kind="company", company_name=entry.name)
        task_ids.append(r.id)

    for i, _ in enumerate(sources.linkedin.searches):
        if sources.linkedin.enabled:
            r = run_scraper.delay(kind="linkedin", search_index=i)
            task_ids.append(r.id)

    for i, _ in enumerate(sources.handshake.searches):
        if sources.handshake.enabled:
            r = run_scraper.delay(kind="handshake", search_index=i)
            task_ids.append(r.id)

    logger.info("dispatch_browser_scrapes: enqueued %d tasks", len(task_ids))
    return task_ids


def _find_company(sources: SourcesConfig, name: str) -> CompanyConfig:
    for c in sources.companies:
        if c.name == name:
            return c
    raise KeyError(f"No company named {name!r} in sources config")


# -----------------------------------------------------------------------
# Synchronous helpers (used by ``jaa scrape once`` — no broker required)
# -----------------------------------------------------------------------


def run_all_sync() -> list[ScrapeResult]:
    """Run every enabled scraper once, in-process, serially.

    Useful for ``jaa scrape once`` and for tests — sidesteps the Celery
    broker entirely.
    """

    sources = _load_sources()

    async def _run_one(
        scraper: object,
        allowed_locs: list[str],
        allowed_depts: list[str],
    ) -> ScrapeResult:
        result, payloads = await scraper.run()  # type: ignore[attr-defined]
        kept, d1 = filter_by_locations(payloads, allowed_locs)
        kept, d2 = filter_by_departments(kept, allowed_depts)
        result.filtered = d1 + d2
        if kept:
            with SessionLocal.begin() as session:
                result.persisted = upsert_jobs(session, kept)
        return result  # type: ignore[no-any-return]

    async def _runner() -> list[ScrapeResult]:
        out: list[ScrapeResult] = []
        for entry in sources.companies:
            if not entry.enabled:
                continue
            out.append(
                await _run_one(
                    make_company_scraper(entry),
                    sources.effective_locations_for(entry),
                    entry.departments,
                )
            )
        if sources.linkedin.enabled:
            linkedin_scrapers = make_linkedin_scrapers(sources.linkedin)
            for i, li_search in enumerate(sources.linkedin.searches):
                out.append(
                    await _run_one(
                        linkedin_scrapers[i],
                        li_search.locations or sources.defaults.locations,
                        [],
                    )
                )
        if sources.handshake.enabled:
            handshake_scrapers = make_handshake_scrapers(sources.handshake)
            for i, hs_search in enumerate(sources.handshake.searches):
                out.append(
                    await _run_one(
                        handshake_scrapers[i],
                        hs_search.locations or sources.defaults.locations,
                        [],
                    )
                )
        return out

    return asyncio.run(_runner())


__all__ = [
    "dispatch_api_scrapes",
    "dispatch_browser_scrapes",
    "run_all_sync",
    "run_scraper",
]
