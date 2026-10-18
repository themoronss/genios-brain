"""Replay every founder case from its cassette; print which miss (a prompt moved) and each verdict.

    cd <worktree> && PYTHONPATH=. GENIOS_TEST_DATABASE_URL=… <venv>/bin/python which_miss.py [F01 …]
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.getcwd())               # run from the worktree root: its own code
import genios_engine                           # noqa: E402
print("engine:", genios_engine.__file__, flush=True)
from tests.replays import cassettes            # noqa: E402
from tests.replays.engine_runner import pin_scratch_database  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import CassetteMiss  # noqa: E402
from tests.replays.marking import judge         # noqa: E402

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
        out[case.case_id] = {"miss": True, "error": str(e)[:400]}
    except Exception:  # noqa: BLE001
        out[case.case_id] = {"miss": None, "error": traceback.format_exc()[-800:]}
    print(case.case_id, json.dumps(out[case.case_id])[:300], flush=True)
print("JSON", json.dumps(out))
