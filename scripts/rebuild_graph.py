"""Deterministically REBUILD one org's context graph from the L1 event ledger + L2 extraction
cache (GRAPH_QUALITY_FIX.md — apply P1/P2/P5 to the existing graph).

The graph is a pure projection of source_events + the cached L2 extractions, so we can drop it and
replay: every emitted event is re-run through the (new) L2 logic, hitting the extraction cache so a
fully-cached org rebuilds with ZERO new LLM calls.

SAFETY (built in):
  * Dry by default. Without --apply it ONLY backs up nothing and prints coverage + a BEFORE probe.
  * --apply first copies every graph_* row for the org into  <table>_bak_<ts>  (reversible), THEN
    wipes + replays. Backups are left in place; restore = insert back from the _bak_<ts> tables.
  * Refuses to wipe if uncached unstructured events would force live LLM calls, unless --allow-llm.
  * KEEPS l2_extraction_results (the cache), source_events and raw_payloads — only the projection
    tables are rebuilt.

Usage:  python -m scripts.rebuild_graph --org org_xxx [--apply] [--allow-llm]
Recommend proving on a small/test org first, then the real one, with the BEFORE/AFTER in hand.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.capture.structured.registry import get_mapping
from genios_engine.context.runner import _internal_emails, _process_one
from genios_engine.platform.config import get_settings
from genios_engine.platform.wiring import make_graph_store, make_llm_client

# Projection tables (org-scoped) rebuilt from the ledger + cache. NOT touched: l2_extraction_results
# (cache), source_events, raw_payloads, connections, signals*, cards*, llm_costs, user_tasks…
_GRAPH_TABLES = ["graph_source_refs", "graph_facts", "graph_observations", "graph_edges",
                 "discrepancies", "graph_change_outbox", "graph_nodes", "graph_versions"]


def _probe(conn, org: str) -> dict:
    total = conn.execute(text("select count(*) from graph_nodes where org_id=:o and valid_to is null"),
                         {"o": org}).scalar() or 0
    edges = conn.execute(text("select count(*) from graph_edges where org_id=:o and valid_to is null"),
                         {"o": org}).scalar() or 0
    iso = conn.execute(text(
        "select count(*) from graph_nodes n where n.org_id=:o and n.valid_to is null "
        "and not exists (select 1 from graph_edges e where e.org_id=:o and e.valid_to is null "
        "               and (e.from_node_id=n.node_id or e.to_node_id=n.node_id)) "
        "and not exists (select 1 from graph_facts f where f.org_id=:o and f.subject_node_id=n.node_id "
        "               and f.valid_to is null and f.status='active')"), {"o": org}).scalar() or 0
    types = {r.node_type: r.c for r in conn.execute(text(
        "select node_type, count(*) c from graph_nodes where org_id=:o and valid_to is null "
        "group by node_type order by c desc"), {"o": org})}
    return {"nodes": total, "edges": edges, "orphans": iso,
            "orphan_pct": round(100.0 * iso / total, 1) if total else 0.0, "types": types}


def _print_probe(tag: str, p: dict) -> None:
    print(f"  [{tag}] nodes={p['nodes']} edges={p['edges']} orphans={p['orphans']} "
          f"({p['orphan_pct']}%)  types={p['types']}")


def _pull_all(conn, org: str):
    """EVERY emitted event for the org (no dedup/exclusion filters — the rebuild replays all)."""
    return conn.execute(text(
        "select se.event_id, se.source, se.object_type, se.actor->>'email' as sender, "
        "se.occurred_at, se.source_object_id, rp.enc_content "
        "from source_events se join raw_payloads rp on rp.event_id = se.event_id "
        "where se.org_id=:o and se.outcome='emitted' order by se.occurred_at asc"), {"o": org}).fetchall()


def _coverage(rows) -> tuple[int, int, int]:
    """(structured, unstructured, unstructured_uncached-upper-bound) — the third would need LLM."""
    structured = sum(1 for r in rows if get_mapping(r.source, r.object_type) is not None)
    return structured, len(rows) - structured, 0  # cache coverage checked live via cache hit at replay


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--apply", action="store_true", help="actually back up + wipe + rebuild")
    ap.add_argument("--allow-llm", action="store_true", help="permit live LLM calls on cache misses")
    args = ap.parse_args()
    org = args.org

    store = make_graph_store()
    eng = store.engine
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    with eng.connect() as c:
        before = _probe(c, org)
        rows = _pull_all(c, org)
        structured, unstructured, _ = _coverage(rows)
        cached_ev = c.execute(text("select count(distinct event_id) from l2_extraction_results "
                                   "where org_id=:o"), {"o": org}).scalar() or 0
    print(f"== ORG {org} ==")
    _print_probe("BEFORE", before)
    print(f"  emitted events: {len(rows)} (structured={structured}, unstructured={unstructured}) · "
          f"cache rows(event-linked)={cached_ev}")
    uncached_est = max(0, unstructured - cached_ev)
    print(f"  est. unstructured events NOT cache-linked (may cost LLM): ~{uncached_est}")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to backup+wipe+rebuild.")
        return
    if uncached_est > 0 and not args.allow_llm:
        print(f"\nREFUSING: ~{uncached_est} events may force live LLM calls. "
              f"Re-run with --allow-llm to proceed (spends tokens), or ensure the org is fully cached.")
        return

    # LLM client: needed only on a genuine cache miss; a fully-cached org never calls it.
    s = get_settings()
    llm = make_llm_client()

    with eng.begin() as c:
        internal = _internal_emails(store, org)
        print(f"\n1) BACKUP → *_bak_{ts} (org rows only)")
        for tbl in _GRAPH_TABLES:
            c.execute(text(f"create table if not exists {tbl}_bak_{ts} as "
                           f"select * from {tbl} where org_id=:o"), {"o": org})
        print("2) WIPE projection tables + l2_processing_runs (cache kept)")
        for tbl in _GRAPH_TABLES:
            c.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})
        c.execute(text("delete from l2_processing_runs where org_id=:o"), {"o": org})

    print(f"3) REPLAY {len(rows)} events (cache hits → zero LLM)…")
    out: dict[str, int] = {}
    for r in rows:
        try:
            outcome, _ = _process_one(r, org_id=org, store=store, llm=llm,
                                      crypto_key=s.crypto_key, internal_emails=internal)
        except Exception as e:      # noqa: BLE001
            outcome = "error:" + str(e)[:40]
        out[outcome] = out.get(outcome, 0) + 1
    print("   outcomes:", out)

    with eng.connect() as c:
        after = _probe(c, org)
    print("\n== RESULT ==")
    _print_probe("BEFORE", before)
    _print_probe("AFTER ", after)
    d_nodes = after["nodes"] - before["nodes"]
    print(f"  Δ nodes={d_nodes:+d} · orphans {before['orphans']}→{after['orphans']} · "
          f"isolation {before['orphan_pct']}%→{after['orphan_pct']}%")
    print(f"  Restore if wrong:  for t in {_GRAPH_TABLES}: insert into t select * from t_bak_{ts}")


if __name__ == "__main__":
    main()
