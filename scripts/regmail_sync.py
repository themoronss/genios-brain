"""Re-sync ONLY gmail for an org (after its stale gmail rows were cleared) with the current
connector, run L2, and report. Gcal/notion data is left untouched."""
from __future__ import annotations

import sys

from genios_engine.api.routes import _sync_connection
from genios_engine.platform.wiring import make_connection_store, make_graph_store
from scripts.verify_ingest import report

org = sys.argv[1] if len(sys.argv) > 1 else "org_325a6e36e6bb4651a2a1e403"
spot = sys.argv[2] if len(sys.argv) > 2 else "piyush@3one4capital.com"

gmail = [c for c in make_connection_store().list_active()
         if c.org_id == org and c.source_type == "gmail"]
if not gmail:
    print("no gmail connection"); sys.exit(1)
print(f"re-syncing gmail (backfill) for {org} …")
_sync_connection(gmail[0], "backfill", 100)      # L1 fresh fetch (to/cc) + L2 (edges)
report(make_graph_store().engine, org, spot)
