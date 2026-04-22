from __future__ import annotations

from sqlalchemy.orm import Session
from src.db.models import Job
from src.scrapers.base import JobPayload
from src.scrapers.persistence import upsert_jobs


def _p(ext_id: str, title: str = "Role", company: str = "Acme") -> JobPayload:
    return JobPayload(
        source="greenhouse:acme",
        external_id=ext_id,
        title=title,
        company=company,
        url=f"https://example.com/{ext_id}",
        application_url=f"https://example.com/{ext_id}",
        description_raw="",
        description_clean="",
    )


def test_upsert_inserts_new(db_session: Session) -> None:
    n = upsert_jobs(db_session, [_p("1"), _p("2"), _p("3")])
    db_session.commit()
    assert n == 3
    assert db_session.query(Job).count() == 3


def test_upsert_skips_duplicates(db_session: Session) -> None:
    upsert_jobs(db_session, [_p("1"), _p("2")])
    db_session.commit()
    n = upsert_jobs(db_session, [_p("1"), _p("2"), _p("3")])
    db_session.commit()
    assert n == 1
    assert db_session.query(Job).count() == 3


def test_upsert_empty_is_noop(db_session: Session) -> None:
    assert upsert_jobs(db_session, []) == 0


def test_upsert_isolated_by_source(db_session: Session) -> None:
    payloads = [
        JobPayload(
            source="greenhouse:acme",
            external_id="1",
            title="a",
            company="Acme",
            url="https://example.com/1",
            application_url="https://example.com/1",
        ),
        JobPayload(
            source="lever:acme",  # different source, same external_id
            external_id="1",
            title="a",
            company="Acme",
            url="https://example.com/1b",
            application_url="https://example.com/1b",
        ),
    ]
    n = upsert_jobs(db_session, payloads)
    db_session.commit()
    assert n == 2
