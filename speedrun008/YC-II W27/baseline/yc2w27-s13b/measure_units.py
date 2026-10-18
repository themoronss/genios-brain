"""What the Reasoning Expertise — the reasoning units — says about a golden file, and what its compile holds.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55433/<fresh db> \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s13b/measure_units.py" \
        <out.json> F02 F45 …

STEP-13b §8 (the check of 12 Oct). Since STEP-12 M33 a situation its file's review explains stands down BEFORE the
compile (`reason/domain_shadow.py`, `covers.explaining` → `continue`), so on an expert-covered file no package is
built and no reasoning unit runs. To see what the engine WOULD hand the expert, each named case is replayed from its
ideal reader (`tests/replays/ideal_reader.IdealReader`, no spend — the cassettes hold no answer for the compiled
lane's own sites, the decider and R-1, which an expert-off run asks) with the expert switched OFF (`run_case(expert=False)`): the compiled lane then
compiles and reasons every situation of the founder's switched-on corpora, and the run's rows say, per situation,
which units completed, were skipped or lacked context, what they found, and what its package carried.

It reads, too, every situation's admission decision (`situation_admission_decisions`): a situation the L2 publisher
HOLDS never reaches the compile (`reason/domain_shadow.py`, `if not publication.admitted … continue`), so it has no
package and no unit runs on it, covered or not.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))


def main(argv: list[str]) -> int:
    out, only = Path(argv[0]), set(argv[1:])
    from sqlalchemy import text

    from tests.replays.engine_runner import pin_scratch_database, remove_tenant, run_case
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import CassetteMiss
    from tests.replays.ideal_reader import IdealReader

    pin_scratch_database()
    from genios_engine.api import routes
    rows = []
    for case in load_cases():
        if case.case_id not in only:
            continue
        row: dict = {"case": case.case_id}
        llm = IdealReader(case)
        try:
            run = run_case(case, llm, keep=True, expert=False)
        except CassetteMiss as miss:
            row["miss"] = str(miss)
            rows.append(row)
            print(case.case_id, "MISS", miss, flush=True)
            continue
        row["misses"] = [list(m) for m in run.misses]
        engine = routes._graph.engine
        with engine.connect() as conn:
            results = conn.execute(text(
                "select r.run_id, r.reasoner_id, r.status, r.output, r.skip_reason_code, r.error_code "
                "  from reasoning_reasoner_results r where r.org_id = :o order by r.run_id, r.ordinal"),
                {"o": run.org_id}).mappings().all()
            runs = conn.execute(text("select count(*) from reasoning_runs where org_id = :o"),
                                {"o": run.org_id}).scalar()
            packages = conn.execute(text(
                "select count(*) from expertise_packages where org_id = :o"), {"o": run.org_id}).scalar()
            sits = conn.execute(text(
                "select situation_type, domain, status from context_situations where org_id = :o"),
                {"o": run.org_id}).all()
            admissions = conn.execute(text(
                "select outcome, reasons from situation_admission_decisions where org_id = :o"),
                {"o": run.org_id}).all()
        status = Counter((r["reasoner_id"], r["status"]) for r in results)
        kinds: dict[str, Counter] = defaultdict(Counter)
        for r in results:
            for f in (r["output"] or {}).get("findings") or ():
                kinds[r["reasoner_id"]][f.get("kind")] += 1
        held = Counter(str(reason) for a in admissions for reason in (a.reasons or ()))
        row.update(runs=runs, packages=packages, situations=[list(s) for s in sits],
                   admissions=dict(Counter(a.outcome for a in admissions)), hold_reasons=dict(held),
                   units={f"{u}:{s}": n for (u, s), n in sorted(status.items())},
                   findings={u: dict(c) for u, c in sorted(kinds.items())},
                   skips=dict(Counter(r["skip_reason_code"] for r in results if r["skip_reason_code"])))
        remove_tenant(engine, run.org_id)
        rows.append(row)
        print(case.case_id, "runs", runs, "packages", packages, "units", len(status),
              "admissions", row["admissions"], "held for", row["hold_reasons"], flush=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
