from __future__ import annotations

import httpx
import pytest
from src.scrapers.greenhouse import GreenhouseScraper


@pytest.mark.asyncio
async def test_greenhouse_parses_payload() -> None:
    body = {
        "jobs": [
            {
                "id": 1001,
                "title": "Software Engineer, New Grad",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/1001",
                "location": {"name": "New York, NY"},
                "offices": [{"name": "New York, NY"}, {"name": "Remote"}],
                "departments": [{"name": "Engineering"}],
                "content": "&lt;p&gt;We value &amp; care&lt;/p&gt;",
                "updated_at": "2026-04-21T10:00:00Z",
            },
            {
                # Missing id — must be skipped, not crash.
                "title": "Broken",
                "absolute_url": "https://example.com/x",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/boards/acme/jobs")
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = GreenhouseScraper(company="Acme", board_id="acme", http_client=client)
        payloads = [p async for p in scraper.fetch()]

    assert len(payloads) == 1
    p = payloads[0]
    assert p.external_id == "1001"
    assert p.company == "Acme"
    assert p.title == "Software Engineer, New Grad"
    assert p.location == "New York, NY"
    assert "Remote" in p.locations
    assert p.department == "Engineering"
    # Unescaped + cleaned.
    assert "We value & care" in p.description_clean
    assert "<p>" not in p.description_clean
    assert p.posted_at is not None


@pytest.mark.asyncio
async def test_greenhouse_http_error_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = GreenhouseScraper(company="Acme", board_id="acme", http_client=client)
        with pytest.raises(httpx.HTTPStatusError):
            [_ async for _ in scraper.fetch()]
