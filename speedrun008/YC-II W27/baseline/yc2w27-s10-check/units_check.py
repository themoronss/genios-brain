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
        run_case(cases[cid], RecordedLLM(cassettes.load(cases[cid])), keep=True)
        with engine.connect() as c:
            runs = c.execute(text("select run_id, capability_id, mode, status, evaluation_time from reasoning_runs where org_id=:o order by evaluation_time"), {"o": org}).fetchall()
            print(cid, "runs:", len(runs), sorted({(r.capability_id or '')[:60] for r in runs}))
            res = c.execute(text("select reasoner_id, status, skip_reason_code, output from reasoning_reasoner_results where org_id=:o and reasoner_id in ('core.timeline','core.cost','core.alternative','core.temporal') order by created_at"), {"o": org}).fetchall()
            from collections import Counter
            print(cid, "unit statuses:", Counter((r.reasoner_id, r.status, r.skip_reason_code) for r in res))
            for r in res:
                if r.reasoner_id == 'core.timeline' and r.output:
                    o = r.output if isinstance(r.output, dict) else json.loads(r.output)
                    print(cid, "timeline output:", json.dumps(o, default=str)[:700]); break
            for r in res:
                if r.reasoner_id == 'core.cost' and r.output:
                    o = r.output if isinstance(r.output, dict) else json.loads(r.output)
                    print(cid, "cost output:", json.dumps(o, default=str)[:500]); break
    finally:
        remove_tenant(engine, org)
with engine.connect() as c:
    print("GOLDEN_ORGS_LEFT", c.execute(text("select count(*) from orgs where id like :p"), {"p": ORG_PREFIX + "%"}).scalar())
