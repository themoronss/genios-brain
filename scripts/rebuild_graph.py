"""Deterministically REBUILD one org's context graph from the L1 event ledger + L2 extraction
cache (GRAPH_QUALITY_FIX.md — apply P1/P2/P5 to the existing graph).

The graph is a pure projection of source_events + the cached L2 extractions, so we can drop it and
replay: every kept event with a road into memory is re-run through the drain's own L2 logic, with
the drain's own columns (`context/runner._rows_for_rebuild`, STEP-18 B12) — no road calls a model.

SAFETY (built in):
  * Dry by default. Without --apply it ONLY backs up nothing and prints coverage + a BEFORE probe.
  * --apply first copies every graph_* row for the org into  <table>_bak_<ts>  (reversible), THEN
    wipes + replays. Backups are left in place; restore = insert back from the _bak_<ts> tables.
  * Refuses to wipe if uncached unstructured events would force live LLM calls, unless --allow-llm.
  * KEEPS l1_extraction_results (the cache), source_events and raw_payloads — only the projection
    tables are rebuilt.

Usage:  python -m scripts.rebuild_graph --org org_xxx [--apply] [--allow-llm]
Recommend proving on a small/test org first, then the real one, with the BEFORE/AFTER in hand.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from genios_engine.capture.structured.registry import get_mapping
from genios_engine.context.runner import _rows_for_rebuild
from genios_engine.context.runner import _safe_process_one
from genios_engine.platform.company_brief import current as company_brief_now
from genios_engine.platform.self_identity import identity_for
from genios_engine.platform.config import get_settings
from genios_engine.platform.wiring import make_graph_store, make_llm_client


def _bounded_engine(database_url: str, pool: int):
    """A dedicated SMALL-pool engine for this OUT-OF-PROCESS rebuild. get_engine's 8+4=12 pool, run
    at 5 workers, exhausted Supabase's 15-session pooler cap and starved the LIVE app (EMAXCONNSESSION
    → stall). This hard-caps the rebuild at `pool` connections (no overflow) so the running app keeps
    its headroom. Mirrors platform/db.py's psycopg normalization + pre-ping."""
    url = database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, pool_size=pool, max_overflow=0,
                         pool_recycle=1800, pool_timeout=30)

# Projection tables (org-scoped) rebuilt from the ledger + cache. NOT touched: l1_extraction_results
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


def _rows(store, org: str):
    """EVERY kept event of the org that has a road into memory, with the drain's own columns — what
    memory already holds included, because a rebuild replays the whole ledger.

    ⛔ STEP-18 B12 (`yc2_w27_s18` M48.C2.L-integration.V1.U05). This used to be a query of its own:
    `outcome = 'emitted'` only, and only `event_id, source, object_type, sender, occurred_at,
    source_object_id, enc_content`. `_process_one` reads a mail's cached extraction off its row, so
    every mail that had reached memory through a signal was held `held_missing_qes_extraction` —
    a rebuild restored the calendar and none of the mail — and the archived and below-floor roads
    STEP-05 opened were never replayed. The drain's own read (`context/runner._rows_for_rebuild`)
    is the one spelling of what a replayed row carries.
    """
    return _rows_for_rebuild(store, org)


def _replay(rows, *, org: str, store, llm, crypto_key: str, workers: int,
            internal=frozenset(), us=None, brief=None) -> dict[str, int]:
    """Replay `rows` through the drain's own `_safe_process_one`; the count of each outcome.

    Parallel, mirroring the L2 drain (ThreadPoolExecutor + `_safe_process_one`): store and llm are
    thread-safe (SQLAlchemy pool + Anthropic client), workers kept under Supabase's 15-client cap,
    and `_safe_process_one` quarantines a single event's failure."""
    out: dict[str, int] = {}
    done = 0

    def _one(r):
        outcome, _node, _err = _safe_process_one(
            r, org_id=org, store=store, llm=llm, crypto_key=crypto_key, internal_emails=internal,
            self_identity=us, company_brief=brief)
        return outcome

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for outcome in ex.map(_one, rows):
            out[outcome] = out.get(outcome, 0) + 1
            done += 1
            if done % 50 == 0:
                print(f"   … {done}/{len(rows)}  {dict(out)}", flush=True)
    return out


def _coverage(rows) -> tuple[int, int, int]:
    """(structured, unstructured, unstructured_uncached-upper-bound) — the third would need LLM."""
    structured = sum(1 for r in rows if get_mapping(r.source, r.object_type) is not None)
    return structured, len(rows) - structured, 0  # cache coverage checked live via cache hit at replay


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--apply", action="store_true", help="actually back up + wipe + rebuild")
    ap.add_argument("--allow-llm", action="store_true", help="permit live LLM calls on cache misses")
    ap.add_argument("--workers", type=int,
                    default=int(os.environ.get("GENIOS_REBUILD_WORKERS", "3")),
                    help="parallel replay workers (keep low — shares the live app's 15-session cap)")
    ap.add_argument("--pool", type=int, default=4,
                    help="hard cap on this job's DB connections (leaves headroom for the live app)")
    args = ap.parse_args()
    org = args.org

    store = make_graph_store()
    # Swap in a bounded pool so the rebuild can't starve the live app of Supabase connections.
    store._engine = _bounded_engine(get_settings().database_url, args.pool)
    eng = store.engine
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    rows = _rows(store, org)
    with eng.connect() as c:
        before = _probe(c, org)
        structured, unstructured, _ = _coverage(rows)
        cached_ev = c.execute(text("select count(distinct event_id) from l1_extraction_results "
                                   "where org_id=:o"), {"o": org}).scalar() or 0
    print(f"== ORG {org} ==")
    _print_probe("BEFORE", before)
    print(f"  kept events with a road: {len(rows)} (structured={structured}, "
          f"unstructured={unstructured}) · "
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
        # WHO IS US, as the drain reads it (STEP-04): the addresses AND the declared domains. With
        # the addresses alone a replay never knew our company's domain, so a rebuilt graph anchored
        # the situations the live drain keeps out.
        us = identity_for(store, org)
        internal = us.addresses
        # Who the founder named — connectors, a watchlist — read once, as the drain does (STEP-09).
        brief = company_brief_now(store, org)
        print(f"\n1) BACKUP → *_bak_{ts} (org rows only)")
        for tbl in _GRAPH_TABLES:
            c.execute(text(f"create table if not exists {tbl}_bak_{ts} as "
                           f"select * from {tbl} where org_id=:o"), {"o": org})
        print("2) WIPE projection tables + l2_processing_runs (cache kept)")
        for tbl in _GRAPH_TABLES:
            c.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})
        c.execute(text("delete from l2_processing_runs where org_id=:o"), {"o": org})

    # Parallel replay: mirrors the L2 drain (ThreadPoolExecutor + _safe_process_one). store/llm are
    # thread-safe (SQLAlchemy pool + Anthropic client). On a b3-2 cache MISS each unstructured event
    # makes ONE real Haiku call, so parallelism turns a ~6h single-threaded run into ~1.5h. Workers
    # kept ≤ Supabase's 15-client cap. _safe_process_one quarantines a single event's failure.
    workers = args.workers
    print(f"3) REPLAY {len(rows)} events across {workers} workers (pool cap {args.pool})…", flush=True)
    out = _replay(rows, org=org, store=store, llm=llm, crypto_key=s.crypto_key, workers=workers,
                  internal=internal, us=us, brief=brief)
    print("   outcomes:", out, flush=True)

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
