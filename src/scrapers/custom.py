"""Generic CSS-selector-driven scraper for bespoke career pages.

Driven entirely by :class:`~src.config.sources.CustomSelectors`. Useful
for small companies whose career page is plain HTML without a public
ATS JSON endpoint.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from pathlib import Path

from parsel import Selector

from src.config.sources import CustomSelectors
from src.scrapers.base import JobPayload, Scraper
from src.scrapers.browser import browser_context
from src.scrapers.html_clean import clean_html

logger = logging.getLogger(__name__)


class CustomScraper(Scraper):
    def __init__(
        self,
        *,
        company: str,
        careers_url: str,
        selectors: CustomSelectors,
        storage_state_path: Path | None = None,
        proxy_url: str | None = None,
        max_postings: int = 100,
    ) -> None:
        super().__init__(source_name=f"custom:{_slugify(company)}")
        self.company = company
        self.careers_url = careers_url
        self.selectors = selectors
        self.storage_state_path = storage_state_path
        self.proxy_url = proxy_url
        self.max_postings = max_postings

    async def fetch(self) -> AsyncIterator[JobPayload]:
        async with browser_context(
            storage_state_path=self.storage_state_path,
            proxy_url=self.proxy_url,
        ) as (_browser, ctx):
            page = await ctx.new_page()
            await page.goto(self.careers_url, wait_until="networkidle")

            pages_visited = 0
            while True:
                html = await page.content()
                sel = Selector(text=html)
                count = 0
                for node in sel.css(self.selectors.listing):
                    try:
                        payload = self._to_payload(node)
                    except Exception:
                        logger.exception("custom:%s — skipping malformed listing", self.company)
                        continue
                    if payload is None:
                        continue
                    yield payload
                    count += 1
                    if count >= self.max_postings:
                        return

                pages_visited += 1
                if not self.selectors.next_page or pages_visited >= 10:
                    return
                next_btn = await page.query_selector(self.selectors.next_page)
                if next_btn is None:
                    return
                await next_btn.click()
                await page.wait_for_load_state("networkidle")

    def _to_payload(self, node) -> JobPayload | None:  # type: ignore[no-untyped-def]
        s = self.selectors
        title = _extract(node, s.title)
        url = _extract(node, s.url)
        if not title or not url:
            return None
        if url.startswith("/"):
            base = "/".join(self.careers_url.split("/", 3)[:3])
            url = f"{base}{url}"
        ext_id = url.rsplit("/", 1)[-1].split("?", 1)[0] or url

        location = _extract(node, s.location) if s.location else None
        department = _extract(node, s.department) if s.department else None
        raw_desc = ""
        if s.description:
            desc_node = node.css(s.description)
            if desc_node:
                raw_desc = desc_node[0].get() or ""

        return JobPayload(
            source=self.source_name,
            external_id=ext_id,
            title=title,
            company=self.company,
            url=url,
            application_url=url,
            description_raw=raw_desc,
            description_clean=clean_html(raw_desc) if raw_desc else "",
            location=location,
            locations=[],
            department=department,
        )


def _extract(node, css: str) -> str | None:  # type: ignore[no-untyped-def]
    """Run a CSS selector, supporting ``::attr(...)`` suffixes."""

    vals = node.css(css).getall()
    if not vals:
        return None
    return vals[0].strip() or None


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.casefold()).strip("-")
