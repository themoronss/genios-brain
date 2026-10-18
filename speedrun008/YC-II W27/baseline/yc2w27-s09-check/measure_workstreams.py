"""STEP-09 read-only check, Task B: replay the STEP-09 golden cases from their cassettes, read the
tenant's rows BEFORE removing it, and write one JSON per run.

Run from the repo root:
  GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/s09_check_a \
    .venv/bin/python <this file> [CASE ...]

Writes only into `out/` beside itself. Every tenant is removed in a `finally`.
"""
from __future__ import annotations

import json
import os
import re
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

KIND = {}
for c in ("F03 F04 F05 F06 F07 F08 F09 F37").split():
    KIND[c] = "intro"
for c in ("F10 F11 F12 F13 F14 F15 F42 F44").split():
    KIND[c] = "investor"
for c in ("F17 F18 F19 F20 F21 F22 F23 F24 F31").split():
    KIND[c] = "program"
for c in ("F01 F02").split():
    KIND[c] = "compliance"
KIND["F25"] = "hire"
for c in ("F26 F27 F28 F29").split():
    KIND[c] = "partner"

CONNECTOR = "hello@introly.test"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


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


def read_tenant(engine, org, case, run):
    """Everything STEP-09 cares about, read from the tenant's rows."""
    ev_obj = {}
    for x in run.landed:
        if x.event_id:
            ev_obj[x.event_id] = x.object_id
    out = {}
    with engine.connect() as conn:
        nodes = _rows(conn, """
            select distinct on (node_id) node_id, node_type, canonical_key, display_name,
                   attributes, valid_to, version
              from graph_nodes where org_id = :o order by node_id, version desc""", o=org)
        name = {n["node_id"]: f'{n["display_name"]} [{n["node_type"]}]' for n in nodes}
        out["nodes"] = [{"node_id": n["node_id"], "type": n["node_type"],
                         "key": n["canonical_key"], "name": n["display_name"],
                         "live": n["valid_to"] is None} for n in nodes]

        corr = _rows(conn, """select correlation_id, anchor_node_id, anchor_type, domain,
                                generation, status, event_count, first_event_at, last_event_at
                           from context_correlations where org_id = :o
                          order by first_event_at, correlation_id""", o=org)
        members = _rows(conn, """select correlation_id, event_id, joined_via
                                   from context_correlation_members where org_id = :o""", o=org)
        for c in corr:
            c["anchor"] = name.get(c["anchor_node_id"], c["anchor_node_id"])
            c["members"] = sorted(f'{ev_obj.get(m["event_id"], m["event_id"])}:{m["joined_via"]}'
                                  for m in members if m["correlation_id"] == c["correlation_id"])
        out["correlations"] = corr

        sits = _rows(conn, """select situation_id, correlation_id, anchor_node_id, situation_type,
                                domain, status, resolved_by, resolution_note, missing,
                                confidence_overall, coverage, importance_bp
                           from context_situations where org_id = :o
                          order by situation_type, situation_id""", o=org)
        outcomes = _rows(conn, """select situation_id, outcome, reason, sweeps
                                    from situation_outcomes where org_id = :o""", o=org)
        admits = _rows(conn, """select situation_id, outcome, reasons
                                  from situation_admission_decisions where org_id = :o
                                 order by decided_at""", o=org)
        interp = _rows(conn, """select situation_id, outcome, proposal, reason_codes
                                  from situation_interpretations where org_id = :o""", o=org)
        for s in sits:
            s["anchor"] = name.get(s["anchor_node_id"], s["anchor_node_id"])
            s["outcomes"] = [f'{o["outcome"]}:{o["reason"]}' for o in outcomes
                             if o["situation_id"] == s["situation_id"]]
            s["admission"] = [f'{a["outcome"]}:{a["reasons"]}' for a in admits
                              if a["situation_id"] == s["situation_id"]]
            s["interpretations"] = [{"outcome": i["outcome"],
                                     "proposal_keys": sorted((i["proposal"] or {}).keys()),
                                     "reason_codes": i["reason_codes"]}
                                    for i in interp if i["situation_id"] == s["situation_id"]]
        out["situations"] = sits
        out["interpretations_total"] = len(interp)

        loops = _rows(conn, """select loop_id, subject_node_id, kind, thread_id, status,
                                 awaited_from_node_id, ask_count, opened_by_event,
                                 closed_by_event, closed_basis, opened_at, closed_at
                            from open_loops where org_id = :o order by opened_at""", o=org)
        for lp in loops:
            lp["subject"] = name.get(lp["subject_node_id"], lp["subject_node_id"])
            lp["awaited_from"] = name.get(lp["awaited_from_node_id"], lp["awaited_from_node_id"])
            lp["opened_by"] = ev_obj.get(lp["opened_by_event"], lp["opened_by_event"])
            lp["closed_by"] = ev_obj.get(lp["closed_by_event"], lp["closed_by_event"])
        out["open_loops"] = loops

        sig = _rows(conn, """select signal_id, rule_id, subject_node_id, status, situation_id,
                               capability_id, pack_id, level
                          from signals where org_id = :o order by created_at""", o=org)
        for s in sig:
            s["subject"] = name.get(s["subject_node_id"], s["subject_node_id"])
        out["signals"] = sig

        cards = _rows(conn, """select c.card_id, c.state, c.level, c.domain, c.headline,
                                 c.business_subject, c.relationship_role, c.capability_key,
                                 c.output_lane, c.signal_id, s.rule_id, s.situation_id
                            from cards c left join signals s
                              on s.signal_id = c.signal_id and s.org_id = c.org_id
                           where c.org_id = :o order by c.created_at""", o=org)
        out["cards_all"] = cards

        facts = _rows(conn, """select distinct on (fact_id) fact_id, subject_node_id, field, value,
                                 status, created_by_event_id, valid_to
                            from graph_facts where org_id = :o
                             and (field like '%%role%%' or field like '%%objective%%'
                                  or field like '%%relationship%%' or field like '%%intro%%')
                           order by fact_id, recorded_at desc""", o=org)
        for f in facts:
            f["subject"] = name.get(f["subject_node_id"], f["subject_node_id"])
            f["event"] = ev_obj.get(f["created_by_event_id"], f["created_by_event_id"])
        out["role_facts"] = [{"subject": f["subject"], "field": f["field"], "value": f["value"],
                              "status": f["status"], "event": f["event"],
                              "live": f["valid_to"] is None} for f in facts]

        ff = _rows(conn, """select field, count(*) as n from graph_facts where org_id = :o
                             group by field order by field""", o=org)
        out["fact_fields"] = {r["field"]: int(r["n"]) for r in ff}
        objective = _rows(conn, """select distinct on (fact_id) subject_node_id, field, value
                                 from graph_facts where org_id = :o
                                  and field in ('thread.objective', 'campaign.objective',
                                                'party.role', 'relationship.nature',
                                                'thread.stage', 'thread.status')
                                order by fact_id, recorded_at desc""", o=org)
        out["business_facts"] = [f'{name.get(r["subject_node_id"], r["subject_node_id"])}: '
                                 f'{r["field"]} = {r["value"]}' for r in objective]

        edges = _rows(conn, """select distinct on (edge_id) edge_id, edge_type, from_node_id,
                                 to_node_id, created_by_event_id, valid_to
                            from graph_edges where org_id = :o
                           order by edge_id, recorded_at desc""", o=org)
        out["edges"] = sorted(f'{name.get(e["from_node_id"], e["from_node_id"])} '
                              f'-{e["edge_type"]}-> {name.get(e["to_node_id"], e["to_node_id"])}'
                              for e in edges)

        obs = _rows(conn, """select subject_node_id, kind, status, created_by_event_id
                          from graph_observations where org_id = :o order by created_at""", o=org)
        out["observations"] = [f'{ev_obj.get(o_["created_by_event_id"], o_["created_by_event_id"])}'
                               f': {o_["kind"]} on {name.get(o_["subject_node_id"], o_["subject_node_id"])}'
                               f' ({o_["status"]})' for o_ in obs]

        qs = _rows(conn, """select event_id, signal_type, domain_hints, state, internal_kind
                         from qualified_signals where org_id = :o order by occurred_at""", o=org)
        out["qualified_signals"] = [f'{ev_obj.get(q["event_id"], q["event_id"])}: {q["signal_type"]}'
                                    f' {q["domain_hints"]} {q["state"]} {q["internal_kind"]}'
                                    for q in qs]
        se = _rows(conn, """select event_id, object_type, outcome, attention, attention_reason,
                               domain_hints, internal_kind, route
                          from source_events where org_id = :o order by occurred_at""", o=org)
        out["source_events"] = [f'{ev_obj.get(s["event_id"], s["event_id"])}: {s["object_type"]}'
                                f' {s["outcome"]} att={s["attention"]}/{s["attention_reason"]}'
                                f' hints={s["domain_hints"]} kind={s["internal_kind"]} route={s["route"]}'
                                for s in se]
    return out, nodes


