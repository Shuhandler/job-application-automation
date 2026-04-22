"""SQLAlchemy engine, session factory, and declarative base.

Phase 0 uses a sync engine only. An async engine can be layered in
at Phase 5 (Discord bot) without touching the models — just construct
``create_async_engine(...)`` against the same URL and reuse
:class:`Base`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _make_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url

    if url.startswith("sqlite"):
        # Ensure the parent directory of a file-backed SQLite URL exists
        # (e.g. ``sqlite:///./data/app.db``). Skip for ``:memory:``.
        if ":memory:" not in url:
            db_path = url.split("sqlite:///", 1)[-1]
            if db_path and db_path != url:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        eng = create_engine(url, future=True, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _enable_sqlite_fks(dbapi_conn, _):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return eng

    return create_engine(url, future=True, pool_pre_ping=True)


engine: Engine = _make_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed DB session with commit-on-exit / rollback-on-error."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
