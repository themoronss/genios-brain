"""Temporal queries over the shared graph — as_of / diff / history.

Per MD g-i-3 §3.1.2:
- as_of(T)       reconstruct graph state at time T (snapshot <= T + replay events to T)
- diff(T1, T2)   set of node/edge/weight changes between two times
- history(id)    ordered changes for a single edge/node with provenance

Snapshot policy:
- Periodic (daily by default) + on-significant-change
- Forward diffs in graph_events; snapshot + replay <= K events for any as_of

The actual snapshot writer is a small scheduled job (lands when first cron runs).
This module exposes the read API + snapshot helpers (capture_snapshot, replay_to).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.config import SNAPSHOT_INTERVAL_HOURS
from core.foundations.telemetry import get_logger
from core.graph.store import GraphEventRow, GraphSnapshotRow, current_version

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# as_of / diff / history result types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AsOfState:
    """Reconstructed graph state at a point in time."""

    org_id: str
    as_of: datetime
    version: int
    nodes: dict[str, dict[str, Any]]
    edges: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class GraphDiff:
    """Set of changes between two times."""

    org_id: str
    from_time: datetime
    to_time: datetime
    events: list[dict[str, Any]]


@dataclass(frozen=True)
class HistoryEntry:
    """One event in a target's history."""

    version: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Reads
# ─────────────────────────────────────────────────────────────────────────────


def as_of(session: Session, *, org_id: str, when: datetime) -> AsOfState:
    """Reconstruct graph state at time `when`.

    Strategy: find latest snapshot <= when, replay events from snapshot up to when.
    """
    snapshot = _latest_snapshot_before(session, org_id=org_id, when=when)
    if snapshot is None:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        from_version = 0
    else:
        snap_payload = snapshot.snapshot
        nodes = dict(snap_payload.get("nodes", {}))
        edges = dict(snap_payload.get("edges", {}))
        from_version = snapshot.version

    events = (
        session.execute(
            select(GraphEventRow)
            .where(GraphEventRow.org_id == org_id)
            .where(GraphEventRow.version > from_version)
            .where(GraphEventRow.created_at <= when)
            .order_by(GraphEventRow.version)
        )
        .scalars()
        .all()
    )

    version = from_version
    for ev in events:
        _apply_event(nodes, edges, ev)
        version = ev.version

    return AsOfState(org_id=org_id, as_of=when, version=version, nodes=nodes, edges=edges)


