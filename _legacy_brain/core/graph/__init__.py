"""Shared graph — built here (g-i-3 foundations), reasoned over by g-i-2, extended by g-i-3 worldmodel.

ONE graph. No forks. Per GENIOS_V2_PLAN.md architectural law.

Public API:
    from core.graph import (
        # Pydantic types (engine-facing)
        Fact, Node, Edge, Decision, Correction, CandidateEdge,
        EdgeType, NodeType, WeightSource, AssertionSource,
        # SQLAlchemy models (persistence)
        FactRow, NodeRow, EdgeRow, GraphEventRow, GraphSnapshotRow,
        # weight ops
        bayesian_update, laplace_smoothed_weight,
    )
"""

from core.graph.schema import (
    AssertionSource,
    CandidateEdge,
    Correction,
    Decision,
    Edge,
    EdgeType,
    Fact,
    Node,
    NodeType,
    WeightSource,
)
from core.graph.store import (
    EdgeRow,
    FactRow,
    GraphEventRow,
    GraphSnapshotRow,
    NodeRow,
)
from core.graph.weights import bayesian_update, laplace_smoothed_weight

__all__ = [
    "AssertionSource",
    "CandidateEdge",
    "Correction",
    "Decision",
    "Edge",
    "EdgeRow",
    "EdgeType",
    "Fact",
    "FactRow",
    "GraphEventRow",
    "GraphSnapshotRow",
    "Node",
    "NodeRow",
    "NodeType",
    "WeightSource",
    "bayesian_update",
    "laplace_smoothed_weight",
]
