"""ORM models for the job-application pipeline.

Mirrors the data model in ``docs/SYSTEM_DESIGN.md`` §1. All JSON-typed
columns use the cross-dialect :class:`sqlalchemy.JSON` so the same
schema works for SQLite (dev) and Postgres (prod).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class JobStatus(StrEnum):
    DISCOVERED = "discovered"
    MATCHED = "matched"
    NOTIFIED = "notified"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    OA_RECEIVED = "oa_received"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class Job(Base):
    """A single job posting, deduped on ``(source, external_id)``."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
        Index("ix_jobs_company", "company"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_role_category", "role_category"),
        Index("ix_jobs_discovered_at", "discovered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    application_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    description_raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_clean: Mapped[str] = mapped_column(Text, nullable=False, default="")

    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    role_category: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status", native_enum=False, length=32),
        nullable=False,
        default=JobStatus.DISCOVERED,
    )

    cover_letter_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resume_variant: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resume_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    referral_contacts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    discord_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    oa_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    email_events: Mapped[list[EmailEvent]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Job id={self.id} {self.company!r} — {self.title!r} [{self.status}]>"


class ResumeVariant(Base):
    """A resume file variant (e.g. ``quant`` / ``tech``).

    Mirrors the YAML-defined variants in ``config/personal.yaml`` so the
    pipeline has a persistent record of what was sent with each
    application (the YAML may evolve over time).
    """

    __tablename__ = "resume_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ReferralContact(Base):
    """A LinkedIn connection cross-referenced against target companies."""

    __tablename__ = "referral_contacts"
    __table_args__ = (
        Index("ix_referral_contacts_company", "company"),
        Index("ix_referral_contacts_linkedin_url", "linkedin_url", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    company: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    linkedin_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    connection_degree: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_synced: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EmailEvent(Base):
    """A Gmail message classified as relevant to an application."""

    __tablename__ = "email_events"
    __table_args__ = (
        Index("ix_email_events_gmail_message_id", "gmail_message_id", unique=True),
        Index("ix_email_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    gmail_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    job: Mapped[Job | None] = relationship(back_populates="email_events")
