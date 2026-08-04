"""PAUSE notion (drop its un-processed pages from the L2 queue — done ones stay in the graph),
then finish GMAIL: fetch the full 30-day window + L2 only what's pending (gmail + any gcal).
Notion is left alone; re-sync it later to resume. Focused, minimal LLM (done events skipped)."""
from __future__ import annotations

import sys

from sqlalchemy import text

from genios_engine.api.routes import _sync_connection
from genios_engine.platform.wiring import make_connection_store, make_graph_store
from scripts.verify_ingest import report

org = sys.argv[1] if len(sys.argv) > 1 else "org_325a6e36e6bb4651a2a1e403"
eng = make_graph_store().engine

# 1. PAUSE notion — remove only its PENDING (not-yet-L2'd) events from the queue.
_PEND = ("event_id in (select event_id from source_events where org_id=:o and source='notion' "
         "and event_id not in (select event_id from l2_processing_runs where org_id=:o and status='done'))")
def _del(sql):
    try:
        with eng.begin() as c:
            return c.execute(text(sql), {"o": org}).rowcount
    except Exception as e:      # noqa: BLE001
        return f"skip ({str(e)[:40]})"
print("PAUSE notion (drop pending pages from queue; done ones kept in graph):")
print("  raw_payloads:", _del(f"delete from raw_payloads where {_PEND}"))
print("  event_trace :", _del(f"delete from event_trace where {_PEND}"))
print("  source_events:", _del("delete from source_events where org_id=:o and source='notion' "
                               "and event_id not in (select event_id from l2_processing_runs where org_id=:o and status='done')"))

with eng.connect() as c:
    print("  notion left (done, kept):",
          c.execute(text("select count(*) from source_events where org_id=:o and source='notion'"), {"o": org}).scalar())

# 2. RESUME email — fetch the full 30-day gmail + L2 the pending (gmail-focused now that notion is out).
gmail = [x for x in make_connection_store().list_active()
         if x.org_id == org and x.source_type == "gmail"]
if not gmail:
    print("no gmail connection"); sys.exit(1)
print("\nEMAIL: gmail backfill (30d) + L2 pending …")
_sync_connection(gmail[0], "backfill", 100)      # L1 fetch all + L2 (process_pending = gmail + gcal only)

report(eng, org, "piyush@3one4capital.com")
