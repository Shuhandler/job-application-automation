"""Celery task layer.

Exposes the configured Celery app and the scrape task functions. Beat
schedule is wired in :mod:`src.tasks.app`.
"""

from src.tasks.app import celery_app
from src.tasks.scrape import (
    dispatch_api_scrapes,
    dispatch_browser_scrapes,
    run_scraper,
)

__all__ = [
    "celery_app",
    "dispatch_api_scrapes",
    "dispatch_browser_scrapes",
    "run_scraper",
]
