"""LinkedIn Jobs scraper (Playwright + authenticated storage_state).

Scrapes ``/jobs/search/?keywords=...&location=...&f_E=<exp-levels>&f_TPR=r<seconds>``.
Requires a valid ``config/linkedin_state.json`` captured from a prior
logged-in session (see docs for the one-off ``playwright codegen`` flow).

The scraper is intentionally conservative:
- small max-pages default (10)
- posting detail pages are fetched serially with inter-request sleeps
- individual posting failures don't abort the whole search
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PwTimeoutError

from src.config.sources import LinkedInExperienceLevel, LinkedInSearch
from src.scrapers.base import JobPayload, Scraper
from src.scrapers.browser import browser_context, scroll_to_bottom
from src.scrapers.html_clean import clean_html

logger = logging.getLogger(__name__)

_EXP_CODE = {
    LinkedInExperienceLevel.INTERNSHIP: "1",
    LinkedInExperienceLevel.ENTRY_LEVEL: "2",
    LinkedInExperienceLevel.ASSOCIATE: "3",
}

SEARCH_URL = "https://www.linkedin.com/jobs/search/"


class LinkedInScraper(Scraper):
    """Run a single LinkedIn jobs search."""

    def __init__(
        self,
        *,
        search: LinkedInSearch,
        storage_state_path: Path,
        proxy_url: str | None = None,
        max_postings: int = 75,
    ) -> None:
        slug = search.query.replace(" ", "-").lower()
        super().__init__(source_name=f"linkedin:{slug}")
        self.search = search
        self.storage_state_path = storage_state_path
        self.proxy_url = proxy_url
        self.max_postings = max_postings

    def _build_url(self) -> str:
        # LinkedIn joins multiple locations with OR semantics by submitting
        # one search per location; we'll iterate locations in ``fetch``
        # instead and use the first here as a sentinel.
        primary_loc = self.search.locations[0] if self.search.locations else ""
        params: dict[str, str] = {
            "keywords": self.search.query,
            "location": primary_loc,
            "f_TPR": f"r{self.search.posted_within_days * 86400}",
        }
        codes = [_EXP_CODE[lvl] for lvl in self.search.experience_levels]
        if codes:
            params["f_E"] = ",".join(codes)
        return f"{SEARCH_URL}?{urlencode(params)}"

    async def fetch(self) -> AsyncIterator[JobPayload]:
        async with browser_context(
            storage_state_path=self.storage_state_path,
            proxy_url=self.proxy_url,
        ) as (_browser, ctx):
            page = await ctx.new_page()
            url = self._build_url()
            logger.info("linkedin search: %s", url)
            await page.goto(url, wait_until="domcontentloaded")

            try:
                await page.wait_for_selector(
                    "ul.jobs-search__results-list, ul.scaffold-layout__list-container",
                    timeout=15_000,
                )
            except PwTimeoutError:
                logger.warning("linkedin: no results list loaded; possibly logged out")
                return

            await scroll_to_bottom(page, max_scrolls=20)

            card_selector = "li[data-occludable-job-id], li.jobs-search-results__list-item, li.scaffold-layout__list-item"
            cards = await page.query_selector_all(card_selector)
            logger.info("linkedin: found %d cards", len(cards))

            seen: set[str] = set()
            for card in cards[: self.max_postings]:
                try:
                    payload = await self._extract_card(page, card)
                except Exception:
                    logger.exception("linkedin: skipping malformed card")
                    continue
                if payload is None or payload.external_id in seen:
                    continue
                seen.add(payload.external_id)
                yield payload
                await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _extract_card(self, page: Page, card) -> JobPayload | None:  # type: ignore[no-untyped-def]
        # Click the card to load the detail pane on the right.
        ext_id = await card.get_attribute("data-occludable-job-id")
        if ext_id is None:
            link = await card.query_selector("a[href*='/jobs/view/']")
            if link is None:
                return None
            href = await link.get_attribute("href") or ""
            ext_id = href.rsplit("/view/", 1)[-1].split("/", 1)[0].split("?", 1)[0]
        if not ext_id:
            return None

        link_el = await card.query_selector("a[href*='/jobs/view/']")
        href = await link_el.get_attribute("href") if link_el else None
        title_el = await card.query_selector("a span[aria-hidden='true'], h3")
        title = (await title_el.inner_text()).strip() if title_el else ""
        company_el = await card.query_selector(".job-card-container__primary-description, h4")
        company = (await company_el.inner_text()).strip() if company_el else ""
        loc_el = await card.query_selector(
            ".job-card-container__metadata-item, .job-search-card__location"
        )
        location = (await loc_el.inner_text()).strip() if loc_el else None

        await card.click()
        with contextlib.suppress(PwTimeoutError):
            await page.wait_for_selector(
                ".jobs-description__content, .show-more-less-html__markup", timeout=5_000
            )

        desc_el = await page.query_selector(
            ".jobs-description__content, .show-more-less-html__markup"
        )
        description_raw = ""
        if desc_el is not None:
            description_raw = await desc_el.inner_html()

        if not (title and company and href):
            return None

        full_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
        return JobPayload(
            source=self.source_name,
            external_id=ext_id,
            title=title,
            company=company,
            url=full_url,
            application_url=full_url,
            description_raw=description_raw,
            description_clean=clean_html(description_raw),
            location=location,
            locations=list(self.search.locations),
            department=None,
            extra={"search_query": self.search.query},
        )
