"""Persist :class:`JobPayload` batches into the ``jobs`` table.

Uses dialect-specific ``INSERT ... ON CONFLICT DO NOTHING`` so dedup is
atomic and racey-safe under concurrent Celery workers. Supports SQLite
(dev) and PostgreSQL (prod). Other dialects fall back to a
check-then-insert pattern.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import cast

from sqlalchemy import insert as sa_insert
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from src.db.models import Job, JobStatus
from src.scrapers.base import JobPayload

logger = logging.getLogger(__name__)


def _payload_to_row(p: JobPayload) -> dict[str, object]:
    """Flatten a :class:`JobPayload` into a values-dict for ``Job``."""

    return {
        "source": p.source,
        "external_id": p.external_id,
        "title": p.title,
        "company": p.company,
        "url": str(p.url),
        "application_url": str(p.application_url),
        "description_raw": p.description_raw,
        "description_clean": p.description_clean,
        "relevance_score": 0.0,
        "matched_keywords": [],
        "role_category": None,
        "status": JobStatus.DISCOVERED.value,
        "referral_contacts": [],
    }


def upsert_jobs(session: Session, payloads: Iterable[JobPayload]) -> int:
    """Insert payloads, skipping rows that already exist.

    Returns the number of **newly inserted** rows. Existing rows are left
    untouched — later pipeline stages update them by primary key.
    """

    rows = [_payload_to_row(p) for p in payloads]
    if not rows:
        return 0

    dialect = session.bind.dialect.name if session.bind is not None else ""

    if dialect == "sqlite":
        sqlite_stmt = (
            sqlite_insert(Job)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["source", "external_id"])
        )
        # ``rowcount`` on SQLite after ON CONFLICT DO NOTHING reflects
        # successful inserts. See sqlite3 changes(): https://sqlite.org/c3ref/changes.html
        sqlite_result = cast(CursorResult[tuple[int, ...]], session.execute(sqlite_stmt))
        return int(sqlite_result.rowcount or 0)

    if dialect == "postgresql":
        pg_stmt = (
            pg_insert(Job)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["source", "external_id"])
        )
        pg_result = cast(CursorResult[tuple[int, ...]], session.execute(pg_stmt))
        return int(pg_result.rowcount or 0)

    # Portable fallback: check-then-insert. Races possible, but safe with
    # the table-level UniqueConstraint catching duplicates.
    logger.warning("Unknown dialect %r — using portable dedup fallback", dialect)
    inserted = 0
    for row in rows:
        exists = session.execute(
            select(Job.id).where(
                Job.source == row["source"],
                Job.external_id == row["external_id"],
            )
        ).first()
        if exists is not None:
            continue
        session.execute(sa_insert(Job).values(**row))
        inserted += 1
    return inserted
