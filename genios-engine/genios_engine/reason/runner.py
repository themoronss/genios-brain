from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore
from genios_engine.packs.registry import PackRegistry
from genios_engine.packs.wiring import DEFAULT_PACK_ID, ensure_default, make_registry
from genios_engine.platform.ids import new_id

from .baselines import build_baselines, load_node_metrics
from .composer import COMPOSITE_RULE_ID as _COMPOSITE_RULE_ID
from .composer import compose_deal_health
from .engine import NodeContext, evaluate, score_rule
from .rules import rule_from_dict, rules_for_scope
from .signals_derived import sentiment_facts

# cross-entity condition keys — presence in ANY effective rule means we must load neighbourhoods.
_CROSS_ENTITY_KEYS = {"neighbor_has_obs", "neighbor_no_obs", "neighbor_fact"}


def _rules_need_neighbors(rules) -> bool:
    for r in rules:
        for c in r.when:
            if c.get("fn") == "edge_count" or _CROSS_ENTITY_KEYS & set(c.keys()):
                return True
    return False

# L3 runner — wake over the graph, evaluate the tenant's EFFECTIVE pack rules, score with the
# pack's scoring config, gate, emit signal.v1 (or log a reason-coded suppression). No domain
# constant lives here: rules, weights, gate thresholds and budget all come from L4's effective
# config, and every emitted signal is stamped with the config_snapshot_id it was scored under.


def _load_context(store, org_id, node_id, node_type) -> NodeContext:
    with store.engine.connect() as c:
        facts = {}
        for r in c.execute(text(
                "select f.field, f.value, f.confidence, f.authority_rank, f.occurred_at, "
                "  (select count(distinct sr.source) from graph_source_refs sr "
                "   join graph_facts fv on fv.fact_version_id=sr.fact_version_id and fv.org_id=f.org_id "
                "   where fv.fact_id=f.fact_id) as src_count "
                "from graph_facts f "
                "where f.org_id=:o and f.subject_node_id=:n and f.valid_to is null and f.status='active'"),
                {"o": org_id, "n": node_id}):
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            facts[r.field] = {"value": v, "confidence": float(r.confidence),
                              "authority_rank": r.authority_rank, "occurred_at": r.occurred_at,
                              "src_count": int(r.src_count or 1)}
        obs = [{"kind": r.kind, "occurred_at": r.occurred_at} for r in c.execute(text(
            "select kind, occurred_at from graph_observations "
            "where org_id=:o and subject_node_id=:n and status='active'"),
            {"o": org_id, "n": node_id})]
    return NodeContext(node_id=node_id, node_type=node_type, facts=facts, obs=obs)


def _neighbor_index(store, org_id):
    """Bulk-load the org's edge/obs/fact structure ONCE (3 org-wide queries) → adjacency + per-node
    obs-kinds + per-node latest-facts. The runner scans every node, so this O(1)-query index beats
    N×2 per-node round-trips against a networked pooler. Built only when a rule needs neighbours."""
    adj: dict = {}          # node_id -> set(neighbour ids)
    obs_idx: dict = {}      # node_id -> set(observation kinds)
    fact_idx: dict = {}     # node_id -> {field: latest value}
    with store.engine.connect() as c:
        # NB: do NOT alias to_node_id as `t` — Row.t is a reserved SQLAlchemy attribute and shadows it.
        for r in c.execute(text("select from_node_id, to_node_id from graph_edges "
                                "where org_id=:o and valid_to is null"), {"o": org_id}):
            adj.setdefault(r.from_node_id, set()).add(r.to_node_id)
            adj.setdefault(r.to_node_id, set()).add(r.from_node_id)
        for r in c.execute(text("select subject_node_id nid, kind from graph_observations "
                                "where org_id=:o and status='active'"), {"o": org_id}):
            obs_idx.setdefault(r.nid, set()).add(r.kind)
        for r in c.execute(text("select subject_node_id nid, field, value, occurred_at from graph_facts "
                                "where org_id=:o and valid_to is null and status='active' "
                                "order by occurred_at desc nulls last"), {"o": org_id}):
            d = fact_idx.setdefault(r.nid, {})
            if r.field in d:                           # ordered desc → first seen is the latest
                continue
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            d[r.field] = (v, r.occurred_at)            # keep occurred_at → latest-across-neighbours
    return adj, obs_idx, fact_idx


