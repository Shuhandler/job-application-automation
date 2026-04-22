"""Playwright helpers for authenticated, stealth-patched scraping.

Centralizes browser launch, storage-state loading, stealth patching, and
UA rotation so individual scrapers don't repeat the setup. All
consumers use the async Playwright API.

Requires ``uv run playwright install chromium`` once per machine.
"""

from __future__ import annotations

import logging
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

# Recent stable Chrome UAs on common platforms; rotated per session.
_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)


def random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


@asynccontextmanager
async def browser_context(
    *,
    storage_state_path: Path | None = None,
    headless: bool = True,
    proxy_url: str | None = None,
    viewport: tuple[int, int] = (1440, 900),
) -> AsyncIterator[tuple[Browser, BrowserContext]]:
    """Yield a stealth-patched :class:`BrowserContext`.

    Loads ``storage_state_path`` if it exists so authenticated sessions
    are reused across runs. ``proxy_url`` (if non-empty) is passed to
    Chromium's ``--proxy-server``.
    """

    stealth = Stealth()
    async with async_playwright() as pw:
        launch_kwargs: dict[str, object] = {"headless": headless}
        if proxy_url:
            launch_kwargs["proxy"] = {"server": proxy_url}
        browser: Browser = await pw.chromium.launch(**launch_kwargs)  # type: ignore[arg-type]

        context_kwargs: dict[str, object] = {
            "user_agent": random_user_agent(),
            "viewport": {"width": viewport[0], "height": viewport[1]},
            "locale": "en-US",
        }
        if storage_state_path and storage_state_path.is_file():
            context_kwargs["storage_state"] = str(storage_state_path)
        else:
            if storage_state_path:
                logger.warning(
                    "storage_state not found at %s — running unauthenticated",
                    storage_state_path,
                )

        ctx: BrowserContext = await browser.new_context(**context_kwargs)  # type: ignore[arg-type]
        await stealth.apply_stealth_async(ctx)

        try:
            yield browser, ctx
        finally:
            await ctx.close()
            await browser.close()


async def scroll_to_bottom(page: Page, *, max_scrolls: int = 30, wait_ms: int = 800) -> None:
    """Infinite-scroll a page until it stops growing or ``max_scrolls``."""

    last_height = 0
    for _ in range(max_scrolls):
        height = await page.evaluate("document.body.scrollHeight")
        if height == last_height:
            return
        last_height = height
        await page.mouse.wheel(0, 10_000)
        await page.wait_for_timeout(wait_ms)
