"""Per-object gate outcome on the golden set, from whatever checkout is first on sys.path.

    cd <checkout> && GENIOS_TEST_DATABASE_URL=... <venv>/python <this> out.json
"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import genios_engine
from tests.replays.founder_case import load_cases
from tests.replays import cassettes
from tests.replays.engine_runner import pin_scratch_database
from tests.replays.marking import judge

print("engine from:", genios_engine.__file__, file=sys.stderr)
pin_scratch_database()
out = {"engine": genios_engine.__file__, "cases": {}}
for case in load_cases():
    run = cassettes.replay(case)
    mark = judge(case, run)
    out["cases"][case.case_id] = {
        "kind": case.kind, "verdict": mark.verdict, "lost_at": mark.lost_at,
        "cards": len(run.cards),
        "landed": [{"object_id": l.object_id, "source_object_id": l.source_object_id,
                    "outcome": l.outcome, "reason": l.reason, "sweep": l.sweep}
                   for l in run.landed],
    }
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print("cases:", len(out["cases"]), file=sys.stderr)
