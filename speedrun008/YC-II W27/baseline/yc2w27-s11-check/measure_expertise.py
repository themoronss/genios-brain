"""STEP-11 check: replay the founder cases from their cassettes and read, per case, where its work lands
in L2 — the situations (type, domain, how each ended), what the decider answered for each, the signals
and cards with their capability and pack — before the tenant is removed. No model spend; read only.

Run from the repo root, on a NEW scratch database:
  GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/<new db> \
    .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s11-check/measure_expertise.py" [CASE ...]

Writes one JSON per case into `out/` beside itself and `out/_summary.json`. Every tenant is removed in a
`finally`.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
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


def _rows(conn, sql, **kw):
    return [dict(r._mapping) for r in conn.execute(text(sql), kw).fetchall()]


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


def read_tenant(engine, org):
    out = {}
    with engine.connect() as conn:
        name = {r["node_id"]: f'{r["display_name"]} [{r["node_type"]}]' for r in _rows(conn, """
            select distinct on (node_id) node_id, node_type, display_name
              from graph_nodes where org_id = :o order by node_id, version desc""", o=org)}
        sits = _rows(conn, """select situation_id, anchor_node_id, situation_type, domain, status,
                                     resolved_by, missing, importance_bp
                                from context_situations where org_id = :o
                               order by situation_type, situation_id""", o=org)
        ends = _rows(conn, """select situation_id, outcome, reason from situation_outcomes
                               where org_id = :o""", o=org)
        admits = _rows(conn, """select situation_id, outcome, reasons
                                  from situation_admission_decisions where org_id = :o
                                 order by decided_at""", o=org)
        interp = _rows(conn, """select situation_id, outcome, proposal, reason_codes
                                  from situation_interpretations where org_id = :o""", o=org)
        for s in sits:
            sid = s["situation_id"]
            s["anchor"] = name.get(s["anchor_node_id"], s["anchor_node_id"])
            s["ends"] = [f'{e["outcome"]}:{e["reason"]}' for e in ends if e["situation_id"] == sid]
            s["admission"] = [f'{a["outcome"]}:{a["reasons"]}' for a in admits if a["situation_id"] == sid]
            s["interpretations"] = []
            for i in interp:
                if i["situation_id"] != sid:
                    continue
                p = i["proposal"] or {}
                s["interpretations"].append({
                    "outcome": i["outcome"], "reason_codes": i["reason_codes"],
                    "keys": sorted(p.keys()) if isinstance(p, dict) else str(type(p)),
                    "play": (p.get("play_id") or p.get("play") or p.get("action_id")) if isinstance(p, dict) else None,
                    "stage": p.get("stage") if isinstance(p, dict) else None})
        out["situations"] = sits
        out["signals"] = _rows(conn, """select rule_id, capability_id, pack_id, situation_id, status, level
                                          from signals where org_id = :o order by created_at""", o=org)
        out["cards"] = _rows(conn, """select c.card_id, c.state, c.level, c.domain, c.capability_key,
                                             c.output_lane, c.headline, s.rule_id, s.situation_id
                                        from cards c left join signals s
                                          on s.signal_id = c.signal_id and s.org_id = c.org_id
                                       where c.org_id = :o order by c.created_at""", o=org)
        out["domains_active"] = [f'{r["domain"]}:{"off" if r["disabled_at"] else "on"}:{r["enabled_by"]}'
                                 for r in _rows(conn, """select domain, enabled_by, disabled_at
                                                           from l3_activation where org_id = :o
                                                          order by domain""", o=org)]
    return out


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
            run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
            mark = judge(case, run)
            rec.update(verdict=mark.verdict, lost_at=mark.lost_at, reason=mark.reason,
                       misses=list(run.misses), chain_ok=list(run.chain_ok),
                       cards_visible=[{"subject": c.subject, "lane": c.output_lane,
                                       "first_line": c.text.split("\n", 1)[0][:160]} for c in run.cards])
            rec.update(read_tenant(engine, org))
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