def _neighborhood(node_id, adj, obs_idx, fact_idx):
    """Per-node 1-hop neighbourhood from the bulk index → (edge_count, neighbor_obs, neighbor_facts).
    neighbor_facts holds the LATEST value per field ACROSS all neighbours (by occurred_at), so the
    result is deterministic — not whichever neighbour set-iteration happened to visit first."""
    nbrs = adj.get(node_id, set())
    neighbor_obs: set = set()
    best: dict = {}          # field -> (value, occurred_at)
    for n in nbrs:
        neighbor_obs |= obs_idx.get(n, set())
        for f, (v, ts) in fact_idx.get(n, {}).items():
            cur = best.get(f)
            # prefer the newer occurred_at; a dated fact beats an undated one; ties keep the first.
            if cur is None or (ts is not None and (cur[1] is None or ts > cur[1])):
                best[f] = (v, ts)
    neighbor_facts = {f: v for f, (v, _ts) in best.items()}
    return len(nbrs), neighbor_obs, neighbor_facts


def _recent_signal(store, org_id, rule_id, node_id, cooldown_hours, eval_time) -> bool:
    with store.engine.connect() as c:
        return c.execute(text(
            "select 1 from signals where org_id=:o and rule_id=:r and subject_node_id=:n "
            "and created_at > :since limit 1"),
            {"o": org_id, "r": rule_id, "n": node_id,
             "since": eval_time - timedelta(hours=cooldown_hours)}).first() is not None


def _budget_used(store, org_id, eval_time) -> int:
    with store.engine.connect() as c:
        return c.execute(text("select count(*) from signals where org_id=:o "
                              "and created_at::date = :d"),
                         {"o": org_id, "d": eval_time.date()}).scalar()


def _active_seats(store, org_id) -> int:
    """Active seats for the org (≥1). The daily budget scales with seats so a multi-seat team
    isn't capped at one seat's worth — the spec's 'per user, never per tenant'."""
    with store.engine.connect() as c:
        n = c.execute(text("select count(*) from org_seats where org_id=:o and active"),
                      {"o": org_id}).scalar()
    return max(1, int(n or 0))


def _suppress(store, org_id, rule_id, node_id, reason, eval_time, detail=None) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into signal_suppression_log (org_id, rule_id, subject_node_id, "
            "reason_code, detail, eval_time) values (:o,:r,:n,:rc,cast(:d as jsonb),:e)"),
            {"o": org_id, "r": rule_id, "n": node_id, "rc": reason,
             "d": json.dumps(detail or {}, default=str), "e": eval_time})


def _emit(store, org_id, rule, node_id, S, inputs, evidence, eval_time, snapshot_id) -> str | None:
    """Emit signal.v1. ON CONFLICT DO NOTHING against the partial-unique index (one OPEN signal
    per org/rule/node) → a concurrent run that already emitted this signal makes us a no-op
    instead of a duplicate. Returns the id, or None if a concurrent run beat us to it."""
    sid = new_id("sig")
    with store.engine.begin() as c:
        row = c.execute(text(
            "insert into signals (signal_id, org_id, rule_id, rule_version, level, "
            "subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
            "config_snapshot_id) "
            "values (:id,:o,:r,:v,:lv,:n,:s,cast(:si as jsonb),:rc,cast(:ev as jsonb),:p,:et,:cs) "
            "on conflict (org_id, rule_id, subject_node_id) where status='open' do nothing "
            "returning signal_id"),
            {"id": sid, "o": org_id, "r": rule.id, "v": rule.version, "lv": rule.level,
             "n": node_id, "s": S, "si": json.dumps(inputs, default=str),
             "rc": rule.reason_code, "ev": json.dumps(evidence, default=str),
             "p": rule.play, "et": eval_time, "cs": snapshot_id}).first()
    return row.signal_id if row else None


