"""SQLAlchemy models for the shared graph + temporal queries.

Per MD g-i-2 + g-i-3:
- Append-only event log of graph mutations for versioning + replay
- Periodic snapshots (snapshot + forward diffs to bound storage)
- as_of(T) / diff(T1, T2) / history(edge_id) queries

Tables (all org-scoped):
- graph_nodes      — current node state
- graph_edges      — current edge state (with Bayesian alpha/beta + status)
- graph_events     — append-only mutation log (the source of truth for replay)
- graph_snapshots  — periodic state captures (replay shortcut)
- facts            — SPO assertions (linked to source_item_id from g-i-1)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────────
# Facts
# ─────────────────────────────────────────────────────────────────────────────


class FactRow(Base):
    """Subject-Predicate-Object assertions grounded in source MemoryItems."""

    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    object: Mapped[str] = mapped_column(Text, nullable=False)
    source_item_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Pointer to g-i-1 MemoryItem stable id",
    )
    asserted_by_type: Mapped[str] = mapped_column(String(16), nullable=False)
    asserted_by_id: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_facts_org_subject", "org_id", "subject"),
        Index("ix_facts_org_predicate", "org_id", "predicate"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────


class NodeRow(Base):
    """Graph node. Entities carry resolution fields."""

    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_unit: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Per-org-unit namespacing for cross-team isolation within an org",
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    first_seen: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_nodes_org_canonical", "org_id", "canonical_name"),
        Index("ix_nodes_org_type", "org_id", "type"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Edges (with Bayesian state + status)
# ─────────────────────────────────────────────────────────────────────────────


class EdgeRow(Base):
    """Graph edge. Provenance + weight provenance + Bayesian Beta(alpha, beta)."""

    __tablename__ = "graph_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_node: Mapped[str] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_node: Mapped[str] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    asserted_by_type: Mapped[str] = mapped_column(String(16), nullable=False)
    asserted_by_id: Mapped[str] = mapped_column(String(255), nullable=False)
    asserted_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    weight_source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="default",
        comment="frequency | human | default — MANDATORY provenance",
    )
    alpha: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    beta: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    decay_lambda: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="asserted",
        comment="asserted | candidate (g-i-3 propose-confirm)",
    )

    __table_args__ = (
        Index("ix_edges_org_from", "org_id", "from_node"),
        Index("ix_edges_org_to", "org_id", "to_node"),
        Index("ix_edges_org_type_status", "org_id", "type", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Append-only mutation log (the source of truth for replay)
# ─────────────────────────────────────────────────────────────────────────────


class GraphEventRow(Base):
    """Every mutation logged here, indexed by monotonic version per org.

    Replay strategy: snapshot <= V + replay events up to V → state at version V.
    """

    __tablename__ = "graph_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Monotonic per-org version. Snapshot+events≤V reconstruct state at V.",
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="node_add | node_update | edge_add | edge_update | weight_update | merge | unmerge",
    )
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)  # node | edge | fact
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_events_org_version", "org_id", "version"),
        Index("ix_events_org_created", "org_id", "created_at"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Periodic snapshots (replay shortcut)
# ─────────────────────────────────────────────────────────────────────────────


class GraphSnapshotRow(Base):
    """Periodic graph-state snapshot. Forward diffs stored in graph_events."""

    __tablename__ = "graph_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Compact graph state (nodes + edges + facts subset relevant to reasoning)",
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_snapshots_org_version", "org_id", "version"),)


# ─────────────────────────────────────────────────────────────────────────────
# Temporal queries (as_of / diff / history)
# ─────────────────────────────────────────────────────────────────────────────


def current_version(session: Any, org_id: str) -> int:
    """Highest graph_events.version for an org. 0 if never mutated."""
    from sqlalchemy import func, select

    result = session.execute(
        select(func.coalesce(func.max(GraphEventRow.version), 0)).where(
            GraphEventRow.org_id == org_id
        )
    ).scalar_one()
    return int(result)


def next_version(session: Any, org_id: str) -> int:
    """Allocate the next monotonic version for an org. Caller writes the event row."""
    return current_version(session, org_id) + 1
