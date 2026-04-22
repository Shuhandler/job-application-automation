"""Celery application + beat schedule.

Usage::

    # Worker:
    uv run celery -A src.tasks.app worker --loglevel=info

    # Beat scheduler:
    uv run celery -A src.tasks.app beat --loglevel=info

Or via the CLI wrappers:

    uv run jaa scrape worker
    uv run jaa scrape beat
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "jaa",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks.scrape"],
)

celery_app.conf.update(
    task_default_queue="scrape",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Per-source rate limits are applied via ``@task(rate_limit=...)``.
    # Retries: enabled per-task with autoretry_for in src.tasks.scrape.
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    # Beat schedule: API sources every 5 min, browser sources every 15 min.
    beat_schedule={
        "dispatch-api-scrapes": {
            "task": "src.tasks.scrape.dispatch_api_scrapes",
            "schedule": schedule(run_every=300.0),
        },
        "dispatch-browser-scrapes": {
            "task": "src.tasks.scrape.dispatch_browser_scrapes",
            "schedule": schedule(run_every=900.0),
        },
    },
)


__all__ = ["celery_app"]
