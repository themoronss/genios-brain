"""THE SECOND POPULATION — the one K1a's `urgency_bp` row and K1's below-floor row need.

`scripts/l4_pilot_seed.py` is and must stay the K1 population: 60 situations identical in every
input EXCEPT Layer 1's importance, which is what makes "importance is the only moving input"
measurable to the basis point. Every OTHER reading on it is a constant BY CONSTRUCTION, so
reporting `urgency_bp` or `core.confidence` as "a constant, therefore not met" off that tenant
measures the fixture, not the engine. Two of the L4 build record's three NOT-MET rows were read
off it.

This is the other tenant, driven through the same production entry points, built so that a
constant WOULD be a defect:

  * a real commitment carrying `due_text` -- the key the extraction contract actually carries
    (`context/qes_adapter` writes it; `due_at` is read by nothing, which is why the K1 seeder's
    canned extraction produced no commitment node at all and its urgency could only ever be 0) --
    spread across every rung of the U5 urgency ladder,
    including two rungs that must read as an ABSENCE (no commitment at all, and a commitment
    whose due text no reader can resolve);
  * a spread of evidence volume and CROSS-SOURCE corroboration, so L2's own confidence vector
    varies and the 4500 floor has something to be a floor OF.

    createdb l4_urgency && python scripts/l4_urgency_floor_pilot.py \\
        --database-url postgresql://.../l4_urgency

Then read the two rows off the tables:

    select output->'metrics'->>'urgency_bp', count(*) from reasoning_reasoner_results
     where org_id='org_gate_b' and reasoner_id='core.timeline' group by 1;
    select outcome_kind, count(*) from reasoning_run_outputs where org_id='org_gate_b' group by 1;
"""
from __future__ import annotations

import argparse, json, os, sys
from datetime import timedelta

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

QUOTE = "the quoted sentence"

# (label, due_text, expected ladder rung) -- due_text is the key the extraction contract
# actually carries (`qes_adapter` writes `due_text`); `due_at` is not read by anything.
DUE_CYCLE = [
    ("overdue",    "2026-08-17", 10_000),
    ("two_days",   "2026-08-21",  9_000),
    ("one_week",   "2026-08-26",  7_500),
    ("fortnight",  "2026-09-02",  6_000),
    ("month",      "2026-09-12",  4_000),
    ("quarter",    "2026-10-20",  2_000),
    ("beyond",     "2027-06-01",    500),
    ("undated",    None,              0),
    ("unreadable", "whenever you get a chance", None),
]

SOURCES = ("gmail", "slack", "crm")


def canned(person: str, company: str, due_text: str | None) -> dict:
    commitments = []
    if due_text is not None:
        commitments = [{"actor": "us", "action": "send the signed authorisation form",
                        "due_text": due_text,
                        "evidence_text": "send the signed authorisation form"}]
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
        "commitments": commitments,
        "questions": [],
        "observations": [{"kind": "next_step_agreed",
                          "evidence_text": "We said we would send it on Tuesday"}],
    }


