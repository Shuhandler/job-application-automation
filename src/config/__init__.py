"""Typed configuration surfaces.

- ``settings`` — secrets + environment (loaded from ``.env``)
- ``personal`` — personal info profile (loaded from YAML)
"""

from src.config.personal import PersonalInfo, load_personal_info
from src.config.settings import Settings, get_settings

__all__ = [
    "PersonalInfo",
    "Settings",
    "get_settings",
    "load_personal_info",
]
