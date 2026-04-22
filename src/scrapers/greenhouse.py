"""Greenhouse public API scraper.

Endpoint: ``GET https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs?content=true``

Response shape (excerpt)::

    {
      "jobs": [
        {
          "id": 12345,
          "title": "Software Engineer",
          "absolute_url": "https://boards.greenhouse.io/.../12345",
          "location": {"name": "New York, NY"},
          "departments": [{"name": "Engineering"}],
          "content": "<p>HTML description</p>",
          "updated_at": "2026-04-21T10:00:00Z"
        },
        ...
      ]
    }
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime
from html import unescape
from typing import Any

import httpx
from pydantic import ValidationError

from src.scrapers.base import JobPayload, Scraper
from src.scrapers.html_clean import clean_html

logger = logging.getLogger(__name__)

BOARD_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs"


class GreenhouseScraper(Scraper):
    """Fetch all public postings for a Greenhouse board."""

    def __init__(
        self,
        *,
        company: str,
        board_id: str,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ) -> None:
        super().__init__(source_name=f"greenhouse:{board_id}")
        self.company = company
        self.board_id = board_id
        self._client = http_client
        self._own_client = http_client is None
        self._timeout = timeout

    async def fetch(self) -> AsyncIterator[JobPayload]:
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            url = BOARD_URL_TEMPLATE.format(board_id=self.board_id)
            resp = await client.get(url, params={"content": "true"})
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if self._own_client:
                await client.aclose()

        for raw in payload.get("jobs", []):
            try:
                job = self._to_payload(raw)
            except ValidationError as e:
                logger.warning(
                    "greenhouse:%s — skipping malformed posting id=%s: %s",
                    self.board_id,
                    raw.get("id"),
                    e.errors()[:1],
                )
                continue
            if job is not None:
                yield job

    def _to_payload(self, raw: dict[str, Any]) -> JobPayload | None:
        ext_id = raw.get("id")
        if ext_id is None:
            return None

        url = raw.get("absolute_url") or ""
        title = (raw.get("title") or "").strip()
        if not title or not url:
            return None

        loc_name = None
        loc_obj = raw.get("location")
        if isinstance(loc_obj, dict):
            loc_name = loc_obj.get("name")

        all_locs: list[str] = []
        for office in raw.get("offices", []) or []:
            name = office.get("name") if isinstance(office, dict) else None
            if name:
                all_locs.append(name)

        dept = None
        depts = raw.get("departments") or []
        if depts and isinstance(depts[0], dict):
            dept = depts[0].get("name")

        raw_html = raw.get("content") or ""
        # Greenhouse double-encodes HTML entities in ``content``.
        raw_html = unescape(raw_html)

        posted_at = None
        updated = raw.get("updated_at")
        if isinstance(updated, str):
            try:
                posted_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except ValueError:
                posted_at = None

        return JobPayload(
            source=self.source_name,
            external_id=str(ext_id),
            title=title,
            company=self.company,
            url=url,
            application_url=url,
            description_raw=raw_html,
            description_clean=clean_html(raw_html),
            location=loc_name,
            locations=all_locs,
            department=dept,
            posted_at=posted_at,
        )
