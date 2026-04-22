from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from src.config.sources import (
    AtsType,
    LinkedInExperienceLevel,
    load_sources_config,
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_example_yaml_round_trip() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = load_sources_config(repo_root / "config" / "sources.example.yaml")
    assert cfg.companies
    assert any(c.ats is AtsType.GREENHOUSE for c in cfg.companies)
    assert any(c.ats is AtsType.LEVER for c in cfg.companies)
    assert any(c.ats is AtsType.WORKDAY for c in cfg.companies)
    assert any(c.ats is AtsType.CUSTOM for c in cfg.companies)
    assert cfg.defaults.locations


def test_greenhouse_requires_board_id(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
companies:
  - name: "X"
    ats: greenhouse
""",
    )
    with pytest.raises(ValidationError) as ei:
        load_sources_config(p)
    assert "board_id" in str(ei.value)


def test_workday_requires_careers_url(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
companies:
  - name: "X"
    ats: workday
""",
    )
    with pytest.raises(ValidationError):
        load_sources_config(p)


def test_custom_requires_selectors(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
companies:
  - name: "X"
    ats: custom
    careers_url: "https://example.com/careers"
""",
    )
    with pytest.raises(ValidationError) as ei:
        load_sources_config(p)
    assert "selectors" in str(ei.value)


def test_handshake_requires_subdomain_when_enabled(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
handshake:
  enabled: true
""",
    )
    with pytest.raises(ValidationError):
        load_sources_config(p)


def test_enabled_companies_filter(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
companies:
  - name: "A"
    ats: greenhouse
    board_id: "a"
    enabled: true
  - name: "B"
    ats: greenhouse
    board_id: "b"
    enabled: false
""",
    )
    cfg = load_sources_config(p)
    assert [c.name for c in cfg.enabled_companies()] == ["A"]
    assert [c.name for c in cfg.enabled_companies(ats=AtsType.GREENHOUSE)] == ["A"]


def test_linkedin_default_experience_levels(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
linkedin:
  enabled: true
  searches:
    - query: "swe new grad"
""",
    )
    cfg = load_sources_config(p)
    search = cfg.linkedin.searches[0]
    assert LinkedInExperienceLevel.INTERNSHIP in search.experience_levels
    assert LinkedInExperienceLevel.ENTRY_LEVEL in search.experience_levels


def test_effective_locations_fallback(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s.yaml",
        """
defaults:
  locations: ["United States"]
companies:
  - name: "A"
    ats: greenhouse
    board_id: "a"
  - name: "B"
    ats: greenhouse
    board_id: "b"
    locations: ["New York"]
""",
    )
    cfg = load_sources_config(p)
    a, b = cfg.companies
    assert cfg.effective_locations_for(a) == ["United States"]
    assert cfg.effective_locations_for(b) == ["New York"]
