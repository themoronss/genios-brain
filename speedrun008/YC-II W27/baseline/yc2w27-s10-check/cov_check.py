import os, sys, json
sys.path.insert(0, os.getcwd())
from tests.replays.engine_runner import ORG_PREFIX, pin_scratch_database
pin_scratch_database()
from sqlalchemy import text
from tests.replays import cassettes
from tests.replays.engine_runner import remove_tenant, run_case
from tests.replays.founder_case import load_cases
from tests.replays.harness import RecordedLLM
from genios_engine.api import routes
engine = routes._graph.engine
cases = {c.case_id: c for c in load_cases()}
for cid in sys.argv[1:]:
    org = f"{ORG_PREFIX}{cid.lower()}"
    try:
        run = run_case(cases[cid], RecordedLLM(cassettes.load(cases[cid])), keep=True)
        with engine.connect() as c:
            runs = [dict(r._mapping) for r in c.execute(text("select connection_id, source, mode, scanned, emitted, archived, claimed_total, claimed_is_estimate, cursor_exhausted, page_budget_spent, error, started_at, finished_at from l1_sync_runs where org_id=:o order by started_at"), {"o": org})]
            conns = [dict(r._mapping) for r in c.execute(text("select connection_id, provider, source_type, status, capture_scope, external_account_id from connections where org_id=:o"), {"o": org})]
            from genios_engine.capture.coverage.window import coverage_for_window
            from datetime import timedelta
            now = max(cases[cid].sweeps)
            wc = coverage_for_window(c, org_id=org, source="gmail", since=now - timedelta(days=400), until=now + timedelta(days=400))
            from genios_engine.context.situations import window_coverage_gaps
            gaps = window_coverage_gaps(c, org, since=now - timedelta(days=400), until=now + timedelta(days=400))
            sits = [dict(r._mapping) for r in c.execute(text("select situation_type, missing from context_situations where org_id=:o and situation_type in ('awaiting_response','reply_owed','campaign_awaiting_reply')"), {"o": org})]
        print(cid, json.dumps({"l1_sync_runs": runs, "connections": conns, "window": {"describe": wc.describe(), "health": str(wc.health), "can_support_absence": wc.can_support_absence, "runs": wc.runs, "indexed": wc.indexed, "claimed_total": wc.claimed_total}, "window_gaps": gaps, "state_situations_missing": sits}, default=str))
    finally:
        remove_tenant(engine, org)
with engine.connect() as c:
    print("GOLDEN_ORGS_LEFT", c.execute(text("select count(*) from orgs where id like :p"), {"p": ORG_PREFIX + "%"}).scalar())