def diff(session: Session, *, org_id: str, from_time: datetime, to_time: datetime) -> GraphDiff:
    """Return all events between two times."""
    if from_time > to_time:
        raise ValueError("from_time must be <= to_time")
    events = (
        session.execute(
            select(GraphEventRow)
            .where(GraphEventRow.org_id == org_id)
            .where(GraphEventRow.created_at > from_time)
            .where(GraphEventRow.created_at <= to_time)
            .order_by(GraphEventRow.version)
        )
        .scalars()
        .all()
    )
    return GraphDiff(
        org_id=org_id,
        from_time=from_time,
        to_time=to_time,
        events=[
            {
                "version": e.version,
                "event_type": e.event_type,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    )


def history(session: Session, *, org_id: str, target_id: str) -> list[HistoryEntry]:
    """All events for one target (node or edge) in chronological order."""
    events = (
        session.execute(
            select(GraphEventRow)
            .where(GraphEventRow.org_id == org_id)
            .where(GraphEventRow.target_id == target_id)
            .order_by(GraphEventRow.version)
        )
        .scalars()
        .all()
    )
    return [
        HistoryEntry(
            version=e.version,
            event_type=e.event_type,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot capture + policy
# ─────────────────────────────────────────────────────────────────────────────


def capture_snapshot(
    session: Session,
    *,
    org_id: str,
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
) -> GraphSnapshotRow:
    """Persist a snapshot at the current version. Caller decides when to call."""
    version = current_version(session, org_id)
    row = GraphSnapshotRow(
        org_id=org_id,
        version=version,
        snapshot={"nodes": nodes, "edges": edges},
    )
    session.add(row)
    session.flush()
    audit.record(
        org_id=org_id,
        actor_type="system",
        actor_id="temporal.capture_snapshot",
        action="config_changed",
        target_type="snapshot",
        target_id=row.id,
        metadata={"version": version, "nodes_count": len(nodes), "edges_count": len(edges)},
    )
    return row


def should_snapshot(
    session: Session,
    *,
    org_id: str,
    significant_change_threshold: int = 100,
) -> bool:
    """Decide if a new snapshot is due.

    Either (a) more than SNAPSHOT_INTERVAL_HOURS since last snapshot, OR
           (b) > significant_change_threshold events since last snapshot.
    """
    latest = _latest_snapshot(session, org_id=org_id)
    if latest is None:
        return True

    age_hours = (datetime.now(UTC) - _to_utc(latest.created_at)).total_seconds() / 3600.0
    if age_hours >= SNAPSHOT_INTERVAL_HOURS:
        return True

    events_since = (
        session.execute(
            select(GraphEventRow)
            .where(GraphEventRow.org_id == org_id)
            .where(GraphEventRow.version > latest.version)
        )
        .scalars()
        .all()
    )
    return len(list(events_since)) >= significant_change_threshold


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


def _latest_snapshot_before(
    session: Session, *, org_id: str, when: datetime
) -> GraphSnapshotRow | None:
    return session.execute(
        select(GraphSnapshotRow)
        .where(GraphSnapshotRow.org_id == org_id)
        .where(GraphSnapshotRow.created_at <= when)
        .order_by(GraphSnapshotRow.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def _latest_snapshot(session: Session, *, org_id: str) -> GraphSnapshotRow | None:
    return session.execute(
        select(GraphSnapshotRow)
        .where(GraphSnapshotRow.org_id == org_id)
        .order_by(GraphSnapshotRow.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def _apply_event(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    ev: GraphEventRow,
) -> None:
    """Apply one event onto a mutable state dict. Caller persists nothing here."""
    target = ev.target_id
    payload = dict(ev.payload)
    if ev.event_type == "node_add":
        nodes[target] = payload
    elif ev.event_type == "node_update":
        nodes.setdefault(target, {}).update(payload)
    elif ev.event_type == "edge_add":
        edges[target] = payload
    elif ev.event_type in {"edge_update", "weight_update"}:
        edges.setdefault(target, {}).update(payload)
    elif ev.event_type == "merge":
        absorbed_ids = payload.get("absorbed", [])
        if isinstance(absorbed_ids, list):
            for aid in absorbed_ids:
                nodes.pop(str(aid), None)
        kept = payload.get("kept_state")
        if isinstance(kept, dict):
            nodes[target] = dict(kept)
    elif ev.event_type == "unmerge":
        restored = payload.get("restored", [])
        if isinstance(restored, list):
            for snap in restored:
                if isinstance(snap, dict) and "id" in snap:
                    nodes[str(snap["id"])] = dict(snap)


def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# ─────────────────────────────────────────────────────────────────────────────
# Event-writer convenience (so callers don't reinvent versioning)
# ─────────────────────────────────────────────────────────────────────────────


def append_event(
    session: Session,
    *,
    org_id: str,
    event_type: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any],
) -> GraphEventRow:
    """Allocate next version + write event. Caller commits."""
    from core.graph.store import next_version

    version = next_version(session, org_id)
    row = GraphEventRow(
        org_id=org_id,
        version=version,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
    )
    session.add(row)
    session.flush()
    return row


def replay_events_iter(
    session: Session,
    *,
    org_id: str,
    from_version: int,
    to_version: int | None = None,
) -> Iterable[GraphEventRow]:
    """Stream events for an org between two versions (inclusive of bounds)."""
    q = (
        select(GraphEventRow)
        .where(GraphEventRow.org_id == org_id)
        .where(GraphEventRow.version >= from_version)
    )
    if to_version is not None:
        q = q.where(GraphEventRow.version <= to_version)
    q = q.order_by(GraphEventRow.version)
    return session.execute(q).scalars().all()
