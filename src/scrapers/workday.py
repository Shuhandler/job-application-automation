"""Workday scraper (Playwright; no auth required for public boards).

Workday tenants expose an internal JSON API at
``/wday/cxs/<tenant>/<site>/jobs`` (POST). We render the careers page
first so Playwright captures the tenant/site + CSRF cookies, then
``request.post`` the JSON endpoint from the same browser context.

Per-company tuning (locations, job family) is done via ``search_params``
on the :class:`~src.config.sources.CompanyConfig`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from pathlib import Path

from src.scrapers.base import JobPayload, Scraper
from src.scrapers.browser import browser_context
from src.scrapers.html_clean import clean_html

logger = logging.getLogger(__name__)

# Matches the ``/wday/cxs/<tenant>/<site>/jobs`` segment that Workday XHRs hit.
_JOBS_API_RE = re.compile(r"(/wday/cxs/[^/]+/[^/]+)/jobs$")


class WorkdayScraper(Scraper):
    def __init__(
        self,
        *,
        company: str,
        careers_url: str,
        storage_state_path: Path | None = None,
        proxy_url: str | None = None,
        search_params: dict[str, str] | None = None,
        max_postings: int = 200,
    ) -> None:
        slug = _slugify(company)
        super().__init__(source_name=f"workday:{slug}")
        self.company = company
        self.careers_url = careers_url
        self.storage_state_path = storage_state_path
        self.proxy_url = proxy_url
        self.search_params = search_params or {}
        self.max_postings = max_postings

    async def fetch(self) -> AsyncIterator[JobPayload]:
        async with browser_context(
            storage_state_path=self.storage_state_path,
            proxy_url=self.proxy_url,
        ) as (_browser, ctx):
            page = await ctx.new_page()

            # Capture the first /jobs XHR URL so we can page through it.
            jobs_api: list[str] = []

            async def _on_request(req) -> None:  # type: ignore[no-untyped-def]
                if _JOBS_API_RE.search(req.url):
                    jobs_api.append(req.url)

            page.on("request", _on_request)
            await page.goto(self.careers_url, wait_until="networkidle")
            # Give XHRs a moment in case networkidle fired early.
            await page.wait_for_timeout(1_500)

            if not jobs_api:
                logger.warning("workday:%s — no jobs API request observed", self.company)
                return

            api_url = jobs_api[0]
            logger.info("workday:%s — api=%s", self.company, api_url)

            offset = 0
            page_size = 50
            search_text = self.search_params.get("q", "")
            while offset < self.max_postings:
                body = {
                    "appliedFacets": {},
                    "limit": page_size,
                    "offset": offset,
                    "searchText": search_text,
                }
                resp = await ctx.request.post(api_url, data=body)
                if not resp.ok:
                    logger.warning(
                        "workday:%s — pagination stopped at offset=%d (%s)",
                        self.company,
                        offset,
                        resp.status,
                    )
                    return
                data = await resp.json()
                postings = data.get("jobPostings") or []
                if not postings:
                    return
                for raw in postings:
                    try:
                        payload = self._to_payload(raw, api_url)
                    except Exception:
                        logger.exception("workday:%s — skipping malformed posting", self.company)
                        continue
                    if payload is not None:
                        yield payload
                if len(postings) < page_size:
                    return
                offset += page_size

    def _to_payload(self, raw: dict[str, object], api_url: str) -> JobPayload | None:
        title = str(raw.get("title") or "").strip()
        ext_path = str(raw.get("externalPath") or "")  # e.g. /job/New-York/.../R-12345
        if not title or not ext_path:
            return None
        ext_id = ext_path.rsplit("_R-", 1)[-1] if "_R-" in ext_path else ext_path.rsplit("/", 1)[-1]

        locations_text = str(raw.get("locationsText") or "")
        loc_list = [s.strip() for s in locations_text.split(";") if s.strip()]
        # The public careers URL host is where candidates apply; derive it
        # from the API URL's origin.
        m = _JOBS_API_RE.search(api_url)
        if m is None:
            return None
        base_api = api_url[: m.end(1) + len("")]
        careers_host = self.careers_url.split("//", 1)[-1].split("/", 1)[0]
        full_url = f"https://{careers_host}{ext_path}"

        description_raw = str(raw.get("jobDescription") or "")
        return JobPayload(
            source=self.source_name,
            external_id=ext_id,
            title=title,
            company=self.company,
            url=full_url,
            application_url=full_url,
            description_raw=description_raw,
            description_clean=clean_html(description_raw),
            location=loc_list[0] if loc_list else None,
            locations=loc_list,
            department=None,
            extra={"workday_api": base_api},
        )


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.casefold()).strip("-")
