"""READ-ONLY graph-quality probe (GRAPH_QUALITY_FIX.md baseline). ONLY SELECTs — writes nothing.

Quantifies the P1/P2/P5 problem per org: total nodes, node-type breakdown, isolation rate
(nodes with 0 edges AND 0 facts = orphans), orphan mention-type nodes (the SAP/OpenClaw dead-dots),
and +tag duplicate candidates (P5). Use to capture the BEFORE baseline before any rebuild.

Usage (from genios-brain, needs .env):  python -m scripts.graph_quality_probe [org_id]
No org → lists top orgs by node count, then probes the biggest.
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from genios_engine.platform.wiring import make_graph_store

_WHITELIST = ("person", "company", "deal", "meeting", "commitment", "thread", "document", "agent")


def _rows(conn, sql, **p):
    return conn.execute(text(sql), p).fetchall()


def probe(conn, org: str) -> None:
    print(f"\n================  ORG {org}  ================")
    total = conn.execute(text("select count(*) from graph_nodes where org_id=:o and valid_to is null"),
                         {"o": org}).scalar() or 0
    edges = conn.execute(text("select count(*) from graph_edges where org_id=:o and valid_to is null"),
                         {"o": org}).scalar() or 0
    print(f"total live nodes: {total} · total live edges: {edges}")

    print("\n-- nodes by type --")
    for r in _rows(conn, "select node_type, count(*) c from graph_nodes where org_id=:o "
                         "and valid_to is null group by node_type order by c desc", o=org):
        flag = "" if r.node_type in _WHITELIST else "   <-- NOT in whitelist (P1: should be fact/observation, not a node)"
        print(f"   {r.node_type:<16} {r.c}{flag}")

    # isolation: nodes with 0 live edges (either direction) AND 0 active facts = orphans
    iso = conn.execute(text(
        "select count(*) from graph_nodes n where n.org_id=:o and n.valid_to is null "
        "and not exists (select 1 from graph_edges e where e.org_id=:o and e.valid_to is null "
        "               and (e.from_node_id=n.node_id or e.to_node_id=n.node_id)) "
        "and not exists (select 1 from graph_facts f where f.org_id=:o and f.subject_node_id=n.node_id "
        "               and f.valid_to is null and f.status='active')"), {"o": org}).scalar() or 0
    pct = (100.0 * iso / total) if total else 0.0
    print(f"\n-- ISOLATION -- orphan nodes (0 edges AND 0 facts): {iso}  ({pct:.1f}% of all nodes)")

    print("\n-- orphans by type (the dead-dots P1 removes) --")
    for r in _rows(conn,
        "select n.node_type, count(*) c from graph_nodes n where n.org_id=:o and n.valid_to is null "
        "and not exists (select 1 from graph_edges e where e.org_id=:o and e.valid_to is null "
        "               and (e.from_node_id=n.node_id or e.to_node_id=n.node_id)) "
        "and not exists (select 1 from graph_facts f where f.org_id=:o and f.subject_node_id=n.node_id "
        "               and f.valid_to is null and f.status='active') "
        "group by n.node_type order by c desc limit 20", o=org):
        print(f"   {r.node_type:<16} {r.c}")

    # P5 — +tag duplicate candidates on person canonical_keys
    plus = conn.execute(text("select count(*) from graph_nodes where org_id=:o and valid_to is null "
                             "and node_type='person' and canonical_key like '%+%'"), {"o": org}).scalar() or 0
    print(f"\n-- P5 -- person nodes with a +tag in canonical_key (merge candidates): {plus}")

    # sample orphan display names so we can eyeball they are junk mentions
    print("\n-- sample orphans (first 15) --")
    for r in _rows(conn,
        "select n.node_type, n.display_name from graph_nodes n where n.org_id=:o and n.valid_to is null "
        "and not exists (select 1 from graph_edges e where e.org_id=:o and e.valid_to is null "
        "               and (e.from_node_id=n.node_id or e.to_node_id=n.node_id)) "
        "and not exists (select 1 from graph_facts f where f.org_id=:o and f.subject_node_id=n.node_id "
        "               and f.valid_to is null and f.status='active') limit 15", o=org):
        print(f"   [{r.node_type}] {r.display_name}")


def main() -> None:
    eng = make_graph_store().engine
    with eng.connect() as c:
        if len(sys.argv) > 1:
            probe(c, sys.argv[1])
            return
        print("== top orgs by live node count ==")
        top = _rows(c, "select org_id, count(*) n from graph_nodes where valid_to is null "
                       "group by org_id order by n desc limit 10")
        for r in top:
            print(f"   {r.org_id:<32} {r.n}")
        if top:
            probe(c, top[0].org_id)


if __name__ == "__main__":
    main()