CONTENT = ("{p} at {c} confirmed our filing was received and is under review. "
           "She asked us to send the signed authorisation form. "
           "We said we would send it on Tuesday.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--org", default="org_gate_b")
    ap.add_argument("--situations", type=int, default=54)
    args = ap.parse_args()
    os.environ["GENIOS_DATABASE_URL"] = args.database_url

    from sqlalchemy import text as sql
    from genios_engine.platform.migrate import apply_migrations
    apply_migrations(args.database_url)

    from genios_engine.context import situations
    from genios_engine.context.derived import (compute as compute_derived, compute_account_view,
                                               compute_deal_view)
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.context.pipeline import process_event
    from genios_engine.context.situation_bso import refresh_situation_importance
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.platform.l4_activation import activate, activated_features
    from genios_engine.reason.domain_shadow import shadow_compile
    from tests.test_admin_support_packs import NOW, _FakeLLM, _seed_event, _seed_org

    store = GraphStore(args.database_url)
    org, M = args.org, args.situations
    _seed_org(store, org)

    plan = {}
    committed = 0
    for i in range(M):
        person, company = f"Meera{i}", f"Northwind{i}"
        label, due_text, rung = DUE_CYCLE[i % len(DUE_CYCLE)]
        n_sources = 1 + (i // len(DUE_CYCLE)) % 3          # 1, 2, 3 -- cross-tool corroboration
        n_events = 1 + (i % 4)                              # 1..4   -- volume
        plan[company] = {"label": label, "rung": rung, "sources": n_sources, "events": n_events}
        for k in range(n_events):
            src = SOURCES[k % n_sources]
            eid = f"b_evt_{i}_{k}"
            with store.engine.begin() as conn:
                _seed_event(conn, org, eid, "admin")
            res = process_event(org_id=org, event_id=eid, source=src,
                                content=CONTENT.format(p=person, c=company),
                                sender_email=f"{person.lower()}@{company.lower()}.test",
                                occurred_at=NOW - timedelta(hours=i * 4 + k),
                                llm=_FakeLLM(canned(person, company, due_text)), store=store,
                                is_inbound=True, internal_emails=frozenset(),
                                domain_hints=[{"domain": "admin"}])
            committed += int(res.outcome == "committed")
    print(f"[seed] events committed={committed}")

    # THE PRODUCTION ORDER (context/runner.py:544-559): the derived roll-ups run BEFORE the
    # situation refresh, which is how a company node comes to carry its people's soonest open
    # `commitment.due_at` at all. `scripts/l4_pilot_seed.py` omits this step entirely.
    rows = (compute_derived(store, org, now=NOW) + compute_deal_view(store, org, now=NOW)
            + compute_account_view(store, org, now=NOW))
    print(f"[seed] derived rows={rows}")

    written = situations.refresh_situations(store, org, eval_time=NOW)
    print(f"[seed] situations={written}")

    with store.engine.begin() as conn:
        srows = conn.execute(sql(
            "select s.situation_id, s.correlation_id, m.event_id from context_situations s "
            "join context_correlation_members m on m.correlation_id = s.correlation_id "
            " and m.org_id = s.org_id where s.org_id=:o"), {"o": org}).all()
        seen, made = set(), 0
        for idx, r in enumerate(srows):
            if r.correlation_id in seen:
                continue
            seen.add(r.correlation_id)
            sig = f"sig_b_{org}_{idx}"
            refs = [{"source_ref": f"prepared_content:{r.event_id}", "quote": QUOTE,
                     "start_offset": 0, "end_offset": len(QUOTE), "verified": True,
                     "signal_id": sig}]
            conn.execute(sql(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                " extraction_ref, evidence_refs, importance_components, state, occurred_at) "
                "values (:s,:o,:e,:tr,'commitment_made',:i,'alg17-v1',:cf,"
                " cast('{\"scope\": \"org\"}' as jsonb), :x, cast(:refs as jsonb), "
                " cast(:comp as jsonb), 'active', :t) on conflict (signal_id) do nothing"),
                {"s": sig, "o": org, "e": r.event_id, "tr": f"tr_b_{org}_{idx}",
                 "i": 1500 + (idx * 137) % 7000, "cf": 5000 + (idx * 53) % 4000,
                 "x": f"ex_b_{org}_{idx}", "refs": json.dumps(refs),
                 "comp": json.dumps({"base_bp": 4000}), "t": NOW - timedelta(hours=idx)})
            made += 1
    print(f"[seed] qualified_signals written={made}")

    ranked = refresh_situation_importance(store, org, eval_time=NOW)
    print(f"[seed] ranked={ranked}")

    activate(store.engine, org, feature="roster_v2", by="gate_b")
    activate(store.engine, org, feature="ranking_v2", by="gate_b")
    print(f"[activate] {sorted(activated_features(store.engine, org))}")

    registry = make_registry(args.database_url)
    ensure_defaults(registry, org)
    counts = dict(shadow_compile(store=store, org_id=org, eval_time=NOW, live=True,
                                 registry=registry, limit=500))
    print(f"[compile] {json.dumps(counts, default=str, sort_keys=True)}")
    print(f"[plan] {json.dumps(plan, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
