"""L3 composite composer (C3) — the PROACTIVE twin of the on-demand query synthesis.

The per-node rule engine emits one signal per concern. A deal in real trouble trips several at once
(unanswered_email + objection_open + competitor_in_live_deal). Listing them as three disconnected
alerts buries the story. This post-pass clusters OPEN single-rule signals by deal (deal node + its
1-hop neighbourhood over graph_edges) and, when a deal carries ≥2 DISTINCT concerns, emits ONE
composite `deal_health` signal on the deal. L5 then renders it into a single "deal at risk: X + Y + Z"
card that surfaces in the insights feed unprompted — no LLM here (the card's E1 render composes the
verdict from the member reason_codes, exactly as the query layer does on demand).
"""
from __future__ import annotations

import json

from sqlalchemy import text

from genios_engine.platform.ids import new_id

COMPOSITE_RULE_ID = "deal_health"
COMPOSITE_REASON = "deal_health"
COMPOSITE_PLAY = "review_deal"


def _adjacency(c, org_id: str) -> dict:
    adj: dict = {}
    # NB: do NOT alias to_node_id as `t` — Row.t is a reserved SQLAlchemy attribute and shadows it.
    for r in c.execute(text("select from_node_id, to_node_id from graph_edges "
                            "where org_id=:o and valid_to is null"), {"o": org_id}):
        adj.setdefault(r.from_node_id, set()).add(r.to_node_id)
        adj.setdefault(r.to_node_id, set()).add(r.from_node_id)
    return adj


def plan_composites(deal_ids, signals, adj: dict):
    """Pure clustering (no IO) — for each deal, gather OPEN signals on the deal + its 1-hop
    neighbours; a deal with ≥2 signals across ≥2 DISTINCT reason_codes yields one composite plan
    {deal_id, score, codes, evidence, inputs}. Kept separate from the DB writes so it's unit-tested.

    `signals` are objects/dicts with .subject_node_id/.reason_code/.score/.score_inputs. `adj` maps
    node_id → set(neighbour ids)."""
    def _g(s, k):
        return s.get(k) if isinstance(s, dict) else getattr(s, k)

    by_subject: dict = {}
    for s in signals:
        by_subject.setdefault(_g(s, "subject_node_id"), []).append(s)

    plans = []
    for deal_id in deal_ids:
        cluster = {deal_id} | set(adj.get(deal_id, set()))
        members = [s for nid in cluster for s in by_subject.get(nid, [])]
        members.sort(key=lambda m: float(_g(m, "score") or 0), reverse=True)  # strongest driver first
        codes: list = []
        for m in members:                       # distinct reason_codes in score-desc order
            rc = _g(m, "reason_code")
            if rc not in codes:
                codes.append(rc)
        if len(members) < 2 or len(codes) < 2:
            continue
        top = members[0]
        inputs = _g(top, "score_inputs")
        inputs = inputs if isinstance(inputs, dict) else json.loads(inputs or "{}")
        plans.append({
            "deal_id": deal_id,
            "score": int(round(float(_g(top, "score") or 0))),
            "codes": codes,
            "evidence": [{"field": "signal", "value": rc} for rc in codes],
            "inputs": {**inputs, "composite_of": codes},
        })
    return plans


def compose_deal_health(store, org_id: str, eval_time, snapshot_id, adj: dict | None = None,
                        fired: set | None = None) -> dict:
    """Emit/refresh composite deal_health signals. Returns {'emitted': n, 'active': {deal_node_id,…}}
    where `active` is every deal that still qualifies — the runner adds these to its `fired` set so
    the lifecycle sweep doesn't resolve a composite that's still true.

    `fired` (from the runner: the {(rule_id, node_id)} that fired THIS run) filters the member set to
    currently-firing signals, so a stale still-open signal whose rule stopped firing — not yet closed
    by the same-run lifecycle sweep — doesn't get folded into a fresh verdict."""
    with store.engine.connect() as c:
        deals = c.execute(text(
            "select node_id, display_name from graph_nodes where org_id=:o "
            "and node_type='deal' and valid_to is null"), {"o": org_id}).fetchall()
        if not deals:
            return {"emitted": 0, "active": set()}
        sigs = c.execute(text(
            "select signal_id, rule_id, reason_code, subject_node_id, score, score_inputs, level "
            "from signals where org_id=:o and status='open' and rule_id <> :rc"),
            {"o": org_id, "rc": COMPOSITE_RULE_ID}).fetchall()
        if adj is None:
            adj = _adjacency(c, org_id)

    if fired is not None:      # keep only signals whose rule actually fired this run (not stale-open)
        sigs = [s for s in sigs if (s.rule_id, s.subject_node_id) in fired]

    plans = plan_composites([d.node_id for d in deals], sigs, adj)

    # existing open composites → so we can leave a still-accurate one alone but RESOLVE + re-emit one
    # whose member set has changed (evidence is stamped at emit time and never mutated in place).
    with store.engine.connect() as c:
        existing = {r.subject_node_id: (r.signal_id, r.evidence) for r in c.execute(text(
            "select signal_id, subject_node_id, evidence from signals where org_id=:o "
            "and status='open' and rule_id=:rc"), {"o": org_id, "rc": COMPOSITE_RULE_ID})}

    def _codes(ev):
        ev = ev if isinstance(ev, list) else (json.loads(ev) if ev else [])
        return [e.get("value") for e in ev]

    emitted = 0
    active: set = {p["deal_id"] for p in plans}
    for p in plans:
        prev = existing.get(p["deal_id"])
        if prev and _codes(prev[1]) == p["codes"]:
            continue                                    # unchanged → leave the open composite as-is
        with store.engine.begin() as c:
            if prev:                                    # member set changed → resolve the stale one
                c.execute(text("update signals set status='resolved' where signal_id=:id"),
                          {"id": prev[0]})
            row = c.execute(text(
                "insert into signals (signal_id, org_id, rule_id, rule_version, level, "
                "subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
                "config_snapshot_id) "
                "values (:id,:o,:r,:v,:lv,:n,:s,cast(:si as jsonb),:rc,cast(:ev as jsonb),:p,:et,:cs) "
                "on conflict (org_id, rule_id, subject_node_id) where status='open' do nothing "
                "returning signal_id"),
                {"id": new_id("sig"), "o": org_id, "r": COMPOSITE_RULE_ID, "v": 1, "lv": "prescriptive",
                 "n": p["deal_id"], "s": p["score"], "si": json.dumps(p["inputs"], default=str),
                 "rc": COMPOSITE_REASON, "ev": json.dumps(p["evidence"], default=str),
                 "p": COMPOSITE_PLAY, "et": eval_time, "cs": snapshot_id}).first()
        if row:
            emitted += 1
    return {"emitted": emitted, "active": active}
