"""STEP-06 · the before-measure, part 2: every active situation's recorded end, on the golden set.

For each founder case (cassette, no spend): every active situation, its domain and type, whether
its domain is live for the tenant, its latest admission decision (or none), and the change gate's
recorded outcomes for it (or none). A situation with neither has NO durable record of what became
of it — only counters in a log line. Read-only queries; the tenant is removed after each case.
Run from the repo root:  GENIOS_TEST_DATABASE_URL=… .venv/bin/python <this file> out.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from sqlalchemy import text  # noqa: E402

from tests.replays.cassettes import load  # noqa: E402
from tests.replays.engine_runner import pin_scratch_database, remove_tenant, run_case  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402

SITUATIONS = (
    "select s.situation_id, s.domain, s.situation_type, s.status, "
    "       (select d.outcome from situation_admission_decisions d where d.org_id = s.org_id "
    "         and d.situation_id = s.situation_id order by d.decided_at desc limit 1) as admission, "
    "       (select d.reasons from situation_admission_decisions d where d.org_id = s.org_id "
    "         and d.situation_id = s.situation_id order by d.decided_at desc limit 1) as reasons, "
    "       (select string_agg(f.lane || ':' || f.outcome, ',' order by f.subject_key) "
    "          from reasoning_fingerprints f where f.org_id = s.org_id "
    "           and f.subject_key like s.situation_id || '|%') as gate "
    "  from context_situations s where s.org_id = :o and s.status in ('active', 'partial')")


def main(out_path: str) -> int:
    pin_scratch_database()
    from genios_engine.api import routes
    from genios_engine.platform.l3_activation import activated_domains
    from genios_engine.reason.domain_shadow import l3_domain_for
    engine = routes._graph.engine
    rows_out, totals = [], Counter()
    for case in load_cases():
        run = run_case(case, RecordedLLM(load(case)), keep=True)
        try:
            live = activated_domains(engine, run.org_id)
            with engine.connect() as c:
                for r in c.execute(text(SITUATIONS), {"o": run.org_id}).mappings():
                    corpus = l3_domain_for(r["domain"])
                    lane = ("live" if corpus in live else
                            "unroutable" if corpus is None else "shadow")
                    end = ("decided" if r["gate"] else
                           f"admission:{r['admission']}" if r["admission"] else "NONE")
                    totals[f"{lane}|{end}"] += 1
                    rows_out.append({"case": case.case_id, "situation_id": r["situation_id"],
                                     "domain": r["domain"], "type": r["situation_type"],
                                     "lane": lane, "admission": r["admission"],
                                     "reasons": r["reasons"], "gate": r["gate"], "end": end})
        finally:
            remove_tenant(engine, run.org_id)
        print(case.case_id, flush=True)
    by_type = Counter(f"{x['lane']}|{x['domain']}:{x['type']}|{x['end']}" for x in rows_out)
    Path(out_path).write_text(json.dumps({"totals": dict(totals), "by_type": dict(by_type),
                                          "rows": rows_out}, indent=1, default=str))
    print("TOTALS", json.dumps(dict(sorted(totals.items())), indent=1))
    print("BY TYPE", json.dumps(dict(sorted(by_type.items())), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
