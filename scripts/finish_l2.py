"""Finish L2 (process_pending) for an org whose L1 re-sync completed but L2 got cut off, then
print the coverage report. No wipe, no re-fetch — just turns pending events into graph."""
from __future__ import annotations

import sys

from genios_engine.context.runner import process_pending
from genios_engine.platform.config import get_settings
from genios_engine.platform.wiring import make_graph_store, make_llm_client
from scripts.verify_ingest import report

org = sys.argv[1] if len(sys.argv) > 1 else "org_325a6e36e6bb4651a2a1e403"
spot = sys.argv[2] if len(sys.argv) > 2 else "piyush@3one4capital.com"

g = make_graph_store()
llm = make_llm_client()
print(f"running L2 for {org} …")
res = process_pending(org_id=org, store=g, llm=llm, crypto_key=get_settings().crypto_key)
print("L2 result:", res)
report(g.engine, org, spot)
