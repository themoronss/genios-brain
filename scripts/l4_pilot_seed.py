"""K1, measured on a population built through the production path.

M admin situations, each on its own company, each carrying an L1 `qualified_signals` row with a
REAL alg17 importance and a coherent verified evidence span -- so L2's admission gate admits them
on their merits, L2 composes importance from L1's score (G7 -> H5), and Layer 4 ranks with it.
Nothing here recomputes a utility: the report reads the rows the reasoning path wrote.
"""
from __future__ import annotations

import argparse, json, os, sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/Users/harshtripathi/Desktop/geniosfull/genios-brain")

QUOTE = "the quoted sentence"

CONTENT = ("{p} at {c} confirmed our filing was received and is under review. "
           "She asked us to send the signed authorisation form by 27 August. "
           "We said we would send it on Tuesday.")


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
    ap.add_argument("--org", default="org_k1_pilot")
    ap.add_argument("--situations", type=int, default=60)
    ap.add_argument("--ranking-v2", default="1")
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
    from genios_engine.platform.l4_activation import activate, activated_features
    from genios_engine.reason.domain_shadow import shadow_compile
    from tests.test_admin_support_packs import NOW, _FakeLLM, _seed_event, _seed_org

    store = GraphStore(args.database_url)
    org, M = args.org, args.situations
    _seed_org(store, org)

    committed = 0
    for i in range(M):
        person, company = f"Meera{i}", f"Northwind{i}"
        eid = f"adm_evt_{i}"
        with store.engine.begin() as conn:
            _seed_event(conn, org, eid, "admin")
        res = process_event(org_id=org, event_id=eid, source="gmail",
                            content=CONTENT.format(p=person, c=company),
                            sender_email=f"{person.lower()}@{company.lower()}.test",
                            occurred_at=NOW - timedelta(hours=i),
                            llm=_FakeLLM(canned(person, company)), store=store,
                            is_inbound=True, internal_emails=frozenset(),
                            domain_hints=[{"domain": "admin"}])
        committed += int(res.outcome == "committed")
    print(f"[seed] events committed={committed}/{M}")

    written = situations.refresh_situations(store, org, eval_time=NOW)
    print(f"[seed] situations={written}")

    # L1's supply, attached to each situation's own correlation members. importance_bp is spread
    # wide and non-repeating so the ranker has a real distribution to read, exactly as
    # `_seed_h5_org` spreads it for H5.
    with store.engine.begin() as conn:
        rows = conn.execute(sql(
            "select s.situation_id, s.correlation_id, m.event_id from context_situations s "
            "join context_correlation_members m on m.correlation_id = s.correlation_id "
            " and m.org_id = s.org_id where s.org_id=:o"), {"o": org}).all()
        seen: set[str] = set()
        made = 0
        for idx, r in enumerate(rows):
            if r.correlation_id in seen:
                continue
            seen.add(r.correlation_id)
            sig = f"sig_k1_{idx}"
            refs = [{"source_ref": f"prepared_content:{r.event_id}", "quote": QUOTE,
                     "start_offset": 0, "end_offset": len(QUOTE), "verified": True,
                     "signal_id": sig}]
            conn.execute(sql(
                "insert into qualified_signals (signal_id, org_id, event_id, trace_id, "
                " signal_type, importance_bp, importance_version, confidence_bp, visibility, "
                " extraction_ref, evidence_refs, importance_components, state, occurred_at) "
                "values (:s,:o,:e,:tr,'commitment_made',:i,'alg17-v1',:cf,"
                " cast('{\"scope\": \"org\"}' as jsonb), :x, cast(:refs as jsonb), "
                " cast(:comp as jsonb), 'active', :t)"),
                {"s": sig, "o": org, "e": r.event_id, "tr": f"tr_k1_{idx}",
                 "i": 1500 + (idx * 137) % 7000, "cf": 5000 + (idx * 53) % 4000,
                 "x": f"ex_k1_{idx}", "refs": json.dumps(refs),
                 "comp": json.dumps({"base_bp": 4000}), "t": NOW - timedelta(hours=idx)})
            made += 1
    print(f"[seed] qualified_signals written={made}")

    ranked = refresh_situation_importance(store, org, eval_time=NOW)
    with store.engine.connect() as conn:
        imp = conn.execute(sql("select importance_bp from context_situations where org_id=:o"),
                           {"o": org}).scalars().all()
    print(f"[seed] ranked={ranked} distinct importance_bp={len(set(imp))} of {len(imp)}")

    activate(store.engine, org, feature="roster_v2", by="k1_gate")
    if args.ranking_v2 == "1":
        activate(store.engine, org, feature="ranking_v2", by="k1_gate")
    print(f"[activate] {sorted(activated_features(store.engine, org))}")

    registry = make_registry(args.database_url)
    ensure_defaults(registry, org)
    counts = dict(shadow_compile(store=store, org_id=org, eval_time=NOW, live=True,
                                 registry=registry, limit=500))
    print(f"[compile] {json.dumps(counts, default=str, sort_keys=True)}")

    from scripts.ranking_distribution import _CANDIDATES, _OUTPUTS, measure
    with store.engine.connect() as conn:
        conn.execute(sql("set transaction read only"))
        cands = [dict(r) for r in conn.execute(
            sql(_CANDIDATES), {"org": org, "since": NOW - timedelta(days=7),
                               "lim": 100000}).mappings()]
        outs = [dict(r) for r in conn.execute(
            sql(_OUTPUTS), {"org": org, "since": NOW - timedelta(days=7),
                            "lim": 100000}).mappings()]
    print(f"[rows] candidates={len(cands)} outputs={len(outs)}")
    rep = measure(cands, outs, org_id=org, since=NOW - timedelta(days=7),
                  until=NOW + timedelta(minutes=1))
    d = rep.as_dict()
    print("[K1]", json.dumps(d, default=str, indent=2, sort_keys=True))
    if args.json_out:
        import pathlib
        pathlib.Path(args.json_out).write_text(json.dumps(
            {"compile": counts, "k1": d}, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
