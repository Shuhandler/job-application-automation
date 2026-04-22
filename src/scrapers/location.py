"""Location allow-list matching.

The rules are intentionally forgiving: any substring match (case-folded)
between an allowed token and the posting's location string counts as a
hit. "Remote" and "United States" are treated specially so "Remote - US"
or "US (Remote)" phrasing matches both.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.scrapers.base import JobPayload

_REMOTE_TOKENS = frozenset({"remote", "anywhere", "work from home", "wfh", "distributed"})
_US_TOKENS = frozenset({"united states", "usa", "u.s.", "u.s.a", " us ", "(us)", "us-"})
_US_STATE_CODES = frozenset(
    {
        "al",
        "ak",
        "az",
        "ar",
        "ca",
        "co",
        "ct",
        "de",
        "fl",
        "ga",
        "hi",
        "id",
        "il",
        "in",
        "ia",
        "ks",
        "ky",
        "la",
        "me",
        "md",
        "ma",
        "mi",
        "mn",
        "ms",
        "mo",
        "mt",
        "ne",
        "nv",
        "nh",
        "nj",
        "nm",
        "ny",
        "nc",
        "nd",
        "oh",
        "ok",
        "or",
        "pa",
        "ri",
        "sc",
        "sd",
        "tn",
        "tx",
        "ut",
        "vt",
        "va",
        "wa",
        "wv",
        "wi",
        "wy",
        "dc",
    }
)
# Matches "New York, NY" / "Remote - CA" style suffix.
_STATE_CODE_RE = re.compile(r"[,\-\s]\s*([a-z]{2})(?=\b|,|\s|$)")


def _normalize(text: str) -> str:
    return " " + text.casefold().strip() + " "


def _is_remote(loc: str) -> bool:
    n = _normalize(loc)
    return any(tok in n for tok in _REMOTE_TOKENS)


def _is_us(loc: str) -> bool:
    """Explicit US tokens OR a recognized ``, ST`` 2-letter suffix."""

    n = _normalize(loc)
    if any(tok in n for tok in _US_TOKENS):
        return True
    return any(m.group(1) in _US_STATE_CODES for m in _STATE_CODE_RE.finditer(loc.casefold()))


def matches(loc: str, allowed: Iterable[str]) -> bool:
    """True if ``loc`` matches any token in the ``allowed`` allow-list.

    Empty ``allowed`` disables filtering (returns ``True``).
    """

    allowed = list(allowed)
    if not allowed:
        return True
    if not loc:
        # No location info — let it through rather than discard silently.
        return True

    n = _normalize(loc)
    for tok in allowed:
        t = tok.casefold().strip()
        if not t:
            continue
        if t == "remote" and _is_remote(loc):
            return True
        if t in {"united states", "usa", "us"} and (_is_us(loc) or _is_remote(loc)):
            # "Remote" jobs often count as US-eligible; include them.
            return True
        if t in n:
            return True
    return False


def any_location_matches(payload: JobPayload, allowed: Iterable[str]) -> bool:
    """True if at least one of a payload's locations matches."""

    allowed = list(allowed)
    if not allowed:
        return True
    candidates: list[str] = []
    if payload.location:
        candidates.append(payload.location)
    candidates.extend(payload.locations)
    if not candidates:
        return True
    return any(matches(loc, allowed) for loc in candidates)


def filter_by_locations(
    payloads: list[JobPayload], allowed: Iterable[str]
) -> tuple[list[JobPayload], int]:
    """Partition ``payloads`` into (kept, dropped_count)."""

    allowed = list(allowed)
    if not allowed:
        return payloads, 0
    kept: list[JobPayload] = []
    dropped = 0
    for p in payloads:
        if any_location_matches(p, allowed):
            kept.append(p)
        else:
            dropped += 1
    return kept, dropped


def filter_by_departments(
    payloads: list[JobPayload], allowed: Iterable[str]
) -> tuple[list[JobPayload], int]:
    """Allow-list filter on :attr:`JobPayload.department`."""

    allowed = [a.casefold().strip() for a in allowed if a.strip()]
    if not allowed:
        return payloads, 0
    kept: list[JobPayload] = []
    dropped = 0
    for p in payloads:
        if p.department is None:
            kept.append(p)
            continue
        dept = p.department.casefold().strip()
        if any(a in dept or dept in a for a in allowed):
            kept.append(p)
        else:
            dropped += 1
    return kept, dropped
