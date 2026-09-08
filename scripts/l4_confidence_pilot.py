"""The confidence distribution on the compiled lane, MEASURED on a varied population.

A floor nothing trips is decoration and a floor everything trips is an outage, and only the
numbers say which one was built. `l4_pilot_seed.py` answers the RANKING question and deliberately
seeds sixty situations that are identical in everything except importance — one event, from one
source, each. That is the right population for K1 and the wrong one for this question: every one
of those situations is the thinnest evidence a situation can have, so a confidence that reads
Layer 2's own trust axes correctly must put all sixty in the same place, and a run that did would
prove nothing about whether the floor DISCRIMINATES.

So this seeds the same admin situations through the same production path — `process_event` ->
`refresh_situations` -> `qualified_signals` -> `refresh_situation_importance` -> `shadow_compile`
-> the real `DecisionMaker` — and varies the one thing that population holds constant: HOW MUCH
independent material backs each situation. `situations.evidence_score` scores volume out of 40 and
distinct sources out of 60, so a grid of (events x distinct sources) walks the evidence axis from
33 to 100 without inventing a number anywhere: every confidence reported below was computed by
`core.confidence` inside a real run and read back off `reasoning_run_outputs`.

    python scripts/l4_confidence_pilot.py --database-url postgresql://.../scratch_db

Deterministic: a fixed grid, a fixed clock, no network beyond the database.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import timedelta

sys.path.insert(0, "/Users/harshtripathi/Desktop/geniosfull/genios-brain")

QUOTE = "the quoted sentence"

CONTENT = ("{p} at {c} confirmed our filing was received and is under review. "
           "She asked us to send the signed authorisation form by 27 August. "
           "We said we would send it on Tuesday.")

#: The grid, as (messages, distinct systems). `evidence_score` = min(40, events*8) +
#: min(60, sources*25), so these seven cells land the evidence axis on 33 / 41 / 49 / 57 / 58 /
#: 66 / 100 — two of them below the 4500 bp lane floor and five above it, with four distinct
#: readings in between. Chosen to STRADDLE the floor rather than to clear it: a population seeded
#: entirely on one side of a threshold cannot tell you the threshold works, and one seeded entirely
#: on the other side tells you only that it fires.
GRID = ((1, 1), (2, 1), (3, 1), (4, 1), (1, 2), (2, 2), (5, 4))

SOURCES = ("gmail", "slack", "crm", "calendar")


def canned(person: str, company: str) -> dict:
    return {
        "relevance": 0.9, "noise_type": "none", "domains": ["admin"],
        "entity_mentions": [
            {"type": "person", "name": person, "email": f"{person.lower()}@{company.lower()}.test",
             "evidence_text": f"{person} at {company}"},
            {"type": "company", "name": company, "email": None,
             "evidence_text": f"at {company}"}],
        "fact_candidates": [
            {"subject": person, "field": "thread.ball_in_court", "value": "us",
             "evidence_text": "asked us to send the signed authorisation form"}],
        "commitments": [
            {"actor": "us", "action": "send the signed authorisation form",
             "due_at": "2026-08-27",
             "evidence_text": "send the signed authorisation form by 27 August"}],
        "questions": [],
        "observations": [{"kind": "next_step_agreed",
                          "evidence_text": "We said we would send it on Tuesday"}],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--org", default="org_conf_pilot")
    ap.add_argument("--situations", type=int, default=60)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    os.environ["GENIOS_DATABASE_URL"] = args.database_url

    from sqlalchemy import text as sql
    from genios_engine.platform.migrate import apply_migrations
    apply_migrations(args.database_url)

    from genios_engine.context import situations
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.pipeline import process_event
    from genios_engine.context.situation_bso import refresh_situation_importance
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.platform.l4_activation import activate
    from genios_engine.reason.decision_maker import (DEFAULT_CONFIDENCE_FLOOR_BP,
                                                     resolve_confidence_floor)
    from genios_engine.reason.domain_shadow import shadow_compile
    from tests.test_admin_support_packs import NOW, _FakeLLM, _seed_event, _seed_org

    store = GraphStore(args.database_url)
    org, M = args.org, args.situations
    _seed_org(store, org)

    # One correlation per person/company, `events` messages inside it, spread over `sources`
    # distinct systems. Same content, same extraction — the ONLY thing that varies is how much
    # independent material backs the situation, which is exactly what the evidence axis measures.
    committed = 0
    for index in range(M):
        events, sources = GRID[index % len(GRID)]
        person, company = f"Meera{index}", f"Northwind{index}"
        for step in range(events):
            eid = f"conf_evt_{index}_{step}"
            source = SOURCES[step % sources]
            with store.engine.begin() as conn:
                # `_seed_event` hard-codes `gmail`; the distinct-source count that
                # `evidence_score` reads comes off `source_events.source`, so the row is restamped
                # here rather than by widening a helper this script does not own.
                _seed_event(conn, org, eid, "admin")
                conn.execute(sql("update source_events set source=:s "
                                 "where org_id=:o and event_id=:e"),
                             {"s": source, "o": org, "e": eid})
            res = process_event(org_id=org, event_id=eid, source=source,
                                content=CONTENT.format(p=person, c=company),
                                sender_email=f"{person.lower()}@{company.lower()}.test",
                                occurred_at=NOW - timedelta(hours=index, minutes=step),
                                llm=_FakeLLM(canned(person, company)), store=store,
                                is_inbound=True, internal_emails=frozenset(),
                                domain_hints=[{"domain": "admin"}])
            committed += int(res.outcome == "committed")
    print(f"[seed] events committed={committed}")

    written = situations.refresh_situations(store, org, eval_time=NOW)
    print(f"[seed] situations={written}")

    with store.engine.begin() as conn:
        rows = conn.execute(sql(
            "select s.situation_id, s.correlation_id, m.event_id from context_situations s "
            "join context_correlation_members m on m.correlation_id = s.correlation_id "
            " and m.org_id = s.org_id where s.org_id=:o"), {"o": org}).all()
        seen: set[str] = set()
        made = 0
        for idx, row in enumerate(rows):
            if row.correlation_id in seen:
                continue
            seen.add(row.correlation_id)
            sig = f"sig_conf_{idx}"
            refs = [{"source_ref": f"prepared_content:{row.event_id}", "quote": QUOTE,
                     "start_offset": 0, "end_offset": len(QUOTE), "verified": True,
                     "signal_id": sig}]
            conn.execute(sql(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                " extraction_ref, evidence_refs, importance_components, state, occurred_at) "
                "values (:s,:o,:e,:tr,'commitment_made',:i,'alg17-v1',:cf,"
                " cast('{\"scope\": \"org\"}' as jsonb), :x, cast(:refs as jsonb), "
                " cast(:comp as jsonb), 'active', :t)"),
                {"s": sig, "o": org, "e": row.event_id, "tr": f"tr_conf_{idx}",
                 "i": 1500 + (idx * 137) % 7000, "cf": 5000 + (idx * 53) % 4000,
                 "x": f"ex_conf_{idx}", "refs": json.dumps(refs),
                 "comp": json.dumps({"base_bp": 4000}), "t": NOW - timedelta(hours=idx)})
            made += 1
    print(f"[seed] qualified_signals written={made}")

    refresh_situation_importance(store, org, eval_time=NOW)
    with store.engine.connect() as conn:
        axes = Counter(tuple(r) for r in conn.execute(sql(
            "select confidence_evidence, confidence_freshness, confidence_consistency, "
            "       confidence_identity, coverage, confidence_analytic "
            "from context_situations where org_id=:o"), {"o": org}))
    print("[L2 axes] evidence/freshness/consistency/identity/coverage/analytic -> situations")
    for row, count in sorted(axes.items()):
        print(f"          {row} -> {count}")

    activate(store.engine, org, feature="roster_v2", by="confidence_gate")
    activate(store.engine, org, feature="ranking_v2", by="confidence_gate")
    registry = make_registry(args.database_url)
    ensure_defaults(registry, org)
    counts = dict(shadow_compile(store=store, org_id=org, eval_time=NOW, live=True,
                                 registry=registry, limit=500))
    print(f"[compile] {json.dumps(counts, default=str, sort_keys=True)}")

    with store.engine.connect() as conn:
        conn.execute(sql("set transaction read only"))
        outputs = [dict(r) for r in conn.execute(sql(
            "select confidence_bp, outcome_kind from reasoning_run_outputs where org_id=:o"),
            {"o": org}).mappings()]
    floor_bp = DEFAULT_CONFIDENCE_FLOOR_BP
    confidences = sorted(item["confidence_bp"] for item in outputs)
    below = [value for value in confidences if value < floor_bp]
    deferred = [item for item in outputs if item["outcome_kind"] == "defer"]
    report = {
        "org_id": org,
        "decisions_measured": len(outputs),
        "floor_bp": floor_bp,
        "distinct_confidence_values": len(set(confidences)),
        "confidence_histogram": dict(sorted(Counter(confidences).items())),
        "min_confidence_bp": min(confidences) if confidences else None,
        "max_confidence_bp": max(confidences) if confidences else None,
        "spread_bp": (max(confidences) - min(confidences)) if confidences else None,
        "below_floor": len(below),
        "below_floor_fraction_bp": (len(below) * 10_000 // len(confidences)
                                    if confidences else None),
        "deferred": len(deferred),
        "outcomes": dict(sorted(Counter(item["outcome_kind"] for item in outputs).items())),
    }
    print("[confidence]", json.dumps(report, indent=2, sort_keys=True))
    # The two failure modes this script exists to tell apart, stated rather than left to a reader.
    if not below:
        print("[verdict] FLOOR NEVER TRIPS — decoration, not a floor (Law 3).")
    elif len(below) == len(confidences):
        print("[verdict] FLOOR TRIPS ON EVERYTHING — an outage, not silence.")
    else:
        print(f"[verdict] the floor DISCRIMINATES: {len(below)} of {len(confidences)} below "
              f"{floor_bp} bp.")
    if args.json_out:
        import pathlib
        pathlib.Path(args.json_out).write_text(json.dumps(
            {"compile": counts, "confidence": report}, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
