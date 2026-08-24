"""Read-only graph subgraph extraction for dashboard rendering.

Per MD g-i-6 §6.1.1:
- Visualization is a READ-ONLY view of the single g-i-3 graph (no new store)
- Interactive: expand nodes, show edge provenance + weight + trust, drill into source facts

This module returns a JSON-shippable subgraph the dashboard can render with
React Flow / D3 (per g-i-6 blocker pick). Pure data; no UI here.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core.graph.store import EdgeRow, NodeRow


@dataclass(frozen=True)
class GraphViewNode:
    """One node in the view payload (everything the UI needs to render + tooltip)."""

    id: str
    type: str
    canonical_name: str
    aliases: list[str]
    org_unit: str


@dataclass(frozen=True)
class GraphViewEdge:
    """One edge in the view payload. Provenance + weight + trust ALL visible (per MD)."""

    id: str
    from_node: str
    to_node: str
    edge_type: str
    weight: float
    weight_source: str
    trust: float
    status: str
    asserted_by_type: str
    asserted_by_id: str


@dataclass(frozen=True)
class GraphView:
    """JSON-shippable read-only subgraph for the dashboard."""

    nodes: list[GraphViewNode]
    edges: list[GraphViewEdge]


def render_graph_view(
    session: Session,
    *,
    org_id: str,
    center_node_ids: list[str],
    hops: int = 1,
) -> GraphView:
    """Extract a subgraph centered on `center_node_ids`, expanded `hops` hops.

    Read-only: NEVER mutates the graph. Returns nodes + edges with full provenance.
    """
    if hops < 0:
        raise ValueError("hops must be >= 0")

    visible_nodes: set[str] = set(center_node_ids)
    visible_edges: set[str] = set()

    frontier = set(center_node_ids)
    for _ in range(hops):
        if not frontier:
            break
        edges = (
            session.execute(
                select(EdgeRow)
                .where(EdgeRow.org_id == org_id)
                .where(or_(EdgeRow.from_node.in_(frontier), EdgeRow.to_node.in_(frontier)))
            )
            .scalars()
            .all()
        )

        next_frontier: set[str] = set()
        for e in edges:
            visible_edges.add(e.id)
            if e.from_node not in visible_nodes:
                next_frontier.add(e.from_node)
                visible_nodes.add(e.from_node)
            if e.to_node not in visible_nodes:
                next_frontier.add(e.to_node)
                visible_nodes.add(e.to_node)

        frontier = next_frontier

    # Load full node + edge rows for the visible set
    node_rows = (
        session.execute(
            select(NodeRow).where(NodeRow.org_id == org_id).where(NodeRow.id.in_(visible_nodes))
        )
        .scalars()
        .all()
    )
    edge_rows = (
        session.execute(
            select(EdgeRow).where(EdgeRow.org_id == org_id).where(EdgeRow.id.in_(visible_edges))
        )
        .scalars()
        .all()
    )

    return GraphView(
        nodes=[
            GraphViewNode(
                id=n.id,
                type=n.type,
                canonical_name=n.canonical_name,
                aliases=list(n.aliases),
                org_unit=n.org_unit,
            )
            for n in node_rows
        ],
        edges=[
            GraphViewEdge(
                id=e.id,
                from_node=e.from_node,
                to_node=e.to_node,
                edge_type=e.type,
                weight=e.weight,
                weight_source=e.weight_source,
                trust=e.trust,
                status=e.status,
                asserted_by_type=e.asserted_by_type,
                asserted_by_id=e.asserted_by_id,
            )
            for e in edge_rows
        ],
    )