def intro_contacts(case):
    """The people a connector's mail introduced: To/Cc of mail from the connector, minus us."""
    ours = {a.lower() for a in case.founder.addresses}
    found = []
    for o in case.objects:
        if o.source != "gmail" or (o.sender_email or "") != CONNECTOR:
            continue
        for addr in (*o.to, *o.cc):
            m = _EMAIL.search(addr)
            if m and m.group(0).lower() not in ours and m.group(0).lower() != CONNECTOR:
                if m.group(0).lower() not in found:
                    found.append(m.group(0).lower())
    return found


def per_contact(contact, data, nodes, run):
    """Does this introduced contact have its OWN correlation / situation / loop / card?"""
    local, domain = contact.split("@", 1)
    first = local.split(".")[0]
    mine = [n for n in nodes if contact in (n["canonical_key"] or "").lower()
            or contact in json.dumps(n["attributes"] or {}).lower()]
    org_nodes = [n for n in nodes if n["node_type"] in ("company", "organization", "organisation")
                 and domain.split(".")[0] in ((n["canonical_key"] or "") + " "
                                              + (n["display_name"] or "")).lower()]
    ids = {n["node_id"] for n in mine} | {n["node_id"] for n in org_nodes}
    corr = [c for c in data["correlations"] if c["anchor_node_id"] in ids]
    sits = [s for s in data["situations"] if s["anchor_node_id"] in ids]
    loops = [lp for lp in data["open_loops"] if lp["subject_node_id"] in ids
             or lp["awaited_from_node_id"] in ids]
    name_terms = {first.lower()} | {domain.split(".")[0].lower()}
    visible = [c for c in run.cards if any(t in c.text.lower() for t in name_terms)]
    intro_member = [c["correlation_id"] for c in corr if any(m.startswith(("intro", "simon", "omar"))
                                                            for m in c["members"])]
    return {"contact": contact,
            "person_nodes": [f'{n["display_name"]} [{n["node_type"]}] {n["canonical_key"]}'
                             for n in mine],
            "org_nodes": [f'{n["display_name"]} [{n["node_type"]}] {n["canonical_key"]}'
                          for n in org_nodes],
            "own_correlations": [f'{c["anchor"]} · {c["domain"]} · {c["members"]}' for c in corr],
            "intro_mail_is_member_of_own_correlation": bool(intro_member),
            "own_situations": [f'{s["situation_type"]} · {s["domain"]} · {s["status"]} · '
                               f'{s["outcomes"]}' for s in sits],
            "loops": [f'{lp["kind"]} subj={lp["subject"]} awaited={lp["awaited_from"]} '
                      f'{lp["status"]}' for lp in loops],
            "cards_visible_naming_contact": [c.card_id for c in visible]}


