"""Signal Layer runtime — compute symbolic signals on tick, and merge a subject's
signals into the reasoning facts dict.

- run_symbolic_detectors: reads graph state, calls the pure detectors, UPSERTs.
- merge_signals_into_facts: read + decay a subject's signals into the facts dict
  the ForwardChainer consumes. Caller-supplied facts ALWAYS win on conflict
  (signals never override structured truth).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.graph.store import EdgeRow, FactRow, NodeRow
from core.signals.detectors import symbolic as det
from core.signals.store import read_signals, upsert_signal
from core.signals.types import (
    SIG_ENGAGEMENT,
    SIG_IMPORTANCE,
    SIG_MOMENTUM,
    SignalUpsert,
)


def _naive_utc(dt: datetime) -> datetime:
    """graph_nodes datetimes are naive UTC; normalize for arithmetic."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def run_symbolic_detectors(session: Session, *, org_id: str, now: datetime | None = None) -> int:
    """Recompute engagement / momentum / importance for every entity node. Returns
    the number of signals written. No LLM — pure DB reads + arithmetic on tick."""
    now = _naive_utc(now or datetime.now(UTC))
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    nodes = (
        session.execute(
            select(NodeRow).where(NodeRow.org_id == org_id, NodeRow.type == "entity")
        )
        .scalars()
        .all()
    )

    written = 0
    for node in nodes:
        name = node.canonical_name

        def _fcount(*conds) -> int:
            return (
                session.execute(
                    select(func.count())
                    .select_from(FactRow)
                    .where(FactRow.org_id == org_id, FactRow.subject == name, *conds)
                ).scalar()
                or 0
            )

        total = _fcount()
        recent = _fcount(FactRow.created_at >= week_ago)
        prior = _fcount(FactRow.created_at < week_ago, FactRow.created_at >= month_ago)
        edges = (
            session.execute(
                select(func.count())
                .select_from(EdgeRow)
                .where(
                    EdgeRow.org_id == org_id,
                    or_(EdgeRow.from_node == node.id, EdgeRow.to_node == node.id),
                )
            ).scalar()
            or 0
        )
        days = (now - _naive_utc(node.last_seen)).total_seconds() / 86400.0

        base = dict(org_id=org_id, subject_node_id=node.id, subject_name=name, produced_by="symbolic")
        upsert_signal(
            session,
            SignalUpsert(signal_type=SIG_ENGAGEMENT, value_num=det.engagement_level(days, total), half_life_days=14, **base),
        )
        upsert_signal(
            session,
            SignalUpsert(signal_type=SIG_MOMENTUM, value_num=det.momentum(recent, prior), half_life_days=10, **base),
        )
        upsert_signal(
            session,
            SignalUpsert(signal_type=SIG_IMPORTANCE, value_num=det.importance(node.attributes or {}, edges), **base),
        )
        written += 3
    return written


def merge_signals_into_facts(
    session: Session,
    *,
    org_id: str,
    facts: dict,
    subject_node_id: str | None = None,
    subject_name: str | None = None,
) -> dict:
    """Merge a subject's (decayed) signals under the facts dict. Caller facts win."""
    sig = read_signals(
        session, org_id=org_id, subject_node_id=subject_node_id, subject_name=subject_name
    )
    merged: dict = dict(sig)
    merged.update(facts)  # structured truth overrides derived signals on conflict
    return merged
