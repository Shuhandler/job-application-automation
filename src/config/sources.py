"""Sources (companies + searches) configuration schema.

Loaded from a YAML file pointed to by ``settings.sources_config_path``.
The top-level document has four optional sections::

    companies:          # ATS-backed company pages (Greenhouse / Lever / Workday / custom)
      - name: ...
    linkedin:           # LinkedIn Jobs searches (Playwright + storage_state)
      enabled: true
      searches: [...]
    handshake:          # Handshake school feed (Playwright + SSO storage_state)
      enabled: true
      school_subdomain: "upenn"
      searches: [...]
    defaults:           # Shared defaults applied to every entry (locations, tags, ...)
      locations: ["United States", "Remote"]

See ``config/sources.example.yaml`` for a fully-populated example.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class AtsType(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    CUSTOM = "custom"


class LinkedInExperienceLevel(StrEnum):
    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry_level"
    ASSOCIATE = "associate"


class CustomSelectors(BaseModel):
    """CSS / XPath selectors for :class:`AtsType.CUSTOM` scrapers."""

    model_config = ConfigDict(extra="forbid")

    listing: NonEmpty  # selects each job card
    title: NonEmpty
    url: NonEmpty
    location: str | None = None
    department: str | None = None
    description: str | None = None
    next_page: str | None = None


class CompanyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonEmpty
    ats: AtsType
    enabled: bool = True
    priority: int = Field(default=2, ge=1, le=5)  # 1 = highest

    # Greenhouse / Lever: the board identifier in the ATS URL path.
    board_id: str | None = None
    # Workday / custom: full landing URL for the careers page.
    careers_url: HttpUrl | None = None
    # Extra querystring params for the scraper (e.g. Lever's ``mode``).
    search_params: dict[str, str] = Field(default_factory=dict)

    # Filtering applied at scrape time.
    locations: list[str] = Field(default_factory=list)  # allow-list; empty = no filter
    departments: list[str] = Field(default_factory=list)  # allow-list; empty = no filter

    # Metadata
    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    # CUSTOM-only selectors
    selectors: CustomSelectors | None = None

    @model_validator(mode="after")
    def _validate_ats_specific(self) -> CompanyConfig:
        if self.ats in {AtsType.GREENHOUSE, AtsType.LEVER} and not self.board_id:
            raise ValueError(
                f"{self.ats.value} company {self.name!r} requires a `board_id` "
                "(the slug in the ATS URL path)."
            )
        if self.ats in {AtsType.WORKDAY, AtsType.CUSTOM} and self.careers_url is None:
            raise ValueError(f"{self.ats.value} company {self.name!r} requires a `careers_url`.")
        if self.ats is AtsType.CUSTOM and self.selectors is None:
            raise ValueError(
                f"Custom company {self.name!r} requires `selectors` (CSS selectors block)."
            )
        return self


class LinkedInSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: NonEmpty
    locations: list[str] = Field(default_factory=list)
    experience_levels: list[LinkedInExperienceLevel] = Field(
        default_factory=lambda: [
            LinkedInExperienceLevel.INTERNSHIP,
            LinkedInExperienceLevel.ENTRY_LEVEL,
        ]
    )
    posted_within_days: int = Field(default=7, ge=1, le=30)
    tags: list[str] = Field(default_factory=list)


class LinkedInConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    searches: list[LinkedInSearch] = Field(default_factory=list)


class HandshakeSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: NonEmpty
    locations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class HandshakeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    # e.g. "upenn" → https://upenn.joinhandshake.com/
    school_subdomain: str | None = None
    searches: list[HandshakeSearch] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_subdomain_if_enabled(self) -> HandshakeConfig:
        if self.enabled and not self.school_subdomain:
            raise ValueError("handshake.enabled = true requires `school_subdomain`.")
        return self


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    """Top-level sources document."""

    model_config = ConfigDict(extra="forbid")

    companies: list[CompanyConfig] = Field(default_factory=list)
    linkedin: LinkedInConfig = Field(default_factory=LinkedInConfig)
    handshake: HandshakeConfig = Field(default_factory=HandshakeConfig)
    defaults: Defaults = Field(default_factory=Defaults)

    def enabled_companies(self, ats: AtsType | None = None) -> list[CompanyConfig]:
        """Return companies with ``enabled=True``, optionally filtered by ATS."""

        return [c for c in self.companies if c.enabled and (ats is None or c.ats is ats)]

    def effective_locations_for(self, entry: CompanyConfig) -> list[str]:
        """Per-entry location allow-list, falling back to ``defaults.locations``."""

        return entry.locations or self.defaults.locations


def load_sources_config(path: str | Path) -> SourcesConfig:
    """Parse a YAML file into a validated :class:`SourcesConfig`."""

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(
            f"Sources config YAML not found at {p!s}. "
            "Copy config/sources.example.yaml to config/sources.yaml and edit."
        )
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Sources YAML at {p!s} must be a mapping at the top level.")
    return SourcesConfig.model_validate(raw)
