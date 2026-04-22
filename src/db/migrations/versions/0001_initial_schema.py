"""Initial schema: jobs, resume_variants, referral_contacts, email_events.

Revision ID: 0001
Revises:
Create Date: 2026-04-22

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JOB_STATUS_VALUES = (
    "discovered",
    "matched",
    "notified",
    "submitted",
    "confirmed",
    "oa_received",
    "interview",
    "offer",
    "rejected",
    "skipped",
)


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("application_url", sa.String(length=2048), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_clean", sa.Text(), nullable=False, server_default=""),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matched_keywords", sa.JSON(), nullable=False),
        sa.Column("role_category", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.Enum(*JOB_STATUS_VALUES, name="job_status", native_enum=False, length=32),
            nullable=False,
            server_default="discovered",
        ),
        sa.Column("cover_letter_path", sa.String(length=1024), nullable=True),
        sa.Column("resume_variant", sa.String(length=32), nullable=True),
        sa.Column("resume_match_score", sa.Float(), nullable=True),
        sa.Column("referral_contacts", sa.JSON(), nullable=False),
        sa.Column("discord_message_id", sa.Integer(), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oa_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interview_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )
    op.create_index("ix_jobs_company", "jobs", ["company"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_role_category", "jobs", ["role_category"])
    op.create_index("ix_jobs_discovered_at", "jobs", ["discovered_at"])

    op.create_table(
        "resume_variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=32), nullable=False, unique=True),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )

    op.create_table(
        "referral_contacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("company", sa.String(length=256), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("linkedin_url", sa.String(length=1024), nullable=False),
        sa.Column("connection_degree", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_synced",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_referral_contacts_company", "referral_contacts", ["company"])
    op.create_index(
        "ix_referral_contacts_linkedin_url",
        "referral_contacts",
        ["linkedin_url"],
        unique=True,
    )

    op.create_table(
        "email_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gmail_message_id", sa.String(length=128), nullable=False),
        sa.Column("sender", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("extracted_data", sa.JSON(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_email_events_gmail_message_id",
        "email_events",
        ["gmail_message_id"],
        unique=True,
    )
    op.create_index("ix_email_events_event_type", "email_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_email_events_event_type", table_name="email_events")
    op.drop_index("ix_email_events_gmail_message_id", table_name="email_events")
    op.drop_table("email_events")

    op.drop_index("ix_referral_contacts_linkedin_url", table_name="referral_contacts")
    op.drop_index("ix_referral_contacts_company", table_name="referral_contacts")
    op.drop_table("referral_contacts")

    op.drop_table("resume_variants")

    op.drop_index("ix_jobs_discovered_at", table_name="jobs")
    op.drop_index("ix_jobs_role_category", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_company", table_name="jobs")
    op.drop_table("jobs")
