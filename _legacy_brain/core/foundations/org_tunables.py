"""Per-org tunable override store + resolver.

The pattern (per config.py header):
    Engine first reads `org_tunables` for (org_id, key); falls back to the
    module-level default in `config.py`.

Why a table:
    Customer onboards on the "default" tier → all defaults apply (zero rows).
    When they upgrade to a paid tier, ops inserts override rows — engine picks
    them up on the next read (cached briefly to avoid DB hit per call).

Schema:
    org_tunables(org_id, key, value_jsonb, set_by, set_at, reason)

The store is intentionally small + opinionated:
- Values are JSON (covers int/float/str/dict/list)
- Caller never mutates a default in-place — uses `set_tunable()` to record
- A 60-second in-process cache cuts DB chatter; flushed via `clear_cache()`
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Index, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from core.foundations import audit, config
from core.foundations.db import Base
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


CACHE_TTL_SECONDS = 60.0

_MISSING = object()


class OrgTunableRow(Base):
    """One row per (org_id, key). UPSERT via set_tunable()."""

    __tablename__ = "org_tunables"

    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_jsonb: Mapped[Any] = mapped_column(JSON, nullable=False)
    set_by: Mapped[str] = mapped_column(String(128), nullable=False)
    set_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(UTC))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_org_tunables_org_key"),
        Index("ix_org_tunables_org", "org_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────────────────


_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}


def clear_cache() -> None:
    """Drop the in-process cache. Call from set_tunable + tests."""
    _CACHE.clear()


def _cached(org_id: str, key: str) -> Any:
    entry = _CACHE.get((org_id, key))
    if entry is None:
        return _MISSING
    expires_at, value = entry
    if expires_at < time.monotonic():
        _CACHE.pop((org_id, key), None)
        return _MISSING
    return value


def _store(org_id: str, key: str, value: Any) -> None:
    _CACHE[(org_id, key)] = (time.monotonic() + CACHE_TTL_SECONDS, value)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def get_tunable(session: Session, *, org_id: str, key: str, default: Any = _MISSING) -> Any:
    """Resolve a tunable for one org.

    Order:
    1. Per-org override (cached 60s)
    2. Caller-supplied `default`
    3. Module-level default in `config.py`

    Raises ValueError if no default available anywhere.
    """
    cached = _cached(org_id, key)
    if cached is not _MISSING:
        return cached

    row = session.execute(
        select(OrgTunableRow)
        .where(OrgTunableRow.org_id == org_id)
        .where(OrgTunableRow.key == key)
    ).scalar_one_or_none()

    if row is not None:
        _store(org_id, key, row.value_jsonb)
        return row.value_jsonb

    if default is not _MISSING:
        return default

    fallback = getattr(config, key, _MISSING)
    if fallback is _MISSING:
        raise ValueError(
            f"Tunable '{key}' has no per-org override, no caller default, "
            f"and no module-level default in core.foundations.config"
        )
    return fallback


def set_tunable(
    session: Session,
    *,
    org_id: str,
    key: str,
    value: Any,
    set_by: str,
    reason: str | None = None,
) -> OrgTunableRow:
    """UPSERT an override + log to audit. Caller commits."""
    existing = session.execute(
        select(OrgTunableRow)
        .where(OrgTunableRow.org_id == org_id)
        .where(OrgTunableRow.key == key)
    ).scalar_one_or_none()

    if existing is None:
        row = OrgTunableRow(
            org_id=org_id,
            key=key,
            value_jsonb=value,
            set_by=set_by,
            reason=reason,
        )
        session.add(row)
    else:
        existing.value_jsonb = value
        existing.set_by = set_by
        existing.set_at = datetime.now(UTC)
        existing.reason = reason
        row = existing
    session.flush()

    audit.record_db(
        session,
        org_id=org_id,
        actor_type="system" if set_by.startswith("system:") else "user",
        actor_id=set_by,
        action="config_changed",
        target_type="org_tunable",
        target_id=key,
        metadata={"reason": reason or ""},
    )
    _CACHE.pop((org_id, key), None)
    log.info(
        "org_tunable_set", org_id=org_id, key=key, set_by=set_by, reason=reason or ""
    )
    return row


def delete_tunable(
    session: Session, *, org_id: str, key: str, set_by: str
) -> bool:
    """Drop an override (org falls back to the module-level default). Returns deleted-flag."""
    row = session.execute(
        select(OrgTunableRow)
        .where(OrgTunableRow.org_id == org_id)
        .where(OrgTunableRow.key == key)
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    audit.record_db(
        session,
        org_id=org_id,
        actor_type="system" if set_by.startswith("system:") else "user",
        actor_id=set_by,
        action="config_changed",
        target_type="org_tunable",
        target_id=key,
        metadata={"op": "deleted"},
    )
    _CACHE.pop((org_id, key), None)
    log.info("org_tunable_deleted", org_id=org_id, key=key, set_by=set_by)
    return True


def list_overrides(session: Session, *, org_id: str) -> dict[str, Any]:
    """Return {key: value} for every override the org has."""
    rows = (
        session.execute(select(OrgTunableRow).where(OrgTunableRow.org_id == org_id))
        .scalars()
        .all()
    )
    return {r.key: r.value_jsonb for r in rows}
