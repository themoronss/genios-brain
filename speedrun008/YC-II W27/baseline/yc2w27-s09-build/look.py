"""Replay a case from its cassette, keep the tenant, print its files and situations, then remove it."""
import os, sys, json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.getcwd())               # run from the repository root
from sqlalchemy import text
from tests.replays import cassettes
from tests.replays.engine_runner import pin_scratch_database, run_case, remove_tenant, ORG_PREFIX
from tests.replays.founder_case import load_cases
from tests.replays.harness import RecordedLLM
from genios_engine.context.workstreams import files_for
pin_scratch_database()
from genios_engine.api import routes
for case in load_cases():
    if case.case_id not in sys.argv[1:]:
        continue
    org = f"{ORG_PREFIX}{case.case_id.lower()}"
    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    eng = routes._graph.engine
    try:
        with eng.connect() as c:
            ws = files_for(c, org, now=datetime(2026, 10, 1, tzinfo=timezone.utc))
            print(f"===== {case.case_id}: {len(ws.files)} files, unfiled {[n.named for n in ws.unfiled]}")
            by_event = {l.event_id: l.object_id for l in run.landed if l.event_id}
            for f in ws.files:
                print(f"  file {f.counterparty_key:<28} kind={f.kind} domains={list(f.domains)} events={[by_event.get(e, e) for e in f.events]} move={f.whose_move} asks={len(f.open_asks)}")
            for r in c.execute(text("select s.situation_type, s.domain, s.status, n.canonical_key from context_situations s join graph_nodes n on n.org_id=s.org_id and n.node_id=s.anchor_node_id and n.valid_to is null where s.org_id=:o order by 4,1"), {"o": org}):
                print(f"  situation {r.situation_type:<26} {r.domain:<12} {r.status:<10} {r.canonical_key}")
            for r in c.execute(text("select headline, state from cards where org_id=:o"), {"o": org}):
                print(f"  card [{r.state}] {r.headline}")
    finally:
        remove_tenant(eng, org)
