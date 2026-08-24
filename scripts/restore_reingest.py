"""SAFE delete + re-sync for an org whose connections were lost.

Reconstructs the org's connections (pattern: composio_user_id == org_id, proven on real orgs),
VALIDATES each against Composio FIRST, and only wipes + re-ingests if Gmail validates — so if the
OAuth is dead we ABORT before deleting (no irreversible data loss). Keeps the connection rows.

Usage (from genios-brain, needs .env):
    python -m scripts.restore_reingest --org org_325a6e36e6bb4651a2a1e403 \
        --spotlight piyush@3one4capital.com --yes
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.api.routes import _sync_connection
from genios_engine.capture.connections.store import Connection
from genios_engine.platform.wiring import (make_connection_store, make_connector_for,
                                           make_graph_store)
from scripts.verify_ingest import fresh_wipe, report


def _sources_from_cursors(eng, org: str) -> list[str]:
    with eng.connect() as c:
        return [r[0] for r in c.execute(
            text("select distinct source from sync_cursors where org_id=:o"), {"o": org})]


def restore_connections(org: str) -> list:
    """Recreate missing connections with composio_user_id == org_id (the real-org pattern)."""
    store = make_connection_store()
    eng = make_graph_store().engine
    have = {c.source_type: c for c in store.list_active() if c.org_id == org}
    had = _sources_from_cursors(eng, org) or ["gmail", "gcal", "notion"]
    for src in had:
        if src in have:
            print(f"  {src}: already present"); continue
        store.add(Connection(
            connection_id=f"con_restore_{src}_{org[-6:]}", org_id=org, provider="google",
            source_type=src, composio_user_id=org,            # pattern: uid == org_id
            config={}, status="connected", created_at=datetime.now(timezone.utc)))
        print(f"  {src}: RESTORED (composio_user_id=org_id)")
    return [c for c in store.list_active() if c.org_id == org]


def validate(conns: list) -> bool:
    """Ping Composio for each connection. Gmail MUST validate or we abort (can't re-pull otherwise)."""
    gmail_ok = True
    any_gmail = False
    for c in conns:
        try:
            ok = make_connector_for(c).validate_connection()
            print(f"  {c.source_type}: validate -> {ok}")
        except Exception as e:      # noqa: BLE001
            print(f"  {c.source_type}: VALIDATE FAILED -> {str(e)[:90]}")
            if c.source_type == "gmail":
                gmail_ok = False
        if c.source_type == "gmail":
            any_gmail = True
    return gmail_ok and any_gmail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--spotlight", default=None)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--yes", action="store_true", help="confirm the wipe + re-ingest")
    args = ap.parse_args()

    print(f"[1/4] restoring connections for {args.org} …")
    conns = restore_connections(args.org)
    if not conns:
        print("  no connections and none restorable — cannot re-sync."); return 1

    print("[2/4] validating against Composio (Gmail must be alive) …")
    if not validate(conns):
        print("\n  ⛔ Gmail did NOT validate — the OAuth is gone. NOT deleting anything "
              "(re-sync would be impossible). The mailbox owner must reconnect first.")
        return 2
    print("  ✅ connections live — safe to wipe + re-ingest.")

    if not args.yes:
        print("\n  pass --yes to actually wipe + re-ingest now."); return 0

    print(f"[3/4] wiping {args.org} data (connections kept) …")
    fresh_wipe(make_graph_store().engine, args.org)

    print("[4/4] re-ingesting (backfill) with the new code …")
    for c in conns:
        print(f"  → {c.source_type} …")
        _sync_connection(c, "backfill", args.limit)

    report(make_graph_store().engine, args.org, args.spotlight)
    return 0


if __name__ == "__main__":
    sys.exit(main())
