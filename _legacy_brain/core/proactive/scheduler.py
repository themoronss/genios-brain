"""Cron + memory-trigger scheduler with incremental scoping (g-i-3.diff).

Per MD g-i-4 §1.1.1:
    on trigger:
        changed = g-i-3.diff(last_run_time, now)
        affected = changed.nodes + 1-hop neighbors + active goals touching them
        run g-i-2 (rules + what-if) over `affected` ONLY  -> candidate insights

Full-graph re-scans are FORBIDDEN — they waste compute + regenerate stale repeats.
Always scope to the delta.

This module exposes:
- compute_affected_subgraph()  — given a diff, expand to affected nodes/edges
- on_memory_event()            — called by g-i-1 emit subscriber on every MemoryItem
- run_cron_tick()              — periodic fallback (Celery beat)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from core.foundations.config import CRON_INTERVAL_HOURS
from core.foundations.telemetry import get_logger
from core.worldmodel.temporal import diff

log = get_logger(__name__)


@dataclass(frozen=True)
class AffectedSubgraph:
    """Scope-restricted subgraph for the proactive engine to reason over."""

    org_id: str
    changed_node_ids: set[str]
    changed_edge_ids: set[str]
    one_hop_node_ids: set[str]
    window_start: datetime
    window_end: datetime

    @property
    def total_nodes(self) -> int:
        return len(self.changed_node_ids | self.one_hop_node_ids)

    @property
    def is_empty(self) -> bool:
        return not self.changed_node_ids and not self.changed_edge_ids


def compute_affected_subgraph(
    session: Session,
    *,
    org_id: str,
    since: datetime,
    until: datetime | None = None,
) -> AffectedSubgraph:
    """Get the changed nodes/edges + 1-hop neighbors from g-i-3 events.

    1-hop expansion is intentionally cheap (read graph_edges only). For deeper
    scoping (active goals touching changed nodes) the caller layers on top.
    """
    now = until or datetime.now(UTC)
    d = diff(session, org_id=org_id, from_time=since, to_time=now)

    changed_nodes: set[str] = set()
    changed_edges: set[str] = set()
    for ev in d.events:
        if ev["target_type"] == "node":
            changed_nodes.add(ev["target_id"])
        elif ev["target_type"] == "edge":
            changed_edges.add(ev["target_id"])

    # 1-hop neighbors via graph_edges lookup
    one_hop: set[str] = set()
    if changed_nodes:
        from sqlalchemy import or_, select

        from core.graph.store import EdgeRow

        rows = (
            session.execute(
                select(EdgeRow)
                .where(EdgeRow.org_id == org_id)
                .where(
                    or_(EdgeRow.from_node.in_(changed_nodes), EdgeRow.to_node.in_(changed_nodes))
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            one_hop.add(r.from_node)
            one_hop.add(r.to_node)
        one_hop -= changed_nodes  # don't double-count

    log.info(
        "proactive_subgraph_scoped",
        org_id=org_id,
        changed_nodes=len(changed_nodes),
        changed_edges=len(changed_edges),
        one_hop=len(one_hop),
    )

    return AffectedSubgraph(
        org_id=org_id,
        changed_node_ids=changed_nodes,
        changed_edge_ids=changed_edges,
        one_hop_node_ids=one_hop,
        window_start=since,
        window_end=now,
    )


def cron_interval_for(module_id: str) -> timedelta:
    """Look up the configured cron cadence for a module (default applies if unknown)."""
    hours = CRON_INTERVAL_HOURS.get(module_id, CRON_INTERVAL_HOURS["default"])
    return timedelta(hours=hours)


def run_cron_tick(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    last_run_at: datetime,
) -> AffectedSubgraph:
    """Periodic fallback: catches webhook drops + reconciles.

    Returns the AffectedSubgraph the caller then feeds to generate.py.
    Empty subgraph -> caller should no-op (nothing to reason about).
    """
    subgraph = compute_affected_subgraph(session, org_id=org_id, since=last_run_at)
    if subgraph.is_empty:
        log.debug("proactive_cron_no_changes", org_id=org_id, module_id=module_id)
    return subgraph


def on_memory_event(
    session: Session,
    *,
    org_id: str,
    item_id: str,
    last_run_at: datetime,
) -> AffectedSubgraph:
    """Called from g-i-1 emit when a MemoryItem arrives.

    Real-time path. Pulls the same diff machinery — only difference is timing
    (called immediately vs at cron tick).
    """
    log.info("proactive_memory_event", org_id=org_id, item_id=item_id)
    return compute_affected_subgraph(session, org_id=org_id, since=last_run_at)
