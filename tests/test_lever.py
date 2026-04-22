from __future__ import annotations

import httpx
import pytest
from src.scrapers.lever import LeverScraper


@pytest.mark.asyncio
async def test_lever_parses_payload() -> None:
    body = [
        {
            "id": "abc-123",
            "text": "Research Scientist",
            "hostedUrl": "https://jobs.lever.co/acme/abc-123",
            "applyUrl": "https://jobs.lever.co/acme/abc-123/apply",
            "categories": {"team": "Research", "location": "New York"},
            "description": "<p>Do science</p>",
            "createdAt": 1_712_000_000_000,
        },
        {
            # Missing id → skipped.
            "text": "broken",
            "hostedUrl": "https://example.com/x",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/postings/acme")
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = LeverScraper(company="Acme", board_id="acme", http_client=client)
        payloads = [p async for p in scraper.fetch()]

    assert len(payloads) == 1
    p = payloads[0]
    assert p.external_id == "abc-123"
    assert p.department == "Research"
    assert p.location == "New York"
    assert str(p.application_url).endswith("/apply")
    assert "Do science" in p.description_clean
    assert p.posted_at is not None


@pytest.mark.asyncio
async def test_lever_handles_non_list_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "an array"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = LeverScraper(company="Acme", board_id="acme", http_client=client)
        assert [p async for p in scraper.fetch()] == []
