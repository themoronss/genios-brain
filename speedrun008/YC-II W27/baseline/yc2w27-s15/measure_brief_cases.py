"""STEP-15 check — what the brief-only golden cases leave behind today, case by case (read-only measurement).

Runs each named case through the real chain with its recorded answers (no spend), keeps the tenant on a
FRESH scratch database (never deleted — the database is this run's alone), and reads back what a morning
brief would have to work with: the files, the expert's checked reviews (mode, fate, question), the open
founder questions, the decisions' outcomes and lanes, the signals and cards.

Usage (from the worktree, so its code runs):
  GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55433/<fresh db> \
    <repo>/.venv/bin/python <this file> F08 F14 ...
"""
from __future__ import annotations

import json
import os
import sys

WT = os.getcwd()
sys.path.insert(0, WT)

from tests.replays import cassettes, engine_runner  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402
from tests.replays.marking import judge  # noqa: E402


def q(conn, sql, **kw):
    from sqlalchemy import text
    return conn.execute(text(sql), kw).mappings().all()


def main(ids: list[str]) -> None:
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    out = {}
    for cid in ids:
        case = cases[cid]
        llm = RecordedLLM(cassettes.load(case))
        run = engine_runner.run_case(case, llm, keep=True)
        mark = judge(case, run)
        org = run.org_id
        with engine.connect() as c:
            reviews = q(c, "select file_id, status, reason, review->>'mode' as mode, "
                           "checked->>'fate' as fate, checked->>'question' as question, "
                           "checked->'words'->>'headline' as headline, "
                           "review->>'wait_or_stop' as wait_or_stop, "
                           "review->'appraisal'->>'stakes' as stakes, "
                           "review->'appraisal'->>'urgency' as urgency, reviewed_at "
                           "from expert_reviews where org_id=:o order by file_id, reviewed_at", o=org)
            questions = q(c, "select file_id, state, question from founder_questions where org_id=:o", o=org)
            signals = q(c, "select signal_id, status, output_lane, lane_reason from signals where org_id=:o", o=org)
            cards = q(c, "select card_id, state, output_lane, headline from cards where org_id=:o", o=org)
            meetings = q(c, "select n.node_id, n.display_name, f.value #>> '{}' as start_at from graph_nodes n "
                            "join graph_facts f on f.org_id=n.org_id and f.subject_node_id=n.node_id "
                            "and f.field='meeting.start_at' and f.valid_to is null "
                            "where n.org_id=:o and n.node_type='meeting' and n.valid_to is null", o=org)
            commitments = q(c, "select count(*) as n from graph_facts where org_id=:o and "
                               "field='commitment.due_at' and valid_to is null and status='active'", o=org)
        from genios_engine.context.workstreams import files_for
        with engine.connect() as c:
            ws = files_for(c, org, now=case.sweeps[-1])
        files = [{"file": f.file_id, "kind": f.work_kind or f.kind, "counterparty": f.counterparty,
                  "whose_move": f.whose_move, "days_quiet": f.days_quiet,
                  "open_asks": [(a.kind, a.owed_by) for a in f.open_asks]} for f in ws.files]
        out[cid] = {
            "verdict": mark.verdict, "expected_brief": case.expected_other.get("brief"),
            "files": files,
            "reviews": [{k: (str(v) if k == "reviewed_at" else v) for k, v in dict(r).items()} for r in reviews],
            "open_questions": [dict(r) for r in questions],
            "signals": [dict(r) for r in signals],
            "cards": [dict(r) for r in cards],
            "meetings": [dict(r) for r in meetings],
            "commitments_due_facts": commitments[0]["n"] if commitments else 0,
            "model_calls": len(run.model_calls), "misses": len(run.misses),
        }
        print(f"== {cid} verdict={mark.verdict} files={len(files)} reviews={len(reviews)} "
              f"signals={len(signals)} cards={len(cards)} questions={len(questions)}", flush=True)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