def _tenant_deal_p90(store, org_id: str, min_deals: int = 5) -> float | None:
    """The org's OWN deal-value P90 (was a static 50000 pack default). Only once there are enough
    deals to be meaningful, else keep the pack default — so impact scaling reflects THIS tenant."""
    vals = []
    with store.engine.connect() as c:
        for r in c.execute(text("select value from graph_facts where org_id=:o and "
                                "field='deal.value' and valid_to is null and status='active'"),
                           {"o": org_id}):
            try:
                vals.append(float(str(r.value).strip('"')))
            except (ValueError, TypeError):
                pass
    if len(vals) < min_deals:
        return None
    import math
    vals.sort()
    return round(vals[min(len(vals) - 1, int(math.ceil(0.9 * len(vals)) - 1))], 2)


def run(*, org_id: str, store: GraphStore, eval_time: datetime | None = None,
        registry: PackRegistry | None = None, pack_id: str = DEFAULT_PACK_ID) -> dict:
    eval_time = eval_time or datetime.now(timezone.utc)

    # L4 — resolve the tenant's effective config (rules + scoring + gate + budget + snapshot id).
    registry = registry or make_registry()
    ensure_default(registry, org_id)                       # design-partner default: sales.v1
    effective, snapshot_id = registry.effective(org_id, pack_id)
    if effective is None:                                  # no pack applied → L3 does nothing
        return {"nodes": 0, "outcomes": {}, "eval_time": eval_time.isoformat(),
                "pack": None}

    scoring_cfg = effective["scoring"]
    _p90 = _tenant_deal_p90(store, org_id)                  # learn deal-value P90 from THIS tenant
    if _p90:
        scoring_cfg = {**scoring_cfg,
                       "impact": {**scoring_cfg.get("impact", {}), "p90_default": _p90}}
    gate = scoring_cfg.get("gate", {})
    gate_s = int(gate.get("s_min", 55))
    gate_c = int(gate.get("c_min", 60))
    rule_offsets = scoring_cfg.get("rule_offsets", {})     # L6 learned per-rule gate nudges
    budget_per_day = int(scoring_cfg.get("budget_per_user_day", 7))
    all_rules = [rule_from_dict(r) for r in effective["rules"]]

    build_baselines(store, org_id, eval_time)              # C9: refresh baselines (+C1 momentum/engagement)
    need_neighbors = _rules_need_neighbors(all_rules)      # C1: only pay neighbourhood cost if a rule uses it
    nbr_adj = nbr_obs_idx = nbr_fact_idx = None
    if need_neighbors:
        nbr_adj, nbr_obs_idx, nbr_fact_idx = _neighbor_index(store, org_id)   # 3 queries for the whole org
    from genios_engine.feedback.calibrate import muted_rules
    muted = muted_rules(store, org_id)                     # L6 F5: skip auto-muted (harmful) rules
    out: Counter = Counter()
    fired: set[tuple[str, str]] = set()
    candidates: list = []                                  # gated signals, ranked before spending
    with store.engine.connect() as c:
        nodes = c.execute(text("select node_id, node_type from graph_nodes "
                               "where org_id=:o and valid_to is null"), {"o": org_id}).fetchall()
    for nd in nodes:
        rules = rules_for_scope(all_rules, nd.node_type)
        if not rules:
            continue
        ctx = _load_context(store, org_id, nd.node_id, nd.node_type)
        baselines, derived = load_node_metrics(store, org_id, nd.node_id)  # C1: one query, both
        ctx.baselines = baselines
        ctx.facts.update(derived)                          # derived.momentum / derived.engagement
        ctx.facts.update(sentiment_facts(ctx.obs))         # derived.sentiment / obs_pos / obs_neg
        if need_neighbors:
            ctx.edge_count, ctx.neighbor_obs, ctx.neighbor_facts = \
                _neighborhood(nd.node_id, nbr_adj, nbr_obs_idx, nbr_fact_idx)
        for rule in rules:
            if rule.id in muted:                          # L6 auto-mute — rule is harmful, silence it
                out["muted"] += 1
                continue
            if not evaluate(ctx, rule, eval_time):
                continue
            out["detected"] += 1
            fired.add((rule.id, nd.node_id))
            S, inputs = score_rule(ctx, rule, eval_time, scoring_cfg)
            gate_s_eff = max(40, min(90, gate_s + int(rule_offsets.get(rule.id, 0))))  # L6 nudge
            if S < gate_s_eff or inputs["C"] < gate_c:
                _suppress(store, org_id, rule.id, nd.node_id, "below_gate", eval_time,
                          {"S": S, "C": inputs["C"]})
                out["below_gate"] += 1
                continue
            if _recent_signal(store, org_id, rule.id, nd.node_id, rule.cooldown_hours, eval_time):
                _suppress(store, org_id, rule.id, nd.node_id, "cooldown", eval_time)
                out["cooldown"] += 1
                continue
            evidence = [{"field": f, "value": (ctx.facts.get(f) or {}).get("value")}
                        for f in rule.evidence_fields]
            candidates.append((S, inputs, rule, nd.node_id, evidence))

    # Rank by S, then spend a SEAT-SCALED daily budget on the best first (was: per-org cap of 7 in
    # node-scan order → a multi-seat team starved to 7 total and a 90-score signal budget-dropped
    # by earlier low ones). Delivery still caps pushes per assignee at L5 (router.budget_full).
    candidates.sort(key=lambda x: x[0], reverse=True)
    remaining = max(0, budget_per_day * _active_seats(store, org_id)
                    - _budget_used(store, org_id, eval_time))
    for i, (S, inputs, rule, node_id, evidence) in enumerate(candidates):
        if i >= remaining:
            _suppress(store, org_id, rule.id, node_id, "budget", eval_time, {"S": S, "rank": i})
            out["budget"] += 1
            continue
        sid = _emit(store, org_id, rule, node_id, S, inputs, evidence, eval_time, snapshot_id)
        out["emitted" if sid else "duplicate_race"] += 1

    # C3 — composite deal-health pass: cluster the just-emitted per-rule signals by deal and emit ONE
    # "deal at risk: X+Y+Z" signal per compound deal. Runs BEFORE the lifecycle close, and every deal
    # that still qualifies is added to `fired` so its composite isn't swept as stale.
    comp = compose_deal_health(store, org_id, eval_time, snapshot_id, adj=nbr_adj, fired=fired)
    out["composite"] += comp["emitted"]
    for nid in comp["active"]:
        fired.add((_COMPOSITE_RULE_ID, nid))

    # lifecycle (C7) — close open signals whose rule no longer fires (condition cleared)
    with store.engine.connect() as c:
        open_sigs = c.execute(text("select signal_id, rule_id, subject_node_id from signals "
                                   "where org_id=:o and status='open'"), {"o": org_id}).fetchall()
    for sig in open_sigs:
        if (sig.rule_id, sig.subject_node_id) not in fired:
            with store.engine.begin() as c:
                c.execute(text("update signals set status='resolved' where signal_id=:id"),
                          {"id": sig.signal_id})
            out["resolved"] += 1
    return {"nodes": len(nodes), "outcomes": dict(out), "eval_time": eval_time.isoformat(),
            "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                     "snapshot_id": snapshot_id}}
