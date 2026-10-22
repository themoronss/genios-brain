"""Dump every card the golden set produces, on today's path and on the L2 path (ideal reader, no spend).

    GENIOS_TEST_DATABASE_URL=... python card_dump.py OUT.json [F01 F02 ...]
"""
import json
import os
import sys
import traceback

REPO = sys.argv[1]
OUT = sys.argv[2]
IDS = sys.argv[3:]
sys.path.insert(0, REPO)
os.chdir(REPO)

from tests.replays.engine_runner import L2_PATH_ENV, pin_scratch_database, run_case  # noqa: E402

pin_scratch_database()
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.ideal_reader import IdealReader  # noqa: E402
from tests.replays.marking import judge  # noqa: E402


def _j(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        return str(v)


def one(case, l2):
    if l2:
        os.environ[L2_PATH_ENV] = "1"
    else:
        os.environ.pop(L2_PATH_ENV, None)
    try:
        run = run_case(case, IdealReader(case))
        verdict = judge(case, run)
        cards = [{
            "card_id": c.card_id, "state": c.state, "level": c.level, "lane": c.output_lane,
            "sweeps": list(c.sweeps), "app_sweeps": list(c.app_sweeps), "versions": len(c.versions),
            "ended": c.ended, "gold": {k: _j(v) for k, v in (c.gold or {}).items()},
            "text": c.text,
        } for c in run.cards]
        return {"verdict": getattr(verdict, "verdict", None), "reason": getattr(verdict, "reason", None),
                "situations": len(run.situations or ()), "cards": cards}
    except BaseException as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {str(exc)[:300]}", "tb": traceback.format_exc()[-800:]}
    finally:
        os.environ.pop(L2_PATH_ENV, None)


out = {}
for case in [c for c in load_cases() if not IDS or c.case_id in IDS]:
    out[case.case_id] = {"title": case.title, "kind": case.kind,
                         "expected": _j(case.raw.get("expected") if hasattr(case, "raw") else None),
                         "today": one(case, False), "l2": one(case, True)}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    t, n = out[case.case_id]["today"], out[case.case_id]["l2"]
    print(case.case_id, "today", t.get("verdict") or t.get("error", "")[:60], len(t.get("cards", [])),
          "| l2", n.get("verdict") or n.get("error", "")[:60], len(n.get("cards", [])), flush=True)
