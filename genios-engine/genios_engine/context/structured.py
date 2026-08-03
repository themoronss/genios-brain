from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.context.graph_store import GraphStore

# B1 — Structured lane. Structured events (calendar / CRM / client-DB) already carry typed
# fields (L1 mapped them via the registry). We write them straight to the graph — NO LLM,
# confidence 1.0, authority R3 (configured system-of-record). This is the cost hero.


@dataclass
class StructuredResult:
    event_id: str
    outcome: str                 # committed_structured
    node_id: str
    facts: int = 0
    edges: int = 0
    graph_version: int | None = None


def commit_structured(store: GraphStore, *, org_id: str, event_id: str, source: str,
                      source_object_id: str, structured_fields: dict, node_type: str,
                      occurred_at: datetime | None,
                      display_name: str | None = None,
                      relations: list[dict] | None = None) -> StructuredResult:
    with store.engine.begin() as conn:
        version = store.bump_version(conn, org_id)
        node = store.find_or_create_node(
            conn, org_id=org_id, node_type=node_type,
            canonical_key=f"{source}:{source_object_id}",
            display_name=display_name or source_object_id,   # readable title, not the raw id
            event_id=event_id)
        store.map_identity(conn, org_id=org_id, source=source,
                           source_object_id=source_object_id, node_id=node)
        fact_n = 0
        for field, value in (structured_fields or {}).items():
            if value in (None, ""):
                continue
            wrote = store.write_fact(
                conn, org_id=org_id, subject_node_id=node, field=field, value=value,
                value_type="string", confidence=1.0, occurred_at=occurred_at,
                event_id=event_id,
                evidence={"source_field": field, "source_object": source_object_id},
                source=source, authority_rank=3)      # R3 system-of-record
            if wrote:
                fact_n += 1
        # relationships → graph edges (person→attended→meeting, deal→about→company, …). The related
        # node is find-or-created by its own canonical_key (email for people) so it MERGES with the
        # same entity seen elsewhere, turning the graph from a scatter of nodes into a real network.
        edge_n = 0
        for rel in (relations or []):
            other = store.find_or_create_node(
                conn, org_id=org_id, node_type=rel["node_type"],
                canonical_key=rel["canonical_key"], display_name=rel.get("display_name"),
                event_id=event_id)
            frm, to = (other, node) if rel.get("direction", "in") == "in" else (node, other)
            wrote = store.write_edge(
                conn, org_id=org_id, edge_type=rel["edge_type"], from_node_id=frm, to_node_id=to,
                confidence=1.0, occurred_at=occurred_at, event_id=event_id,
                evidence={"relation": rel["edge_type"], "source_object": source_object_id},
                source=source, authority_rank=3)
            if wrote:
                edge_n += 1
        store.write_change(conn, org_id=org_id, graph_version=version, cause_event_id=event_id,
                           payload={"structured": True, "facts": fact_n, "edges": edge_n})
    return StructuredResult(event_id, "committed_structured", node, fact_n, edge_n, version)
