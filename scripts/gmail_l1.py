"""Clear an org's gmail capture, then L1-only backfill (now 30 days) — NO LLM/L2. Reports the count
so you can see how many 1-month emails came in before deciding to run L2.

    python scripts/gmail_l1.py [org_id]

⛔ STEP-18 S18-X07 (`yc2_w27_s18` M48.C3.L-data.V1.U17). The wipe ran each statement in its own
transaction and printed `skip:` on a failure — so a fingerprint delete that failed (a lock, a
timeout, a database without 0144) still let the events go, and the re-sync then skipped every
message as `seen_on_screen`, the B20 defect by another road. Now the wipe is ONE transaction, as
the disconnect's is (`api/routes.integration_disconnect`): all of it or none of it, and a failure
stops the script before anything is re-synced.
"""
from __future__ import annotations

import sys

from sqlalchemy import text

DEFAULT_ORG = "org_325a6e36e6bb4651a2a1e403"

#: The wipe, in order, for one org's gmail capture — so the 30-day window re-fetches cleanly (dedup
#: would block it otherwise).
WIPE = (
    "delete from l2_processing_runs where org_id=:o and event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from l1_extraction_results where org_id=:o and event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from raw_payloads where event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from event_trace where event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    # ⛔ STEP-18 B20 (`yc2_w27_s18` M48.C3.L-data.V0.U11): a message's fingerprint claim names its
    # event, and a claim by an event with no row is still honoured — leaving these behind made the
    # re-fetch below skip every message as `seen_on_screen`. Selected through `source_events`, so
    # before them.
    "delete from message_fingerprints where org_id=:o and event_id in (select event_id from source_events where org_id=:o and source='gmail')",
    "delete from source_events where org_id=:o and source='gmail'",
    "delete from sync_cursors where org_id=:o and source='gmail'",
)


def clear_gmail(engine, org: str) -> None:
    """One org's gmail capture, wiped in ONE transaction — every statement of `WIPE`, or, on any
    failure, none of them: the error propagates and nothing is deleted. (Worded so: the statement
    counter reads a string that opens with a SQL verb as SQL, `03` F100.)"""
    with engine.begin() as c:
        for sql in WIPE:
            c.execute(text(sql), {"o": org})


def main(argv: list[str]) -> int:
    from genios_engine.platform.wiring import make_graph_store

    org = argv[1] if len(argv) > 1 else DEFAULT_ORG
    eng = make_graph_store().engine
    try:
        clear_gmail(eng, org)
    except Exception as e:      # noqa: BLE001 — named, and the script stops
        print(f"the wipe failed and was rolled back — nothing deleted, nothing re-synced: {e}",
              file=sys.stderr)
        return 1
    print("cleared old gmail events")
    _resync(eng, org)
    return 0


def _resync(eng, org: str) -> None:
    from genios_engine.api import routes as R
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.platform.wiring import (make_connection_store, make_connector_for,
                                               make_relevance_classifier)

    gmail = [c for c in make_connection_store().list_active()
             if c.org_id == org and c.source_type == "gmail"][0]
    summary = run_sync(
        make_connector_for(gmail), org_id=org, connection_id=gmail.connection_id,
        repo=R._repo, mode="backfill", limit=100, parked_store=R._parked,
        relevance=make_relevance_classifier(), trace_repo=R._trace_repo,
        payload_store=R._payload_store, cursor_store=R._cursors,
        document_job_store=R._documents, source="gmail", max_pages=20,
        # Every event this script lands is a real `source_events` row that L2 will read. Omitting the
        # declaration reproduced the `coverage_ready=None` population W9 exists to end — in a script
        # the AST ratchet over `genios_engine/` cannot see.
        coverage_fn=R._coverage_fn_for(org))
    print("L1 (30d) summary:", summary)
    with eng.connect() as c:
        print("gmail events now:",
              c.execute(text("select outcome,count(*) from source_events where org_id=:o and source='gmail' group by outcome"),
                        {"o": org}).fetchall())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
