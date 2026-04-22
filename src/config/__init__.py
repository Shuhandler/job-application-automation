"""Typed configuration surfaces.

- ``settings`` — secrets + environment (loaded from ``.env``)
- ``personal`` — personal info profile (loaded from YAML)
"""

from src.config.personal import PersonalInfo, load_personal_info
from src.config.settings import Settings, get_settings
from src.config.sources import (
    AtsType,
    CompanyConfig,
    CustomSelectors,
    HandshakeConfig,
    HandshakeSearch,
    LinkedInConfig,
    LinkedInExperienceLevel,
    LinkedInSearch,
    SourcesConfig,
    load_sources_config,
)

__all__ = [
    "AtsType",
    "CompanyConfig",
    "CustomSelectors",
    "HandshakeConfig",
    "HandshakeSearch",
    "LinkedInConfig",
    "LinkedInExperienceLevel",
    "LinkedInSearch",
    "PersonalInfo",
    "Settings",
    "SourcesConfig",
    "get_settings",
    "load_personal_info",
    "load_sources_config",
]
