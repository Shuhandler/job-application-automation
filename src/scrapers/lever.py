"""Lever public API scraper.

Endpoint: ``GET https://api.lever.co/v0/postings/{company}?mode=json``

Response is a JSON array of postings. Each item looks like::

    {
      "id": "abc-123-def",
      "text": "Software Engineer",
      "hostedUrl": "https://jobs.lever.co/.../abc-123-def",
      "applyUrl":  "https://jobs.lever.co/.../abc-123-def/apply",
      "categories": {"team": "Engineering", "location": "New York"},
      "description": "<p>HTML</p>",
      "createdAt": 1712000000000  // epoch ms
    }
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from src.scrapers.base import JobPayload, Scraper
from src.scrapers.html_clean import clean_html

logger = logging.getLogger(__name__)

BOARD_URL_TEMPLATE = "https://api.lever.co/v0/postings/{company}"


class LeverScraper(Scraper):
    """Fetch all public postings for a Lever board."""

    def __init__(
        self,
        *,
        company: str,
        board_id: str,
        http_client: httpx.AsyncClient | None = None,
        extra_params: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> None:
        super().__init__(source_name=f"lever:{board_id}")
        self.company = company
        self.board_id = board_id
        self._client = http_client
        self._own_client = http_client is None
        self._extra_params = extra_params or {}
        self._timeout = timeout

    async def fetch(self) -> AsyncIterator[JobPayload]:
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            url = BOARD_URL_TEMPLATE.format(company=self.board_id)
            params = {"mode": "json", **self._extra_params}
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if self._own_client:
                await client.aclose()

        if not isinstance(payload, list):
            logger.warning(
                "lever:%s — unexpected payload type %s", self.board_id, type(payload).__name__
            )
            return

        for raw in payload:
            try:
                job = self._to_payload(raw)
            except ValidationError as e:
                logger.warning(
                    "lever:%s — skipping malformed posting id=%s: %s",
                    self.board_id,
                    raw.get("id") if isinstance(raw, dict) else None,
                    e.errors()[:1],
                )
                continue
            if job is not None:
                yield job

    def _to_payload(self, raw: dict[str, Any]) -> JobPayload | None:
        if not isinstance(raw, dict):
            return None
        ext_id = raw.get("id")
        title = (raw.get("text") or "").strip()
        url = raw.get("hostedUrl") or ""
        apply_url = raw.get("applyUrl") or url
        if not ext_id or not title or not url:
            return None

        categories = raw.get("categories") or {}
        loc = categories.get("location") if isinstance(categories, dict) else None
        dept = categories.get("team") if isinstance(categories, dict) else None

        all_locs: list[str] = []
        additional = raw.get("additionalPlain") or raw.get("additional") or ""
        # Some Lever companies encode "All locations" inside categories.allLocations
        extra_locs = categories.get("allLocations") if isinstance(categories, dict) else None
        if isinstance(extra_locs, list):
            all_locs = [x for x in extra_locs if isinstance(x, str)]

        description_raw = raw.get("description") or ""
        # Lever sometimes returns description + additional sections separately.
        if additional:
            description_raw = f"{description_raw}\n{additional}"

        posted_at = None
        created = raw.get("createdAt")
        if isinstance(created, int):
            try:
                posted_at = datetime.fromtimestamp(created / 1000, tz=UTC)
            except (OSError, ValueError):
                posted_at = None

        return JobPayload(
            source=self.source_name,
            external_id=str(ext_id),
            title=title,
            company=self.company,
            url=url,
            application_url=apply_url,
            description_raw=description_raw,
            description_clean=clean_html(description_raw),
            location=loc,
            locations=all_locs,
            department=dept,
            posted_at=posted_at,
        )
