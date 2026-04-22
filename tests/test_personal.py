from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from src.config.personal import (
    PersonalInfo,
    RoleCategory,
    WorkAuthorization,
    load_personal_info,
)


def test_load_valid(personal_yaml: Path) -> None:
    info = load_personal_info(personal_yaml)
    assert isinstance(info, PersonalInfo)
    assert info.full_name == "Jane Doe"
    assert info.work_authorization is WorkAuthorization.US_CITIZEN
    assert info.education.university == "Example University"
    assert {v.name for v in info.resume_variants} == {RoleCategory.QUANT, RoleCategory.TECH}


def test_resume_for_category(personal_yaml: Path) -> None:
    info = load_personal_info(personal_yaml)
    quant = info.resume_for(RoleCategory.QUANT)
    assert quant.file_path == Path("resumes/quant.pdf")


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_personal_info(tmp_path / "does-not-exist.yaml")


def test_rejects_unknown_work_auth(tmp_path: Path) -> None:
    bad = tmp_path / "p.yaml"
    bad.write_text(
        """
full_name: "X"
email: "x@y.com"
phone: "1"
location: "NY"
work_authorization: nonexistent
education:
  university: "U"
  degree: "B"
  major: "M"
  graduation_date: 2026-05-15
resume_variants:
  - name: quant
    file_path: "r.pdf"
    description: "d"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_personal_info(bad)


def test_example_yaml_is_valid() -> None:
    """``config/personal.example.yaml`` must round-trip through the schema."""

    repo_root = Path(__file__).resolve().parents[1]
    info = load_personal_info(repo_root / "config" / "personal.example.yaml")
    assert info.full_name
    assert info.resume_variants
