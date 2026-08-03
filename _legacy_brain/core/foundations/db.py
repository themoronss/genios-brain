"""SQLAlchemy 2.0 engine + session.

Sync engine — keeps the codebase consistent with Celery + simpler to reason about
at 10-15 startup scale. Async can come later behind the same Session interface
if real load demands.

Use:
    from core.foundations.db import get_session
    with get_session() as session:
        session.execute(...)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.foundations.config import settings


class Base(DeclarativeBase):
    """Single declarative base for all v2 models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _init_engine() -> tuple[Engine, sessionmaker[Session]]:
    """Lazy engine init so tests can override DATABASE_URL before first use."""
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,  # detect dropped connections
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,  # 30 min — survives Supabase idle timeouts
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine, factory


def get_engine() -> Engine:
    """Return the singleton engine. Initializes on first call."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine, _SessionLocal = _init_engine()
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a session in a context manager.

    Commits on clean exit, rolls back on exception, always closes.
    Caller does NOT call commit/rollback/close explicitly.
    """
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
