"""STEP-15 check — what the existing morning surfaces print for a kept golden tenant (read-only).

Calls, at the case's last sweep instant: `executive/summary.build_summary` (the ladder, the Slack digest's
payload), `executive/brief.load_briefs` (the decision brief) and `reason/brief_ranking.open_decisions`
(what the daily re-rank would see). Nothing is written: `daily_brief_ranking` stores, so only its read
half is called.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

WT = os.getcwd()
sys.path.insert(0, WT)

from tests.replays import engine_runner  # noqa: E402


def main(pairs: list[str]) -> None:
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    from genios_engine.executive.brief import load_briefs
    from genios_engine.executive.summary import build_summary
    from genios_engine.reason.brief_ranking import open_decisions
    graph = routes._graph
    for pair in pairs:
        org, at = pair.split("@")
        when = datetime.fromisoformat(at.replace("Z", "+00:00")) + timedelta(minutes=5)
        print("=====", org, when.isoformat())
        for horizon in ("one_line", "one_minute", "five_minute"):
            s = build_summary(graph, org, horizon, eval_time=when)
            print(" summary", horizon, json.dumps(s, default=str)[:700])
        for b in load_briefs(graph, org, eval_time=when):
            print(" brief", json.dumps({k: b.get(k) for k in ("entity", "situation", "why_it_matters",
                                                               "recommendation", "risks", "grounded")},
                                       default=str)[:600])
        for d in open_decisions(graph.engine, org_id=org, eval_time=when):
            print(" open_decision", d.decision_id[:16], d.base_utility_bp, d.headline)


if __name__ == "__main__":
    main(sys.argv[1:])
