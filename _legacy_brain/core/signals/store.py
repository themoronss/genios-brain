"""Signal Layer persistence — SignalRow + upsert + decayed read.

One CURRENT value per (org, subject, signal_type): detectors UPSERT. Read applies
half-life decay to numeric signals and returns a flat dict ready to merge into the
reasoning facts dict (`facts["ball_in_court"] = 1.0`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Double,
    Index,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import DateTime

from core.foundations.db import Base
from core.signals.types import SignalUpsert


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SignalRow(Base):
    """Mirrors migration 0030_signals. Current-value-only; UPSERT on the unique key."""

    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_node_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value_num: Mapped[float | None] = mapped_column(Double, nullable=True)
    value_cat: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Double, nullable=False, default=1.0)
    produced_by: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    as_of_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    half_life_days: Mapped[float | None] = mapped_column(Double, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id", "subject_node_id", "signal_type", name="uq_signals_subject_type"
        ),
        Index("ix_signals_org_subject", "org_id", "subject_node_id"),
        Index("ix_signals_org_type", "org_id", "signal_type"),
    )


def upsert_signal(session: Session, u: SignalUpsert) -> None:
    """Insert or refresh the current value for (org, subject, signal_type)."""
    now = _utcnow()
    stmt = (
        pg_insert(SignalRow)
        .values(
            id=_uuid(),
            org_id=u.org_id,
            subject_node_id=u.subject_node_id,
            subject_name=u.subject_name,
            signal_type=u.signal_type,
            value_num=u.value_num,
            value_cat=u.value_cat,
            confidence=u.confidence,
            produced_by=u.produced_by,
            evidence=list(u.evidence),
            as_of_version=u.as_of_version,
            half_life_days=u.half_life_days,
            computed_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_signals_subject_type",
            set_={
                "value_num": u.value_num,
                "value_cat": u.value_cat,
                "confidence": u.confidence,
                "produced_by": u.produced_by,
                "evidence": list(u.evidence),
                "as_of_version": u.as_of_version,
                "half_life_days": u.half_life_days,
                "computed_at": now,
            },
        )
    )
    session.execute(stmt)


def upsert_signals_bulk(session: Session, upserts: list[SignalUpsert]) -> int:
    """One INSERT ... ON CONFLICT for many signals — avoids N round-trips on a
    networked DB. Each (org, subject, signal_type) must be unique within the
    batch (one per node per type, so it is)."""
    if not upserts:
        return 0
    now = _utcnow()
    rows = [
        {
            "id": _uuid(),
            "org_id": u.org_id,
            "subject_node_id": u.subject_node_id,
            "subject_name": u.subject_name,
            "signal_type": u.signal_type,
            "value_num": u.value_num,
            "value_cat": u.value_cat,
            "confidence": u.confidence,
            "produced_by": u.produced_by,
            "evidence": list(u.evidence),
            "as_of_version": u.as_of_version,
            "half_life_days": u.half_life_days,
            "computed_at": now,
        }
        for u in upserts
    ]
    stmt = pg_insert(SignalRow).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_signals_subject_type",
        set_={
            "value_num": stmt.excluded.value_num,
            "value_cat": stmt.excluded.value_cat,
            "confidence": stmt.excluded.confidence,
            "produced_by": stmt.excluded.produced_by,
            "evidence": stmt.excluded.evidence,
            "as_of_version": stmt.excluded.as_of_version,
            "half_life_days": stmt.excluded.half_life_days,
            "computed_at": stmt.excluded.computed_at,
        },
    )
    session.execute(stmt)
    return len(rows)


def read_signals(
    session: Session,
    *,
    org_id: str,
    subject_node_id: str | None = None,
    subject_name: str | None = None,
) -> dict[str, float | str]:
    """Return {signal_type: value} for a subject, half-life-decayed on read.

    Numeric signals decay toward 0 by their half_life_days; categorical signals
    are returned as-is. Result is ready to merge into the reasoning facts dict.
    """
    stmt = select(SignalRow).where(SignalRow.org_id == org_id)
    if subject_node_id is not None:
        stmt = stmt.where(SignalRow.subject_node_id == subject_node_id)
    elif subject_name is not None:
        stmt = stmt.where(SignalRow.subject_name == subject_name)

    now = _utcnow()
    out: dict[str, float | str] = {}
    for row in session.execute(stmt).scalars():
        if row.value_num is not None:
            v = row.value_num
            if row.half_life_days:
                age_days = (now - row.computed_at).total_seconds() / 86400.0
                v = v * (0.5 ** (age_days / row.half_life_days))
            out[row.signal_type] = v
        elif row.value_cat is not None:
            out[row.signal_type] = row.value_cat
    return out
