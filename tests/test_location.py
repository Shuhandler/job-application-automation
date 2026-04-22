from __future__ import annotations

import pytest
from src.scrapers.base import JobPayload
from src.scrapers.location import (
    any_location_matches,
    filter_by_departments,
    filter_by_locations,
    matches,
)


def _p(**overrides: object) -> JobPayload:
    defaults: dict[str, object] = {
        "source": "greenhouse:test",
        "external_id": "1",
        "title": "Role",
        "company": "Acme",
        "url": "https://example.com/1",
        "application_url": "https://example.com/1",
    }
    defaults.update(overrides)
    return JobPayload.model_validate(defaults)


@pytest.mark.parametrize(
    "loc, allowed, expected",
    [
        ("New York, NY", ["New York"], True),
        ("San Francisco, CA", ["New York"], False),
        ("Remote - US", ["United States"], True),
        ("Remote (Global)", ["Remote"], True),
        ("London, UK", ["United States", "Remote"], False),
        ("Anywhere in the US", ["United States"], True),
        ("", ["New York"], True),  # no loc info → pass through
        ("Anywhere", [], True),  # empty allow-list → pass
    ],
)
def test_matches(loc: str, allowed: list[str], expected: bool) -> None:
    assert matches(loc, allowed) is expected


def test_any_location_matches_across_fields() -> None:
    p = _p(location="London, UK", locations=["Remote", "New York"])
    assert any_location_matches(p, ["Remote"]) is True


def test_filter_by_locations_partitions() -> None:
    payloads = [
        _p(external_id="1", location="New York, NY"),
        _p(external_id="2", location="London, UK"),
        _p(external_id="3", location="Remote"),
    ]
    kept, dropped = filter_by_locations(payloads, ["United States", "Remote"])
    assert {p.external_id for p in kept} == {"1", "3"}
    assert dropped == 1


def test_filter_by_departments() -> None:
    payloads = [
        _p(external_id="1", department="Engineering"),
        _p(external_id="2", department="Sales"),
        _p(external_id="3", department=None),  # unknown → pass through
    ]
    kept, dropped = filter_by_departments(payloads, ["engineering"])
    assert {p.external_id for p in kept} == {"1", "3"}
    assert dropped == 1
