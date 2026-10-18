"""STEP-06 · the before-measure on the golden set: what ends with no recorded end state.

Runs every founder case through the real chain with its cassette (no spend), keeps the tenant,
reads what STEP-06 promises to make zero, then removes the tenant. Read-only queries only.
Run from the repo root:  GENIOS_TEST_DATABASE_URL=… .venv/bin/python <this file> out.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from tests.replays.cassettes import load  # noqa: E402
from tests.replays.engine_runner import pin_scratch_database, remove_tenant, run_case  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402

Q = {
    "cards_total": "select count(*) from cards where org_id=:o",
    "cards_expired": "select count(*) from cards where org_id=:o and state='expired'",
    "cards_expired_no_event":
        "select count(*) from cards c where c.org_id=:o and c.state='expired' and not exists "
        "(select 1 from card_events e where e.card_id=c.card_id and e.org_id=c.org_id "
        " and e.kind in ('card.expired','window.lapsed','card.dismissed'))",
    "situations_total": "select count(*) from context_situations where org_id=:o",
    "situations_active":
        "select count(*) from context_situations where org_id=:o and status in ('active','partial')",
    "admitted_latest":
        "select count(*) from (select distinct on (situation_id) situation_id, outcome "
        "from situation_admission_decisions where org_id=:o "
        "order by situation_id, decided_at desc) d where d.outcome='admit'",
    "held_latest":
        "select count(*) from (select distinct on (situation_id) situation_id, outcome "
        "from situation_admission_decisions where org_id=:o "
        "order by situation_id, decided_at desc) d where d.outcome='hold'",
    "admitted_no_fingerprint":
        "select count(*) from (select distinct on (situation_id) situation_id, outcome "
        "from situation_admission_decisions where org_id=:o "
        "order by situation_id, decided_at desc) d where d.outcome='admit' and not exists "
        "(select 1 from reasoning_fingerprints f where f.org_id=:o "
        " and f.subject_key like d.situation_id || '|%')",
    "fingerprint_outcomes":
        "select lane || ':' || outcome, count(*) from reasoning_fingerprints where org_id=:o "
        "group by 1",
    "events_by_outcome": "select outcome, count(*) from source_events where org_id=:o group by 1",
    "events_no_end_state":
        "select count(*) from source_events se where se.org_id=:o "
        "and se.outcome <> 'superseded' "
        "and not exists (select 1 from l2_processing_runs r where r.org_id=se.org_id "
        "                and r.event_id=se.event_id) "
        "and not exists (select 1 from parked_events p where p.org_id=se.org_id "
        "                and p.event_id=se.event_id) "
        "and not exists (select 1 from event_trace t where t.org_id=se.org_id "
        "                and t.event_id=se.event_id "
        "                and t.action in ('drop','park','short_circuit','archive'))",
}
GROUPED = {"fingerprint_outcomes", "events_by_outcome"}


def main(out_path: str) -> int:
    pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    per_case, totals = {}, Counter()
    for case in load_cases():
        run = run_case(case, RecordedLLM(load(case)), keep=True)
        row = {}
        try:
            with engine.connect() as c:
                for name, sql in Q.items():
                    if name in GROUPED:
                        row[name] = {k: v for k, v in c.execute(text(sql), {"o": run.org_id})}
                    else:
                        row[name] = c.execute(text(sql), {"o": run.org_id}).scalar()
                        totals[name] += row[name]
        finally:
            remove_tenant(engine, run.org_id)
        per_case[case.case_id] = row
        print(case.case_id, {k: v for k, v in row.items() if k not in GROUPED}, flush=True)
    Path(out_path).write_text(json.dumps({"totals": dict(totals), "per_case": per_case},
                                         indent=1, default=str))
    print("TOTALS", dict(totals))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
