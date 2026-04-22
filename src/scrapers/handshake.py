"""Handshake scraper (Playwright + authenticated storage_state).

Handshake is school-scoped: ``https://<school>.joinhandshake.com/stu/postings``.
The storage_state must be captured after SSO'ing in (Shibboleth /
Okta / etc.). Handshake uses React and infinite-scrolling — we wait
for posting cards to appear, scroll, and extract each one.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PwTimeoutError

from src.config.sources import HandshakeSearch
from src.scrapers.base import JobPayload, Scraper
from src.scrapers.browser import browser_context, scroll_to_bottom
from src.scrapers.html_clean import clean_html

logger = logging.getLogger(__name__)


class HandshakeScraper(Scraper):
    def __init__(
        self,
        *,
        search: HandshakeSearch,
        school_subdomain: str,
        storage_state_path: Path,
        proxy_url: str | None = None,
        max_postings: int = 75,
    ) -> None:
        slug = search.query.replace(" ", "-").lower()
        super().__init__(source_name=f"handshake:{school_subdomain}:{slug}")
        self.search = search
        self.school_subdomain = school_subdomain
        self.storage_state_path = storage_state_path
        self.proxy_url = proxy_url
        self.max_postings = max_postings

    def _build_url(self) -> str:
        base = f"https://{self.school_subdomain}.joinhandshake.com/stu/postings"
        params: dict[str, str] = {"query": self.search.query}
        if self.search.locations:
            params["location"] = self.search.locations[0]
        return f"{base}?{urlencode(params)}"

    async def fetch(self) -> AsyncIterator[JobPayload]:
        async with browser_context(
            storage_state_path=self.storage_state_path,
            proxy_url=self.proxy_url,
        ) as (_browser, ctx):
            page = await ctx.new_page()
            url = self._build_url()
            logger.info("handshake search: %s", url)
            await page.goto(url, wait_until="networkidle")

            try:
                await page.wait_for_selector(
                    "[data-hook='job-result-card'], a[href*='/jobs/']", timeout=15_000
                )
            except PwTimeoutError:
                logger.warning("handshake: no results loaded; possibly logged out")
                return

            await scroll_to_bottom(page, max_scrolls=20)

            cards = await page.query_selector_all(
                "[data-hook='job-result-card'], a[href*='/jobs/']"
            )
            logger.info("handshake: found %d cards", len(cards))

            seen: set[str] = set()
            for card in cards[: self.max_postings]:
                try:
                    href = await card.get_attribute("href")
                    if href is None:
                        link_el = await card.query_selector("a[href*='/jobs/']")
                        href = await link_el.get_attribute("href") if link_el else None
                    if not href:
                        continue
                    ext_id = href.rsplit("/jobs/", 1)[-1].split("/", 1)[0].split("?", 1)[0]
                    if not ext_id or ext_id in seen:
                        continue
                    seen.add(ext_id)

                    title_el = await card.query_selector("h3, [data-hook='job-title']")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    company_el = await card.query_selector("[data-hook='employer-name'], h4")
                    company = (await company_el.inner_text()).strip() if company_el else ""
                    loc_el = await card.query_selector("[data-hook='job-location']")
                    location = (await loc_el.inner_text()).strip() if loc_el else None

                    full_url = (
                        href
                        if href.startswith("http")
                        else f"https://{self.school_subdomain}.joinhandshake.com{href}"
                    )

                    if not (title and company):
                        continue

                    yield JobPayload(
                        source=self.source_name,
                        external_id=ext_id,
                        title=title,
                        company=company,
                        url=full_url,
                        application_url=full_url,
                        description_raw="",
                        description_clean="",
                        location=location,
                        locations=list(self.search.locations),
                        department=None,
                        extra={"search_query": self.search.query},
                    )
                    await asyncio.sleep(random.uniform(0.4, 1.2))
                except Exception:
                    logger.exception("handshake: skipping malformed card")
                    continue

    async def _enrich_description(self, page: Page, url: str) -> str:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            desc_el = await page.query_selector("[data-hook='job-description'], .job-description")
            if desc_el is not None:
                html = await desc_el.inner_html()
                return clean_html(html)
        except PwTimeoutError:
            logger.warning("handshake: description fetch timed out for %s", url)
        return ""
