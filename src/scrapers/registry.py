"""Factory functions that construct scrapers from config entries.

Celery tasks (``src.tasks.scrape``) use these so they never need to
import individual scraper modules conditionally.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.config import get_settings
from src.config.sources import (
    AtsType,
    CompanyConfig,
    HandshakeConfig,
    LinkedInConfig,
)
from src.scrapers.base import Scraper
from src.scrapers.custom import CustomScraper
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.handshake import HandshakeScraper
from src.scrapers.lever import LeverScraper
from src.scrapers.linkedin import LinkedInScraper
from src.scrapers.workday import WorkdayScraper


def make_company_scraper(entry: CompanyConfig) -> Scraper:
    """Build the right :class:`Scraper` for a :class:`CompanyConfig`."""

    settings = get_settings()
    if entry.ats is AtsType.GREENHOUSE:
        assert entry.board_id is not None
        return GreenhouseScraper(company=entry.name, board_id=entry.board_id)
    if entry.ats is AtsType.LEVER:
        assert entry.board_id is not None
        return LeverScraper(
            company=entry.name,
            board_id=entry.board_id,
            extra_params=entry.search_params,
        )
    if entry.ats is AtsType.WORKDAY:
        assert entry.careers_url is not None
        return WorkdayScraper(
            company=entry.name,
            careers_url=str(entry.careers_url),
            proxy_url=settings.proxy_url or None,
            search_params=entry.search_params,
        )
    if entry.ats is AtsType.CUSTOM:
        assert entry.careers_url is not None and entry.selectors is not None
        return CustomScraper(
            company=entry.name,
            careers_url=str(entry.careers_url),
            selectors=entry.selectors,
            proxy_url=settings.proxy_url or None,
        )
    raise ValueError(f"Unhandled ATS type: {entry.ats}")


def make_linkedin_scrapers(cfg: LinkedInConfig) -> list[Scraper]:
    """One scraper per LinkedIn search."""

    if not cfg.enabled:
        return []
    settings = get_settings()
    return [
        LinkedInScraper(
            search=search,
            storage_state_path=settings.linkedin_storage_state_path,
            proxy_url=settings.proxy_url or None,
        )
        for search in cfg.searches
    ]


def make_handshake_scrapers(cfg: HandshakeConfig) -> list[Scraper]:
    """One scraper per Handshake search."""

    if not cfg.enabled or cfg.school_subdomain is None:
        return []
    settings = get_settings()
    return [
        HandshakeScraper(
            search=search,
            school_subdomain=cfg.school_subdomain,
            storage_state_path=settings.handshake_storage_state_path,
            proxy_url=settings.proxy_url or None,
        )
        for search in cfg.searches
    ]


def make_all_scrapers(
    companies: Iterable[CompanyConfig],
    linkedin: LinkedInConfig,
    handshake: HandshakeConfig,
) -> list[Scraper]:
    """Materialize every enabled scraper from a :class:`SourcesConfig`."""

    scrapers: list[Scraper] = [make_company_scraper(c) for c in companies if c.enabled]
    scrapers.extend(make_linkedin_scrapers(linkedin))
    scrapers.extend(make_handshake_scrapers(handshake))
    return scrapers


def is_api_based(entry: CompanyConfig) -> bool:
    """API-based entries poll every 5 min; browser-based every 15 min."""

    return entry.ats in {AtsType.GREENHOUSE, AtsType.LEVER}


__all__ = [
    "is_api_based",
    "make_all_scrapers",
    "make_company_scraper",
    "make_handshake_scrapers",
    "make_linkedin_scrapers",
]