def main(ids):
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    summary = []
    for cid in ids:
        case = cases[cid]
        org = f"{ORG_PREFIX}{case.case_id.lower()}"
        rec = {"case": cid, "kind": KIND.get(cid), "title": case.title,
               "case_kind": case.kind, "blocked_on": case.blocked_on,
               "expected_other": dict(case.expected_other),
               "expected_cards": [{"about": e.about, "min": e.min, "max": e.max}
                                  for e in case.cards]}
        t0 = time.time()
        try:
            run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
            mark = judge(case, run)
            rec["verdict"] = mark.verdict
            rec["lost_at"] = mark.lost_at
            rec["reason"] = mark.reason
            rec["misses"] = list(run.misses)
            rec["chain_ok"] = list(run.chain_ok)
            rec["model_calls"] = len(run.model_calls)
            rec["landed"] = [f"{x.object_id}@{x.sweep}: {x.outcome}"
                             + (f" ({x.reason})" if x.reason else "") for x in run.landed]
            rec["cards_visible"] = [{"card_id": c.card_id, "state": c.state, "subject": c.subject,
                                     "lane": c.output_lane, "sweeps": c.sweeps,
                                     "first_line": c.text.split("\n", 1)[0][:160]}
                                    for c in run.cards]
            data, nodes = read_tenant(engine, org, case, run)
            rec.update(data)
            if KIND.get(cid) == "intro":
                rec["introduced_contacts"] = [per_contact(ct, data, nodes, run)
                                              for ct in intro_contacts(case)]
        except BaseException as e:   # noqa: BLE001 — a cassette miss is a BaseException
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()[-4000:]
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
        summary.append({k: rec.get(k) for k in ("case", "kind", "verdict", "lost_at", "error",
                                                 "tenant_removed", "seconds")})
        print(json.dumps(summary[-1], default=str), flush=True)
    with engine.connect() as conn:
        left = conn.execute(text("select id from orgs where id like :p"),
                            {"p": ORG_PREFIX + "%"}).scalars().all()
    (OUT / "_summary.json").write_text(json.dumps({"runs": summary, "golden_orgs_left": left},
                                                  indent=1, default=str))
    print("golden orgs left:", left)


if __name__ == "__main__":
    wanted = sys.argv[1:] or sorted(KIND)
    main(wanted)
