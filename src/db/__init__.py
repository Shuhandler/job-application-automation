"""Database layer — SQLAlchemy 2.0 models + session management."""

from src.db.base import Base, SessionLocal, engine, get_session
from src.db.models import (
    EmailEvent,
    Job,
    JobStatus,
    ReferralContact,
    ResumeVariant,
)

__all__ = [
    "Base",
    "EmailEvent",
    "Job",
    "JobStatus",
    "ReferralContact",
    "ResumeVariant",
    "SessionLocal",
    "engine",
    "get_session",
]
