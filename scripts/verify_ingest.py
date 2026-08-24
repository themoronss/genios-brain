"""End-to-end ingest + verification for ONE org across gmail / gcal / notion.

Runs the REAL pipeline (the same run_sync + process_pending the API uses), then prints a
per-source coverage report from the graph so you can SEE, with certainty, exactly what
relevant info landed — not a promise.

Usage (needs env: DATABASE_URL, COMPOSIO_API_KEY, CRYPTO_KEY, ANTHROPIC_API_KEY):

    python -m scripts.verify_ingest --org org_7173
    python -m scripts.verify_ingest --org org_7173 --spotlight piyush@3one4capital.com
    python -m scripts.verify_ingest --org org_7173 --fresh --yes   # clear org + re-ingest from scratch

--fresh wipes ONLY this org's captured + graph rows so the new full-body/attachment/edge code
re-ingests everything (dedup otherwise skips already-seen mail). Destructive — needs --yes.
Default (no --fresh) is a safe incremental pull of new mail only.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from genios_engine.api.routes import _sync_connection      # exact API sync+L2 path, reused
from genios_engine.platform.config import get_settings
from genios_engine.platform.wiring import make_connection_store, make_graph_store

# org_id-keyed tables cleared by --fresh (capture + graph + read models). Missing tables skipped.
_FRESH_TABLES = [
    "source_refs", "graph_facts", "graph_observations", "graph_edges", "graph_changes",
    "discrepancies", "source_identity_map", "graph_nodes", "context_read_models",
    "l2_extraction_results", "l2_processing_runs", "processing_cache",
    "parked_events", "sync_cursors", "source_events",
]
# tables with NO org_id column (keyed by event_id) — must be deleted via a source_events join,
# BEFORE source_events is cleared. (Deleting these by org_id silently no-ops → stale payloads
# survive → dedup blocks re-fetch → the "no edges / to=None" bug.)
_BY_EVENT_TABLES = ["raw_payloads", "event_trace"]


def _scalar(conn, sql, **p):
    try:
        return conn.execute(text(sql), p).scalar() or 0
    except Exception as e:      # noqa: BLE001 — a missing/renamed table shouldn't kill the report
        return f"(n/a: {str(e)[:40]})"


def _rows(conn, sql, **p):
    try:
        return conn.execute(text(sql), p).fetchall()
    except Exception as e:      # noqa: BLE001
        return [("(n/a)", str(e)[:40])]


def fresh_wipe(engine, org: str) -> None:
    """Wipe ALL of one org's captured + graph rows so a fresh re-ingest has a clean slate.
    Each delete runs in its OWN transaction — one failure (missing table) never aborts the rest.
    Connections/secrets are NOT touched (re-sync needs them)."""
    def _del(sql: str):
        try:
            with engine.begin() as conn:
                return conn.execute(text(sql), {"o": org}).rowcount
        except Exception as e:      # noqa: BLE001
            return f"skip ({str(e)[:40]})"
    # event_id-keyed tables first (before source_events is gone)
    for t in _BY_EVENT_TABLES:
        print(f"  cleared {t}:",
              _del(f"delete from {t} where event_id in (select event_id from source_events where org_id=:o)"))
    for t in _FRESH_TABLES:
        print(f"  cleared {t}:", _del(f"delete from {t} where org_id=:o"))


def report(engine, org: str, spotlight: str | None) -> None:
    with engine.connect() as conn:
        print("\n================  COVERAGE REPORT  ================")
        print("\n-- L1: source_events by source × outcome --")
        for r in _rows(conn,
                       "select source, outcome, count(*) c from source_events where org_id=:o "
                       "group by source, outcome order by source, outcome", o=org):
            print(f"   {r[0]:<18} {r[1]:<22} {r[2]}")

        print("\n-- graph_nodes by type --")
        for r in _rows(conn, "select node_type, count(*) c from graph_nodes where org_id=:o "
                             "group by node_type order by c desc", o=org):
            print(f"   {r[0]:<18} {r[1]}")

        print("\n-- graph_edges by type (the relationships) --")
        for r in _rows(conn, "select edge_type, count(*) c from graph_edges where org_id=:o "
                             "group by edge_type order by c desc", o=org):
            print(f"   {r[0]:<18} {r[1]}")

        print("\n-- content --")
        print("   facts:        ", _scalar(conn, "select count(*) from graph_facts where org_id=:o", o=org))
        print("   observations: ", _scalar(conn, "select count(*) from graph_observations where org_id=:o", o=org))
        print("   attachments:  ", _scalar(conn,
              "select count(*) from source_events where org_id=:o and object_type='email_attachment'", o=org))

        print("\n-- fact confidence (= relevance) distribution: STORE-DON'T-DELETE proof --")
        for r in _rows(conn,
                       "select width_bucket(confidence,0,1,5) b, count(*) c, round(min(confidence)::numeric,2), "
                       "round(max(confidence)::numeric,2) from graph_facts where org_id=:o group by b order by b", o=org):
            print(f"   bucket {r[0]}: {r[1]} facts  (conf {r[2]}–{r[3]})")

        if spotlight:
            print(f"\n-- SPOTLIGHT: {spotlight} --")
            nid = _scalar(conn, "select node_id from graph_nodes where org_id=:o and canonical_key=:k "
                                "and valid_to is null limit 1", o=org, k=spotlight.lower())
            if not nid or isinstance(nid, str):
                print("   node not found (not yet ingested?)")
            else:
                conns_out = _rows(conn,
                    "select e.edge_type, o.display_name from graph_edges e join graph_nodes o "
                    "on o.node_id=e.to_node_id where e.org_id=:o and e.from_node_id=:n", o=org, n=nid)
                conns_in = _rows(conn,
                    "select e.edge_type, o.display_name from graph_edges e join graph_nodes o "
                    "on o.node_id=e.from_node_id where e.org_id=:o and e.to_node_id=:n", o=org, n=nid)
                print(f"   connections ({len(conns_out)+len(conns_in)}):")
                for r in (list(conns_out) + list(conns_in)):
                    print(f"      [{r[0]}] {r[1]}")
                print("   facts:")
                for r in _rows(conn, "select field, value, round(confidence::numeric,2) from graph_facts "
                                     "where org_id=:o and subject_node_id=:n and valid_to is null limit 20", o=org, n=nid):
                    print(f"      {r[0]} = {r[1]}  (conf {r[2]})")
        print("\n==================================================\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--spotlight", default=None, help="entity email to inspect (e.g. piyush@3one4capital.com)")
    ap.add_argument("--fresh", action="store_true", help="wipe this org's rows first (destructive)")
    ap.add_argument("--yes", action="store_true", help="confirm --fresh")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    s = get_settings()
    if not (s.use_real_db and s.use_real_composio and s.use_real_llm):
        print("MISSING ENV — need DATABASE_URL, COMPOSIO_API_KEY, CRYPTO_KEY, ANTHROPIC_API_KEY.")
        print(f"   db={s.use_real_db} composio={s.use_real_composio} llm={s.use_real_llm}")
        return 2

    graph = make_graph_store()
    if args.fresh:
        if not args.yes:
            print("--fresh is destructive; pass --yes to confirm."); return 2
        print(f"Wiping org {args.org} …"); fresh_wipe(graph.engine, args.org)

    conns = [c for c in make_connection_store().list_active() if c.org_id == args.org]
    if not conns:
        print(f"No active connections for org {args.org}."); return 1
    print(f"Syncing {len(conns)} connection(s): {[c.source_type for c in conns]}")
    for c in conns:                                   # gmail / gcal / notion — each L1 + L2
        mode = "backfill" if args.fresh else "incremental"   # backfill = full pull via initial_snapshot
        print(f"  → {c.source_type} ({mode}) …")
        _sync_connection(c, mode, args.limit)

    report(graph.engine, args.org, args.spotlight)
    return 0


if __name__ == "__main__":
    sys.exit(main())
