"""Replay a live expert pass from the answers it recorded — no spend — and read what the check made of each review.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55433/<fresh db> \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s13b/replay_live_pass.py" \
        <folder of the live pass's per-case cassettes> <out.json> [F03 F10 …]

STEP-13b §8 (the check of 12 Oct). `scripts/golden_eval.py --live --site expert` keeps, beside its scorecard, every
answer the run was given (`scores/<date>-<model>-expert/<case>.json`: the live model's for the expert site, the
ideal reader's for every other). The scorecard says which cases moved; it does not say WHY — the review's fate,
what the check dropped and for which reason. This replays each case from those answers (the prompts are the
same bytes at this commit: `git diff 7d88ef25 d3c1bb3c -- genios_engine/reason/expert genios_engine/contracts
tests/replays` is empty), keeps the tenant long enough to read its `expert_reviews` rows, then removes it.

Read-only but for the scratch tenant it writes and removes. Never a model call: a cassette miss is recorded.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))


def main(argv: list[str]) -> int:
    folder, out = Path(argv[0]), Path(argv[1])
    only = set(argv[2:])
    from sqlalchemy import text

    from tests.replays.engine_runner import pin_scratch_database, remove_tenant, run_case
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import CassetteMiss, RecordedLLM
    from tests.replays.marking import judge

    pin_scratch_database()
    from genios_engine.api import routes
    rows = []
    for case in load_cases():
        if only and case.case_id not in only:
            continue
        path = folder / f"{case.case_id}.json"
        if not path.is_file():
            continue
        answers = json.loads(path.read_text(encoding="utf-8"))
        row: dict = {"case": case.case_id, "kind": case.kind}
        try:
            run = run_case(case, RecordedLLM(answers), keep=True)
        except CassetteMiss as miss:                       # not the recorded run
            row["miss"] = str(miss)
            rows.append(row)
            print(case.case_id, "MISS", miss, flush=True)
            continue
        mark = judge(case, run)
        row.update(verdict=mark.verdict, reason=mark.reason, misses=len(run.misses))
        engine = routes._graph.engine
        with engine.connect() as conn:
            reviews = conn.execute(text(
                "select file_id, fingerprint, model, status, reason, review, checked, input_tokens, "
                "       output_tokens, cost_micro_usd, reviewed_at "
                "  from expert_reviews where org_id = :o order by reviewed_at, file_id"),
                {"o": run.org_id}).mappings().all()
        row["reviews"] = []
        for r in reviews:
            checked = r["checked"] or {}
            review = r["review"] or {}
            row["reviews"].append({
                "file": r["file_id"], "status": r["status"], "reason": r["reason"],
                "mode": review.get("mode"),
                "fate": checked.get("fate"), "because": checked.get("because"),
                "question": checked.get("question"),
                "dropped": [[v["line"], v.get("reason"), v.get("detail", "")[:160]]
                            for v in checked.get("verdicts") or () if v.get("verdict") == "dropped"],
                "corrected": [[v["line"], v.get("detail", "")[:160]]
                              for v in checked.get("verdicts") or () if v.get("verdict") == "corrected"],
                "noted": [[v["line"], v.get("reason")]
                          for v in checked.get("verdicts") or () if v.get("verdict") == "noted"],
                "facts": len(review.get("facts") or ()), "patterns": len(review.get("patterns") or ()),
                "inferences": len(review.get("inferences") or ()),
                "tokens": [r["input_tokens"], r["output_tokens"]], "cost_micro_usd": r["cost_micro_usd"]})
        remove_tenant(engine, run.org_id)
        rows.append(row)
        fates = Counter((v["status"], v["fate"]) for v in row["reviews"])
        print(case.case_id, mark.verdict, dict(fates), flush=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
