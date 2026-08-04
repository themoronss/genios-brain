"""Clear an org's gmail capture, then L1-only backfill (now 30 days) — NO LLM/L2. Reports the count
so you can see how many 1-month emails came in before deciding to run L2."""
from __future__ import annotations

import sys

from sqlalchemy import text

from genios_engine.api import routes as R
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.platform.wiring import (make_connection_store, make_connector_for,
                                           make_graph_store, make_relevance_classifier)

org = sys.argv[1] if len(sys.argv) > 1 else "org_325a6e36e6bb4651a2a1e403"
eng = make_graph_store().engine

# clear existing gmail capture so the 30-day window re-fetches cleanly (dedup would block it otherwise)
for sql in [
    "delete from l2_processing_runs where org_id=:o and event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from l2_extraction_results where org_id=:o and event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from raw_payloads where event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from event_trace where event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from source_events where org_id=:o and source='gmail'",
    "delete from sync_cursors where org_id=:o and source='gmail'",
]:
    try:
        with eng.begin() as c:
            c.execute(text(sql), {"o": org})
    except Exception as e:      # noqa: BLE001
        print("skip:", str(e)[:60])
print("cleared old gmail events")

gmail = [c for c in make_connection_store().list_active()
         if c.org_id == org and c.source_type == "gmail"][0]
summary = run_sync(
    make_connector_for(gmail), org_id=org, connection_id=gmail.connection_id,
    repo=R._repo, mode="backfill", limit=100, parked_store=R._parked,
    relevance=make_relevance_classifier(), trace_repo=R._trace_repo,
    payload_store=R._payload_store, cursor_store=R._cursors,
    document_job_store=R._documents, source="gmail", max_pages=20)
print("L1 (30d) summary:", summary)
with eng.connect() as c:
    print("gmail events now:",
          c.execute(text("select outcome,count(*) from source_events where org_id=:o and source='gmail' group by outcome"),
                    {"o": org}).fetchall())
