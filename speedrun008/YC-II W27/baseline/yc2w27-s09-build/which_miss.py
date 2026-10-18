"""Replay every founder case from its cassette; print which miss (a prompt moved) and each verdict."""
import json, sys, traceback
from pathlib import Path
sys.path.insert(0, os.getcwd())               # run from the repository root
from tests.replays import cassettes
from tests.replays.engine_runner import pin_scratch_database
from tests.replays.founder_case import load_cases
from tests.replays.harness import CassetteMiss
from tests.replays.marking import judge

pin_scratch_database()
out = {}
ids = sys.argv[1:]
for case in load_cases():
    if ids and case.case_id not in ids:
        continue
    try:
        run = cassettes.replay(case)
        m = judge(case, run)
        out[case.case_id] = {"miss": False, "verdict": m.verdict, "lost_at": m.lost_at,
                             "reason": m.reason[:160], "cards": len(run.cards)}
    except CassetteMiss as e:
        out[case.case_id] = {"miss": True, "error": str(e)[:300]}
    except Exception as e:  # noqa
        out[case.case_id] = {"miss": None, "error": traceback.format_exc()[-600:]}
    print(case.case_id, json.dumps(out[case.case_id])[:260], flush=True)
print(json.dumps(out, indent=1))
