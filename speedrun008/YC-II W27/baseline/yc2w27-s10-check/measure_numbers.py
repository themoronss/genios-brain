"""STEP-10 read-only check, Task B: replay the STEP-10 golden cases from their cassettes (no spend),
read every derived NUMBER the tenant holds BEFORE removing it, and write one JSON per case.

Run from the extracted tree at 79d0ff54 (cwd), with a NEW scratch database:
  GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/s10_check_a \
    <repo>/.venv/bin/python <this file> [CASE ...]

Writes only into OUT (scratchpad). Every tenant is removed in a `finally`.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

sys.path.insert(0, os.getcwd())
OUT = Path(os.environ.get("S10_OUT", "/tmp/s10_out"))
OUT.mkdir(parents=True, exist_ok=True)

from tests.replays.engine_runner import ORG_PREFIX, pin_scratch_database  # noqa: E402

URL = pin_scratch_database()          # BEFORE api.routes is imported

from sqlalchemy import text  # noqa: E402

from tests.replays import cassettes  # noqa: E402
from tests.replays.engine_runner import remove_tenant, run_case  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM  # noqa: E402
from tests.replays.marking import judge  # noqa: E402

GROUP = {}
for c in "F10 F11 F12 F13 F14 F15 F42 F44".split():
    GROUP[c] = "investor/wave"
for c in "F03 F04 F05 F06 F07 F08 F09 F37".split():
    GROUP[c] = "intro"
for c in "F17 F19 F24".split():
    GROUP[c] = "program"
GROUP["F16"] = "bounce"
for c in "F26 F27 F28 F29".split():
    GROUP[c] = "partner"
GROUP["F25"] = "hire"

TIME_WORDS = re.compile(
    r"(\b\d+(?:\.\d+)?\s*(?:day|days|hour|hours|hrs|week|weeks|month|months)\b"
    r"|usually|typically|normal|replies in|reply time|since\b|ago\b|silent|quiet|no reply"
    r"|follow[- ]?up)", re.I)

TIMELINE_SQL = (
    "select f.subject_node_id as node_id, f.field as field, se.occurred_at as at, "
    "       r.event_id as event_id "
    "from graph_source_refs r "
    "join graph_facts f on f.fact_version_id = r.fact_version_id and f.org_id = r.org_id "
    "join source_events se on se.event_id = r.event_id "
    "where r.org_id = :o and f.field in ('thread.last_outbound', 'thread.last_inbound')")


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


def _trim(v, n=300):
    s = json.dumps(_jsonable(v), default=str)
    return s if len(s) <= n else s[:n] + "…"


def _days(later, earlier):
    return round((later - earlier).total_seconds() / 86400.0, 2)


def _gaps(timeline, first, second):
    """Days from each `first`-direction message to the NEXT `second`-direction one. Only the first
    `second` after a pending `first` counts; consecutive `first`s keep the earliest pending."""
    out, pending = [], None
    for d, at, _ev in timeline:
        if d == first:
            if pending is None:
                pending = at
        elif d == second and pending is not None:
            out.append(_days(at, pending))
            pending = None
    return out


def read_tenant(engine, org, case, run):
    ev_obj = {x.event_id: x.object_id for x in run.landed if x.event_id}
    now = max(case.sweeps)
    founder = {a.lower() for a in case.founder.addresses}
    out = {"now": now}
    with engine.connect() as conn:
        nodes = _rows(conn, """select distinct on (node_id) node_id, node_type, canonical_key,
                                 display_name, valid_to from graph_nodes where org_id = :o
                               order by node_id, version desc""", o=org)
        name = {n["node_id"]: f'{n["display_name"]} [{n["node_type"]}]' for n in nodes}
        out["nodes"] = [f'{n["display_name"]} [{n["node_type"]}] {n["canonical_key"]}'
                        + ("" if n["valid_to"] is None else " (closed)") for n in nodes]

        facts = _rows(conn, """select fact_id, fact_version_id, subject_node_id, field, value,
                                 value_type, status, derivation_type, created_by_event_id,
                                 occurred_at, valid_from, valid_to, recorded_at
                            from graph_facts where org_id = :o order by field, subject_node_id,
                                 recorded_at""", o=org)
        out["fact_field_counts"] = {}
        for f in facts:
            out["fact_field_counts"][f["field"]] = out["fact_field_counts"].get(f["field"], 0) + 1
        live = [f for f in facts if f["valid_to"] is None and f["status"] == "active"]
        out["live_facts"] = [{"subject": name.get(f["subject_node_id"], f["subject_node_id"]),
                              "field": f["field"], "value": _trim(f["value"], 200),
                              "type": f["value_type"], "derivation": f["derivation_type"],
                              "event": ev_obj.get(f["created_by_event_id"], f["created_by_event_id"]),
                              "valid_from": f["valid_from"]}
                             for f in live]
        numberish = re.compile(r"^(party\.|thread\.|derived\.|outreach\.|cohort\.|campaign\.|"
                               r"analytic|engagement\.|relationship\.|deal\.|meeting\.|"
                               r"commitment\.|condition\.|awaiting|account\.)")
        out["derived_numbers"] = [x for x in out["live_facts"] if numberish.match(x["field"])]
        out["retired_waiting_facts"] = [
            {"subject": name.get(f["subject_node_id"], f["subject_node_id"]), "field": f["field"],
             "value": _trim(f["value"], 80), "valid_to": f["valid_to"], "status": f["status"]}
            for f in facts if f["valid_to"] is not None and numberish.match(f["field"])
            and f["field"].startswith(("thread.", "party.", "derived.history"))]

        out["baselines"] = [{"key": r["key"], "subject": name.get(r["key"].split(":", 1)[-1],
                                                                  r["key"].split(":", 1)[-1]),
                             "value": float(r["value"]), "n": r["sample_size"],
                             "cold_start": r["cold_start"], "method": r["method"]}
                            for r in _rows(conn, "select * from baselines where org_id = :o "
                                                 "order by key", o=org)]
        out["metric_history"] = [{"subject": name.get(r["subject_node_id"], r["subject_node_id"]),
                                  "metric": r["metric"], "value_bp": r["value_bp"],
                                  "unit": r["unit"], "observed_at": r["observed_at"],
                                  "reason": r["sample_reason"], "coverage_ready": r["coverage_ready"]}
                                 for r in _rows(conn, "select * from metric_history where org_id = :o "
                                                      "order by metric, subject_node_id", o=org)]
        out["cohort_membership"] = [f'{r["cohort_id"]}: {name.get(r["node_id"], r["node_id"])}'
                                    + ("" if r["left_at"] is None else " (left)")
                                    for r in _rows(conn, "select * from cohort_membership "
                                                         "where org_id = :o", o=org)]
        out["peer_baselines"] = [{k: r[k] for k in ("cohort_id", "metric", "p50_bp", "population")}
                                 for r in _rows(conn, "select * from peer_baselines where org_id = :o",
                                                o=org)]
        out["source_coverage"] = _rows(conn, "select domain, required, connected, freshness, "
                                             "coverage_ready, coverage_epoch from source_coverage "
                                             "where org_id = :o", o=org)
        out["coverage_epochs"] = _rows(conn, "select domain, epoch, coverage_ready, capabilities, "
                                             "opened_at, closed_at from coverage_epochs "
                                             "where org_id = :o", o=org)

        loops = _rows(conn, """select loop_id, subject_node_id, kind, thread_id, status,
                                 awaited_from_node_id, ask_count, opened_by_event, closed_by_event,
                                 closed_basis, opened_at, last_seen_at, closed_at
                            from open_loops where org_id = :o order by opened_at""", o=org)
        out["open_loops"] = [{"subject": name.get(lp["subject_node_id"], lp["subject_node_id"]),
                              "awaited_from": name.get(lp["awaited_from_node_id"],
                                                       lp["awaited_from_node_id"]),
                              "kind": lp["kind"], "status": lp["status"],
                              "ask_count": lp["ask_count"],
                              "opened_by": ev_obj.get(lp["opened_by_event"], lp["opened_by_event"]),
                              "opened_at": lp["opened_at"],
                              "age_days_at_last_sweep": (_days(now, lp["opened_at"])
                                                         if lp["opened_at"] else None),
                              "closed_by": ev_obj.get(lp["closed_by_event"], lp["closed_by_event"]),
                              "closed_basis": lp["closed_basis"]} for lp in loops]

        corr = _rows(conn, """select correlation_id, anchor_node_id, anchor_type, domain, generation,
                                status, event_count, first_event_at, last_event_at
                           from context_correlations where org_id = :o
                          order by first_event_at, correlation_id""", o=org)
        out["correlations"] = [{"anchor": name.get(c["anchor_node_id"], c["anchor_node_id"]),
                                "domain": c["domain"], "generation": c["generation"],
                                "status": c["status"], "events": c["event_count"],
                                "first": c["first_event_at"], "last": c["last_event_at"],
                                "quiet_days_at_last_sweep": (_days(now, c["last_event_at"])
                                                             if c["last_event_at"] else None)}
                               for c in corr]
        sits = _rows(conn, """select situation_id, situation_type, domain, status, anchor_node_id,
                                inputs, missing, coverage, first_seen_at, last_seen_at
                           from context_situations where org_id = :o
                          order by situation_type, situation_id""", o=org)
        admits = _rows(conn, """select situation_id, outcome, reasons
                                  from situation_admission_decisions where org_id = :o
                                 order by decided_at""", o=org)
        outcomes = _rows(conn, """select situation_id, outcome, reason
                                    from situation_outcomes where org_id = :o""", o=org)
        out["situations"] = []
        for s in sits:
            inputs = s["inputs"] if isinstance(s["inputs"], dict) else {}
            nums = {}

            def walk(prefix, v):
                if isinstance(v, dict):
                    for k, x in v.items():
                        walk(f"{prefix}.{k}" if prefix else str(k), x)
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    nums[prefix] = v
                elif isinstance(v, str) and len(v) < 60:
                    nums[prefix] = v
            walk("", inputs)
            out["situations"].append({
                "type": s["situation_type"], "domain": s["domain"], "status": s["status"],
                "anchor": name.get(s["anchor_node_id"], s["anchor_node_id"]),
                "coverage": s["coverage"], "missing": _trim(s["missing"], 200),
                "input_scalars": {k: v for k, v in list(nums.items())[:80]},
                "admission": [f'{a["outcome"]}:{a["reasons"]}' for a in admits
                              if a["situation_id"] == s["situation_id"]][-3:],
                "outcomes": [f'{o["outcome"]}:{o["reason"]}' for o in outcomes
                             if o["situation_id"] == s["situation_id"]]})

        sig = _rows(conn, """select rule_id, subject_node_id, status, situation_id, evidence,
                               score_inputs, level, do_nothing_consequence, uncertainty
                          from signals where org_id = :o order by created_at""", o=org)
        out["signals"] = [{"rule": s["rule_id"], "subject": name.get(s["subject_node_id"],
                                                                     s["subject_node_id"]),
                           "status": s["status"], "level": s["level"],
                           "evidence": _trim(s["evidence"], 600),
                           "score_inputs": _trim(s["score_inputs"], 300),
                           "do_nothing": s["do_nothing_consequence"]} for s in sig]

        cards = _rows(conn, """select card_id, state, headline, situation, why, why_now,
                                 business_subject, unresolved_item, do_nothing_consequence, artifact
                            from cards where org_id = :o order by created_at""", o=org)
        out["cards_db"] = []
        for c in cards:
            blob = " | ".join(str(x) for x in (c["headline"], c["situation"], _trim(c["why"], 3000),
                                               c["why_now"], c["unresolved_item"],
                                               c["do_nothing_consequence"],
                                               (c["artifact"] or {}).get("body")
                                               if isinstance(c["artifact"], dict) else None) if x)
            out["cards_db"].append({"card_id": c["card_id"], "state": c["state"],
                                    "headline": c["headline"], "subject": c["business_subject"],
                                    "time_phrases": sorted({m.group(0).lower()
                                                            for m in TIME_WORDS.finditer(blob)}),
                                    "time_sentences": [s.strip()[:220] for s in
                                                       re.split(r"(?<=[.!?|])\s+", blob)
                                                       if TIME_WORDS.search(s)][:8]})

        se = _rows(conn, """select event_id, object_type, outcome, occurred_at, actor, recipients,
                               source_object_id, parent_object_id, internal_kind, attention,
                               attention_reason, route, linkage_hints, domain_hints, source
                          from source_events where org_id = :o order by occurred_at""", o=org)
        out["source_events"] = []
        for s in se:
            actor = s["actor"] if isinstance(s["actor"], dict) else {}
            email = str(actor.get("email") or "").lower()
            out["source_events"].append({
                "obj": ev_obj.get(s["event_id"], s["event_id"]), "event_id": s["event_id"],
                "source": s["source"], "type": s["object_type"], "outcome": s["outcome"],
                "at": s["occurred_at"], "actor": email, "ours": email in founder,
                "recipients": s["recipients"], "thread": s["parent_object_id"],
                "kind": s["internal_kind"], "attention": f'{s["attention"]}/{s["attention_reason"]}',
                "route": s["route"], "linkage": _trim(s["linkage_hints"], 200)})

        qs = _rows(conn, """select event_id, signal_type, state, direction, thread_key, coverage,
                               ball_in_court, turn_index, coverage_ready
                          from qualified_signals where org_id = :o order by occurred_at""", o=org)
        out["qualified_signals"] = [{"obj": ev_obj.get(q["event_id"], q["event_id"]),
                                     "type": q["signal_type"], "state": q["state"],
                                     "direction": q["direction"], "thread": q["thread_key"],
                                     "coverage": q["coverage"], "coverage_ready": q["coverage_ready"],
                                     "ball": q["ball_in_court"]} for q in qs]

        # ---- the directed timeline, exactly as waiting.py reads it (no window: the case is short)
        tl_rows = _rows(conn, TIMELINE_SQL, o=org)
        per_node = {}
        for r in tl_rows:
            d = "out" if r["field"] == "thread.last_outbound" else "in"
            per_node.setdefault(r["node_id"], set()).add((d, r["at"], r["event_id"]))
        timelines = {}
        all_theirs, all_ours = [], []
        for node, items in per_node.items():
            tl = sorted(items, key=lambda x: (x[1], x[0]))
            theirs = _gaps(tl, "out", "in")
            ours = _gaps(tl, "in", "out")
            all_theirs += theirs
            all_ours += ours
            timelines[name.get(node, node)] = {
                "events": [f'{d} {at.isoformat()} {ev_obj.get(ev, ev)}' for d, at, ev in tl],
                "their_reply_days": theirs, "our_reply_days": ours}
        out["timeline"] = timelines
        out["their_reply_days_all"] = sorted(all_theirs)
        out["our_reply_days_all"] = sorted(all_ours)
        out["our_reply_median_days"] = median(all_ours) if all_ours else None

        # ---- our reply time straight from source_events, by thread: an inbound, then OUR next
        # outbound in the same thread (mail only)
        by_thread = {}
        for s in out["source_events"]:
            if s["source"] != "gmail" or not s["thread"]:
                continue
            by_thread.setdefault(s["thread"], []).append(s)
        thread_ours, thread_theirs = [], []
        for th, items in by_thread.items():
            items.sort(key=lambda x: x["at"])
            seq = [("out" if x["ours"] else "in", x["at"], x["obj"]) for x in items]
            thread_ours += [(th, g) for g in _gaps(seq, "in", "out")]
            thread_theirs += [(th, g) for g in _gaps(seq, "out", "in")]
        out["by_thread_our_reply_days"] = thread_ours
        out["by_thread_their_reply_days"] = thread_theirs
    return out


def main(ids):
    from genios_engine.api import routes
    engine = routes._graph.engine
    cases = {c.case_id: c for c in load_cases()}
    summary = []
    for cid in ids:
        case = cases[cid]
        org = f"{ORG_PREFIX}{case.case_id.lower()}"
        rec = {"case": cid, "group": GROUP.get(cid), "title": case.title, "case_kind": case.kind,
               "sweeps": [s.isoformat() for s in case.sweeps], "blocked_on": case.blocked_on,
               "objects": [{"id": o.object_id, "source": o.source, "at": o.occurred_at.isoformat(),
                            "from": o.sender, "to": list(o.to), "cc": list(o.cc),
                            "thread": o.thread, "subject": o.subject, "sweep": o.sweep}
                           for o in case.objects]}
        t0 = time.time()
        try:
            run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
            mark = judge(case, run)
            rec["verdict"], rec["lost_at"], rec["reason"] = mark.verdict, mark.lost_at, mark.reason
            rec["misses"] = list(run.misses)
            rec["chain_ok"] = list(run.chain_ok)
            rec["model_calls"] = len(run.model_calls)
            rec["landed"] = [f"{x.object_id}@{x.sweep}: {x.outcome}"
                             + (f" ({x.reason})" if x.reason else "") for x in run.landed]
            rec["cards_visible"] = [{"card_id": c.card_id, "state": c.state, "subject": c.subject,
                                     "sweeps": c.sweeps, "text": c.text[:1500]} for c in run.cards]
            rec.update(read_tenant(engine, org, case, run))
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
        summary.append({k: rec.get(k) for k in ("case", "group", "verdict", "lost_at", "error",
                                                 "misses", "tenant_removed", "seconds")})
        print(json.dumps(summary[-1], default=str), flush=True)
    with engine.connect() as conn:
        left = conn.execute(text("select id from orgs where id like :p"),
                            {"p": ORG_PREFIX + "%"}).scalars().all()
    (OUT / "_summary.json").write_text(json.dumps({"runs": summary, "golden_orgs_left": left},
                                                  indent=1, default=str))
    print("golden orgs left:", left, flush=True)


if __name__ == "__main__":
    wanted = sys.argv[1:] or sorted(GROUP)
    main(wanted)
