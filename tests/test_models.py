from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.db.models import EmailEvent, Job, JobStatus, ReferralContact, ResumeVariant


def _make_job(**overrides: object) -> Job:
    defaults: dict[str, object] = {
        "source": "greenhouse:janestreet",
        "external_id": "12345",
        "title": "Quantitative Researcher — New Grad",
        "company": "Jane Street",
        "url": "https://boards.greenhouse.io/janestreet/jobs/12345",
        "application_url": "https://boards.greenhouse.io/janestreet/jobs/12345",
        "description_raw": "We are looking for...",
        "description_clean": "We are looking for...",
        "relevance_score": 0.87,
        "matched_keywords": ["quant", "C++", "probability"],
        "role_category": "quant",
        "status": JobStatus.MATCHED,
        "referral_contacts": [],
    }
    defaults.update(overrides)
    return Job(**defaults)


def test_job_roundtrip(db_session: Session) -> None:
    job = _make_job()
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id is not None
    assert job.status is JobStatus.MATCHED
    assert job.matched_keywords == ["quant", "C++", "probability"]
    assert job.discovered_at is not None


def test_job_unique_source_external_id(db_session: Session) -> None:
    db_session.add(_make_job())
    db_session.commit()

    db_session.add(_make_job())
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_email_event_relationship(db_session: Session) -> None:
    job = _make_job(external_id="email-link-1")
    db_session.add(job)
    db_session.commit()

    ev = EmailEvent(
        job_id=job.id,
        gmail_message_id="msg-1",
        sender="noreply@janestreet.com",
        subject="Application received",
        received_at=datetime.now(UTC),
        event_type="confirmation",
        extracted_data={},
    )
    db_session.add(ev)
    db_session.commit()
    db_session.refresh(job)

    assert len(job.email_events) == 1
    assert job.email_events[0].event_type == "confirmation"


def test_resume_variant_unique_name(db_session: Session) -> None:
    db_session.add(ResumeVariant(name="quant", file_path="a.pdf", keywords=[]))
    db_session.commit()
    db_session.add(ResumeVariant(name="quant", file_path="b.pdf", keywords=[]))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_referral_contact_unique_linkedin_url(db_session: Session) -> None:
    db_session.add(
        ReferralContact(
            name="A",
            company="Jane Street",
            title="SWE",
            linkedin_url="https://linkedin.com/in/a",
            connection_degree=1,
        )
    )
    db_session.commit()
    db_session.add(
        ReferralContact(
            name="A Dup",
            company="Jane Street",
            title="SWE",
            linkedin_url="https://linkedin.com/in/a",
            connection_degree=1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
