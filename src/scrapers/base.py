"""Base types for scrapers: DTO, abstract scraper, result container."""

from __future__ import annotations

import abc
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

logger = logging.getLogger(__name__)

NonEmpty = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class JobPayload(BaseModel):
    """DTO returned by a :class:`Scraper` — not yet persisted.

    Kept deliberately decoupled from :class:`src.db.models.Job` so scraper
    code never touches an ORM session. Mapping to ``Job`` happens in
    :func:`src.scrapers.persistence.upsert_jobs`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: NonEmpty  # e.g. "greenhouse:janestreet"
    external_id: NonEmpty  # ATS-provided stable ID — dedup key
    title: NonEmpty
    company: NonEmpty
    url: HttpUrl  # canonical posting URL
    application_url: HttpUrl  # direct link to the apply page
    description_raw: str = ""  # original HTML/markdown as served
    description_clean: str = ""  # whitespace-normalized plaintext
    location: str | None = None  # primary location string as provided
    locations: list[str] = Field(default_factory=list)  # all locations if multi-region
    department: str | None = None
    posted_at: datetime | None = None
    extra: dict[str, str] = Field(default_factory=dict)  # source-specific metadata


class ScrapeResult(BaseModel):
    """Summary returned to Celery / CLI after a scrape run."""

    model_config = ConfigDict(extra="forbid")

    source: str
    fetched: int = 0  # jobs returned by the remote
    filtered: int = 0  # rejected by location/department allow-list
    persisted: int = 0  # newly inserted (after dedup)
    errors: int = 0
    error_samples: list[str] = Field(default_factory=list)


class Scraper(abc.ABC):
    """Abstract base for every source.

    Implementations override :meth:`fetch`, which yields
    :class:`JobPayload` instances. :meth:`run` is the framework
    entry point — it materializes the async iterator, captures
    exceptions, and returns a :class:`ScrapeResult` plus the payload
    list for the persistence layer.
    """

    #: Stable string that becomes ``JobPayload.source`` for this scraper.
    source_name: str

    def __init__(self, *, source_name: str) -> None:
        self.source_name = source_name

    @abc.abstractmethod
    def fetch(self) -> AsyncIterator[JobPayload]:
        """Async-yield :class:`JobPayload` objects.

        Implementations should be resilient to partial failure —
        individual bad postings should be logged and skipped rather than
        aborting the whole run. Fatal errors (auth, rate-limit) may be
        raised.
        """

    async def run(self) -> tuple[ScrapeResult, list[JobPayload]]:
        """Materialize :meth:`fetch` into a result + payloads.

        Location/department filtering happens in
        :func:`src.scrapers.location.filter_by_locations` after this
        returns — keeping it out of the scraper keeps ``fetch`` focused
        on I/O.
        """

        result = ScrapeResult(source=self.source_name)
        payloads: list[JobPayload] = []
        try:
            async for p in self.fetch():
                result.fetched += 1
                payloads.append(p)
        except Exception as exc:
            logger.exception("Scraper %s failed", self.source_name)
            result.errors += 1
            result.error_samples.append(f"{type(exc).__name__}: {exc}")
        return result, payloads
