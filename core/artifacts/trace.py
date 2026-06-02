"""Trace payload — THE MOAT made visible (per MD §6.2.1).

Every artifact carries this. It's what makes a decision audit-ready for a
regulated buyer:
    sourceFacts[]   the g-i-1 source items this rests on
    rulesFired[]    ordered rules from the derivation chain
    graphPath[]     edges traversed (with provenance + weight + trust)
    confidence      external + calibrated (g-i-2)
    uncertainty[]   visible flags (mandatory, not decorative)
    asOf            graph version + timestamp (reproducible later)

This trace is the FIRST-CLASS engine output for g-i-6 narrator + g-i-7 envelope.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.artifacts.uncertainty import (
    UncertaintyFlag,
    collect_uncertainty,
)
from core.graph.store import EdgeRow, FactRow


class SourceFactRef(BaseModel):
    """A fact referenced in the trace. Self-describing (no graph lookup needed by reader)."""

    model_config = ConfigDict(frozen=True)

    id: str
    subject: str
    predicate: str
    object: str
    source_item_id: str
    source_type: str = ""
    timestamp: datetime | None = None


class RuleFiringRef(BaseModel):
    """A rule firing in the proof chain."""

    model_config = ConfigDict(frozen=True)

    id: str
    priority: int
    matched_facts: dict[str, Any]
    conclusion: str


class EdgePathRef(BaseModel):
    """One edge traversed during reasoning. Provenance visible."""

    model_config = ConfigDict(frozen=True)

    id: str
    from_node: str
    to_node: str
    edge_type: str
    asserted_by_type: str
    asserted_by_id: str
    weight: float
    weight_source: str  # 'frequency' | 'human' | 'default'
    trust: float


class ConfidenceBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    overall: float
    breakdown: dict[str, float]


class AsOfPin(BaseModel):
    """Pins the exact graph version for replay reproducibility."""

    model_config = ConfigDict(frozen=True)

    graph_version: int
    timestamp: datetime


class Trace(BaseModel):
    """The audit-ready trace payload. Frozen + JSON-serializable for g-i-7 envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    org_id: str
    source_facts: list[SourceFactRef] = Field(default_factory=list)
    rules_fired: list[RuleFiringRef] = Field(default_factory=list)
    graph_path: list[EdgePathRef] = Field(default_factory=list)
    confidence: ConfidenceBreakdown
    uncertainty: list[UncertaintyFlag] = Field(default_factory=list)
    as_of: AsOfPin


def build_trace(
    session: Session,
    *,
    decision_id: str,
    org_id: str,
    derivation_chain: list[dict[str, Any]],
    grounding_ref_ids: Iterable[str],
    edge_path_ids: Iterable[str],
    confidence_overall: float,
    confidence_breakdown: dict[str, float],
    decision_path: str,
    as_of_version: int,
    as_of_timestamp: datetime,
) -> Trace:
    """Assemble the trace payload from already-emitted Decision data + graph state.

    Pure assembly — no reasoning. Read-only on the graph.
    """
    source_facts: list[SourceFactRef] = [
        f for f in (_load_source_fact_ref(session, fid) for fid in grounding_ref_ids) if f
    ]

    rules_fired = [
        RuleFiringRef(
            id=step.get("rule_id", "unknown"),
            priority=int(step.get("rule_priority", 0)),
            matched_facts=dict(step.get("matched_facts", {})),
            conclusion=step.get("conclusion", ""),
        )
        for step in derivation_chain
        if isinstance(step, dict) and step.get("rule_id")
    ]

    graph_path: list[EdgePathRef] = [
        e for e in (_load_edge_path_ref(session, eid) for eid in edge_path_ids) if e
    ]

    flags = collect_uncertainty(
        session,
        org_id=org_id,
        decision_path=decision_path,
        edge_ids_in_proof=edge_path_ids,
        derivation_chain=derivation_chain,
    )

    return Trace(
        decision_id=decision_id,
        org_id=org_id,
        source_facts=source_facts,
        rules_fired=rules_fired,
        graph_path=graph_path,
        confidence=ConfidenceBreakdown(overall=confidence_overall, breakdown=confidence_breakdown),
        uncertainty=flags,
        as_of=AsOfPin(graph_version=as_of_version, timestamp=as_of_timestamp),
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _load_source_fact_ref(session: Session, fact_id: str) -> SourceFactRef | None:
    row = session.get(FactRow, fact_id)
    if row is None:
        return None
    return SourceFactRef(
        id=row.id,
        subject=row.subject,
        predicate=row.predicate,
        object=row.object,
        source_item_id=row.source_item_id,
        timestamp=row.created_at,
    )


def _load_edge_path_ref(session: Session, edge_id: str) -> EdgePathRef | None:
    row = session.get(EdgeRow, edge_id)
    if row is None:
        return None
    return EdgePathRef(
        id=row.id,
        from_node=row.from_node,
        to_node=row.to_node,
        edge_type=row.type,
        asserted_by_type=row.asserted_by_type,
        asserted_by_id=row.asserted_by_id,
        weight=row.weight,
        weight_source=row.weight_source,
        trust=row.trust,
    )
