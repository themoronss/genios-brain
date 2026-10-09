"""STEP-12 check: replay the founder cases from their cassettes and read, per case, what an expert pass
would be handed for each FILE (the brief's line, the file, its timeline, its numbers, its playbook),
what the model was actually asked (calls per site; each decider answer), and how the case was marked.
No model spend; read only.

Run from the repo root, on a NEW scratch database:
  GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/<new db> \
    .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s12-check/measure_expert_inputs.py" [CASE ...]

Writes one JSON per case into `out/` beside itself (not kept in git) and `out/_summary.json`. Every
tenant is removed in a `finally`.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.getcwd())
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

from tests.replays.engine_runner import ORG_PREFIX, pin_scratch_database  # noqa: E402

URL = pin_scratch_database()          # BEFORE api.routes is imported

from sqlalchemy import text  # noqa: E402

from tests.replays import cassettes  # noqa: E402
from tests.replays.engine_runner import remove_tenant, run_case  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402
from tests.replays.marking import judge  # noqa: E402


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def _measured(m):
    return None if m is None else {"value": getattr(m, "value", None), "n": getattr(m, "n", None),
                                   "basis": getattr(m, "basis", None)}


def read_files(engine, org, now):
    """Each file of the tenant as an expert pass would be handed it — read through the same modules the
    one-file route reads (`api/workstream_routes.read_workstream`)."""
    from genios_engine.context.workstream_numbers import numbers_for
    from genios_engine.context.workstream_timeline import timeline_for
    from genios_engine.context.workstreams import files_for
    from genios_engine.packs.compiler.playbook_reader import playbook_for
    from genios_engine.platform import company_brief

    out = []
    with engine.connect() as conn:
        brief = company_brief.brief_for(conn, org)
        ws = files_for(conn, org, now=now)
        for f in ws.files:
            tl = timeline_for(conn, org, f.file_id, now=now)
            nums = numbers_for(conn, org, f, tl, now=now)
            pb = playbook_for(f.work_kind)
            people = [{"their_reply_time": _measured(p.their_reply_time),
                       "their_normal": _measured(p.their_normal),
                       "your_reply_time": _measured(p.your_reply_time),
                       "your_normal": _measured(p.your_normal)}
                      for p in nums.people]
            out.append({
                "file_id": f.file_id, "counterparty": f.counterparty, "role": f.kind,
                "work_kind": f.work_kind, "brief_line": f.line, "domains": list(f.domains),
                "events": len(f.events), "correlations": len(f.correlations),
                "days_quiet": f.days_quiet, "whose_move": f.whose_move,
                "open_asks": len(f.open_asks), "introduced_by": f.introduced_by,
                "touches": len(tl.touches), "upcoming": len(tl.upcoming),
                "usual_gap": _measured(tl.usual_gap),
                "silence_exceeds_prior_gaps": tl.silence_exceeds_prior_gaps,
                "people_numbers": people, "waves": len(nums.waves),
                "no_reply_can_be_said": nums.no_reply_can_be_said,
                "mailboxes": len(nums.mailboxes),
                "playbook": {"reason": pb.reason,
                             "spine": getattr(getattr(pb, "playbook", None), "playbook_id", None),
                             "stages": len(getattr(getattr(pb, "playbook", None), "stages", ()) or ()),
                             "review_label": getattr(getattr(pb, "playbook", None), "review_label", None)},
            })
        unfiled = [n.named for n in ws.unfiled]
    return {"brief_lines": len(getattr(brief, "lines", ()) or ()),
            "brief_truncated": list(getattr(brief, "truncated", ()) or ()),
            "files": out, "unfiled_named": unfiled}


def read_reasoning(engine, org):
    with engine.connect() as conn:
        rows = lambda sql: [dict(r._mapping) for r in conn.execute(text(sql), {"o": org}).fetchall()]  # noqa: E731
        sits = rows("select situation_id, anchor_node_id, situation_type, domain, status "
                    "from context_situations where org_id = :o order by situation_type")
        ends = rows("select situation_id, outcome, reason from situation_outcomes where org_id = :o")
        cards = rows("select c.card_id, c.state, c.domain, c.capability_key, c.output_lane, c.headline, "
                     "s.rule_id from cards c left join signals s on s.signal_id = c.signal_id "
                     "and s.org_id = c.org_id where c.org_id = :o order by c.created_at")
        interp = rows("select situation_id, outcome from situation_interpretations where org_id = :o")
    end_of = {e["situation_id"]: f'{e["outcome"]}:{e["reason"]}' for e in ends}
    return {"situations": [{"type": s["situation_type"], "domain": s["domain"], "status": s["status"],
                            "end": end_of.get(s["situation_id"]),
                            "anchor": s["anchor_node_id"]} for s in sits],
            "cards": [{"state": c["state"], "domain": c["domain"], "rule": c["rule_id"],
                       "lane": c["output_lane"], "headline": (c["headline"] or "")[:120]} for c in cards],
            "r6_interpretations": len(interp)}


def decider_answers(case, calls):
    answers = cassettes.load(case)
    raw = json.loads(Path(cassettes.path_for(case)).read_text()) if hasattr(cassettes, "path_for") else None
    parsed = {}
    if raw is not None:
        parsed = {k: v for k, v in raw.get("answers", {}).items() if isinstance(v, dict)}
    out = []
    for site, key in calls:
        if site != "decider":
            continue
        entry = parsed.get(key) or {}
        p = entry.get("parsed") or {}
        out.append({"outcome": p.get("outcome"), "play": p.get("play_id"),
                    "missing": p.get("missing"), "rationale": (p.get("rationale") or "")[:200]})
    return out, len(answers)


def main(ids):
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    summary = []
    for cid in ids:
        case = cases[cid]
        org = f"{ORG_PREFIX}{case.case_id.lower()}"
        rec = {"case": cid, "title": case.title, "case_kind": case.kind, "blocked_on": case.blocked_on}
        t0 = time.time()
        try:
            llm = RecordedLLM(cassettes.load(case))
            run = run_case(case, llm, keep=True)
            mark = judge(case, run)
            calls = list(run.model_calls)
            rec.update(verdict=mark.verdict, lost_at=mark.lost_at, reason=mark.reason,
                       misses=list(run.misses),
                       calls_by_site=dict(Counter(site for site, _ in calls)),
                       cards_visible=[{"subject": c.subject, "lane": c.output_lane,
                                       "first_line": c.text.split("\n", 1)[0][:160]} for c in run.cards])
            rec["decider"], _ = decider_answers(case, calls)
            now = case.sweeps[-1]
            rec.update(read_files(engine, org, now))
            rec.update(read_reasoning(engine, org))
        except BaseException as e:   # noqa: BLE001 — a cassette miss is a BaseException
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()[-3000:]
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            try:
                remove_tenant(engine, org)
                rec["tenant_removed"] = True
            except BaseException as e:  # noqa: BLE001
                rec["tenant_removed"] = f"FAILED: {type(e).__name__}: {e}"
        rec["seconds"] = round(time.time() - t0, 1)
        (OUT / f"{cid}.json").write_text(json.dumps(_jsonable(rec), indent=1, default=str))
        summary.append({k: rec.get(k) for k in ("case", "case_kind", "verdict", "lost_at", "error",
                                                 "tenant_removed", "seconds")})
        print(json.dumps(summary[-1], default=str), flush=True)
    with engine.connect() as conn:
        left = conn.execute(text("select id from orgs where id like :p"),
                            {"p": ORG_PREFIX + "%"}).scalars().all()
    (OUT / "_summary.json").write_text(json.dumps({"runs": summary, "golden_orgs_left": left},
                                                  indent=1, default=str))
    print("golden orgs left:", left)


if __name__ == "__main__":
    wanted = sys.argv[1:] or sorted(c.case_id for c in load_cases())
    main(wanted)
