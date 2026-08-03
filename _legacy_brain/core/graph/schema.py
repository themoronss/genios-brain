"""Engine-facing types for the shared graph.

Per MD g-i-2 §2.1.1 + g-i-3 §3.2.1:
- Edge types: temporal, dependency, influence  (influence ASSERTED only — never auto from temporal)
- Weight source: frequency | human | default  (MANDATORY — no naked numbers)
- Edge status: asserted | candidate            (g-i-3 propose-confirm adds 'candidate')
- Bayesian params alpha/beta per edge for correction-driven learning (g-i-3)

These are read/write contracts. Persistence lives in store.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class NodeType(StrEnum):
    """Per MD g-i-2 §2.1.1."""

    ENTITY = "entity"  # account, contact, rep
    EVENT = "event"  # demo, email, stage-change
    GOAL = "goal"  # close deal, reduce churn
    RISK = "risk"
    DEPENDENCY = "dependency"


class EdgeType(StrEnum):
    """Per MD g-i-2 §2.1.1. INFLUENCE is asserted-only (never auto from TEMPORAL)."""

    TEMPORAL = "temporal"  # A before B
    DEPENDENCY = "dependency"  # A needs B
    INFLUENCE = "influence"  # A affects B — ASSERTED only (rule or human)


class WeightSource(StrEnum):
    """Per MD g-i-2 §2.1.1 — provenance MANDATORY for every weight."""

    FREQUENCY = "frequency"  # derived from co-occurrence (Laplace smoothed)
    HUMAN = "human"  # set by a human (highest trust)
    DEFAULT = "default"  # below N_min evidence — flagged as low-trust


class AssertionSource(StrEnum):
    """Who/what asserted this node/edge/fact."""

    RULE = "rule"  # a rule_id from a module
    HUMAN = "human"  # a user_id
    SOURCE = "source"  # a g-i-1 source_item_id (grounded extraction)


class EdgeStatus(StrEnum):
    """Per MD g-i-3 §3.2.2 — candidates exist but cannot be reasoned on."""

    ASSERTED = "asserted"
    CANDIDATE = "candidate"


# ─────────────────────────────────────────────────────────────────────────────
# Fact (subject-predicate-object)
# ─────────────────────────────────────────────────────────────────────────────


class Fact(BaseModel):
    """A single SPO assertion grounded in a source. Engine input."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    subject: str
    predicate: str
    object: str
    source_item_id: str = Field(
        ...,
        description="Pointer back to the MemoryItem this fact came from (g-i-1 stable id)",
    )
    asserted_by_type: AssertionSource
    asserted_by_id: str = Field(..., description="rule_id / user_id / source_item_id")
    confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Node (entity / event / goal / risk / dependency)
# ─────────────────────────────────────────────────────────────────────────────


class Node(BaseModel):
    """A graph node. Entities carry resolution fields (canonical_name, aliases)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    org_unit: str = Field(..., description="Per-org-unit namespacing (g-i-3 §3.2.1)")
    type: NodeType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_item_ids: list[str] = Field(
        default_factory=list,
        description="g-i-1 MemoryItem ids that grounded this node (extraction provenance)",
    )
    first_seen: datetime
    last_seen: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Edge (with Bayesian params + status)
# ─────────────────────────────────────────────────────────────────────────────


class Edge(BaseModel):
    """A graph edge. Carries provenance + weight provenance + Bayesian state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    from_node: str
    to_node: str
    type: EdgeType
    asserted_by_type: AssertionSource
    asserted_by_id: str
    asserted_at: datetime
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    weight_source: WeightSource = WeightSource.DEFAULT
    # Bayesian (g-i-3 learning) — Beta(alpha, beta)
    alpha: int = Field(default=1, ge=0)
    beta: int = Field(default=1, ge=0)
    trust: float = Field(default=0.0, ge=0.0, le=1.0)
    status: EdgeStatus = EdgeStatus.ASSERTED

    @model_validator(mode="after")
    def _influence_must_not_be_inferred_from_temporal(self) -> Edge:
        """Per MD g-i-2 HARD RULE: INFLUENCE edges cannot have asserted_by_type=SOURCE
        unless explicitly tagged. Prevents the post-hoc-fallacy failure mode at schema level.
        SOURCE-asserted INFLUENCE is rejected; INFLUENCE requires RULE or HUMAN.
        """
        if self.type == EdgeType.INFLUENCE and self.asserted_by_type == AssertionSource.SOURCE:
            raise ValueError(
                "INFLUENCE edge cannot be asserted by SOURCE (post-hoc fallacy). "
                "Use RULE or HUMAN assertion."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Decision (g-i-2 emits; g-i-3 references in corrections)
# ─────────────────────────────────────────────────────────────────────────────


class Decision(BaseModel):
    """An engine output. Full schema lives with g-i-2; type here for FK reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    conclusion: str
    derivation_chain: list[dict[str, Any]] = Field(default_factory=list)
    path: str = Field(..., description="symbolic | neural | hybrid")
    confidence: float = Field(..., ge=0.0, le=1.0)
    grounding_refs: list[str] = Field(default_factory=list)
    route: str = Field(..., description="autonomous | notify | flag")
    as_of_version: int
    triggered_by: str = Field(default="query", description="query | proactive_scan | webhook")
    module_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Correction (g-i-7 captures; g-i-3 consumes for Bayesian update)
# ─────────────────────────────────────────────────────────────────────────────


class Correction(BaseModel):
    """A structured human override. Feeds g-i-3 learning loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    decision_id: str
    input_context: dict[str, Any]
    engine_decision: dict[str, Any]
    human_decision: dict[str, Any]
    diff: dict[str, Any]
    rule_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    timestamp: datetime
    actor: str


# ─────────────────────────────────────────────────────────────────────────────
# CandidateEdge (g-i-3 §3.2.2 — propose-confirm flow)
# ─────────────────────────────────────────────────────────────────────────────


class CandidateEdge(BaseModel):
    """An association detected via lift. NEVER reasoned on as causal until confirmed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    org_id: str
    from_node: str
    to_node: str
    signal_lift: float = Field(..., gt=0.0, description="lift(X,Y) = P(X^Y)/(P(X)P(Y))")
    co_occurrence_count: int = Field(..., ge=0)
    status: str = Field(default="proposed", description="proposed | confirmed | rejected")
    proposed_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
