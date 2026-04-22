"""Phase 1 — Source monitoring.

Each concrete scraper subclasses :class:`src.scrapers.base.Scraper` and
yields :class:`~src.scrapers.base.JobPayload` DTOs. The registry maps
:class:`~src.config.sources.AtsType` / source-name values to scraper
classes so Celery tasks can dispatch generically.
"""

from src.scrapers.base import JobPayload, Scraper, ScrapeResult

__all__ = ["JobPayload", "ScrapeResult", "Scraper"]
