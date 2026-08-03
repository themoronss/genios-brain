"""SQLAlchemy models for worldmodel-specific tables.

Per migration 0003 — extends the graph (which lives in core.graph.store):
- CorrectionRow      — structured human overrides
- CandidateEdgeRow   — lift-detected associations, propose-confirm only
- CandidateRuleRow   — clustered uncovered corrections -> rule-author prompt
- EntityMergeRow     — reversible merge log for resolve.py
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.foundations.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CorrectionRow(Base):
    """Structured human override of an engine decision. Feeds Bayesian update."""

    __tablename__ = "corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    input_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    engine_decision: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    human_decision: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    edge_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    timestamp: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (Index("ix_corrections_org_timestamp", "org_id", "timestamp"),)


class CandidateEdgeRow(Base):
    """Lift-detected (X,Y) association — proposed to a human; NEVER auto-asserted."""

    __tablename__ = "candidate_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_node: Mapped[str] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node: Mapped[str] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    signal_lift: Mapped[float] = mapped_column(Float, nullable=False)
    co_occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="proposed",
        comment="proposed | confirmed | rejected (rejected = negative memory)",
    )
    proposed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_candidate_edges_org_status", "org_id", "status"),
        Index("ix_candidate_edges_pair", "from_node", "to_node"),
    )


class CandidateRuleRow(Base):
    """Cluster of uncovered corrections -> humans author a hard rule."""

    __tablename__ = "candidate_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_correction_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="proposed",
        comment="proposed | authored | rejected",
    )
    proposed_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    authored_rule_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (Index("ix_candidate_rules_org_status", "org_id", "status"),)


class EntityMergeRow(Base):
    """Audit + reversibility log for entity resolution merges."""

    __tablename__ = "entity_merges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    merged_into: Mapped[str] = mapped_column(
        ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    merged_from: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    merged_by: Mapped[str] = mapped_column(String(255), nullable=False)
    merged_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
