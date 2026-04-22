"""Personal info profile loaded from YAML.

Schema is defined with Pydantic so the YAML file is validated on load.
Keep secrets out of this file — those belong in ``.env`` and are handled
by :mod:`src.config.settings`.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, StringConstraints


class WorkAuthorization(StrEnum):
    US_CITIZEN = "us_citizen"
    US_PERMANENT_RESIDENT = "us_permanent_resident"
    F1_OPT = "f1_opt"
    F1_CPT = "f1_cpt"
    H1B = "h1b"
    REQUIRES_SPONSORSHIP = "requires_sponsorship"
    OTHER = "other"


class RoleCategory(StrEnum):
    QUANT = "quant"
    TECH = "tech"


NonEmpty = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")

    university: NonEmpty
    degree: NonEmpty
    major: NonEmpty
    minor: str | None = None
    gpa: float | None = Field(default=None, ge=0.0, le=4.0)
    graduation_date: date
    coursework: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: NonEmpty
    title: NonEmpty
    start_date: date
    end_date: date | None = None  # None = current
    location: str | None = None
    bullets: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonEmpty
    description: NonEmpty
    url: HttpUrl | None = None
    tech_stack: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    model_config = ConfigDict(extra="forbid")

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    math: list[str] = Field(default_factory=list)  # e.g. ["stochastic calculus", "probability"]
    other: list[str] = Field(default_factory=list)


class ResumeVariantConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleCategory
    file_path: Path
    description: NonEmpty
    keywords: list[str] = Field(default_factory=list)


class Links(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linkedin: HttpUrl | None = None
    github: HttpUrl | None = None
    portfolio: HttpUrl | None = None
    scholar: HttpUrl | None = None


class PersonalInfo(BaseModel):
    """Top-level profile document."""

    model_config = ConfigDict(extra="forbid")

    full_name: NonEmpty
    preferred_name: str | None = None
    email: EmailStr
    phone: NonEmpty
    location: NonEmpty  # "City, State"
    work_authorization: WorkAuthorization
    requires_sponsorship_now: bool = False
    requires_sponsorship_future: bool = False

    education: Education
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    links: Links = Field(default_factory=Links)

    resume_variants: list[ResumeVariantConfig]

    def resume_for(self, category: RoleCategory) -> ResumeVariantConfig:
        """Return the :class:`ResumeVariantConfig` for ``category``.

        Raises ``KeyError`` if the user hasn't declared a variant for
        that category — caller decides whether to fall back or surface
        the error.
        """

        for v in self.resume_variants:
            if v.name is category:
                return v
        raise KeyError(f"No resume variant declared for role category {category!r}")


def load_personal_info(path: str | Path) -> PersonalInfo:
    """Parse a YAML file into a validated :class:`PersonalInfo`."""

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(
            f"Personal info YAML not found at {p!s}. "
            "Copy config/personal.example.yaml to config/personal.yaml and edit."
        )
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Personal info YAML at {p!s} must be a mapping at the top level.")
    return PersonalInfo.model_validate(raw)
