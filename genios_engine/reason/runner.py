from __future__ import annotations

import json
import logging
import math
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore
from genios_engine.contracts.reasoning import DecisionOutcome, ExecutionMode
from genios_engine.packs.capabilities import BUILTIN_CAPABILITIES
from genios_engine.packs.registry import PackRegistry
from genios_engine.packs.wiring import (DEFAULT_PACK_ID, ensure_default, ensure_defaults,
                                        make_registry)
from genios_engine.platform.ids import new_id

from .baselines import build_baselines, load_node_metrics
from .adapters import (legacy_capability_manifest, reason_legacy_rule,
                       reason_native_capability)
from .audit import persist_execution
from .authority import (AUTHORITATIVE_SIGNAL_JOINS, AUTHORITATIVE_SIGNAL_PREDICATE,
                        projected_score)
from .composer import COMPOSITE_RULE_ID as _COMPOSITE_RULE_ID
from .composer import compose_deal_health
from .engine import NodeContext
from .publication import (build_native_publication, native_rule_id, native_rule_ids,
                          publish_native_signal)
from .rules import rule_from_dict, rules_for_scope
from .signals_derived import (NEIGHBOR_DERIVED_PATHS, deal_activity_facts, deal_facts,
                              sentiment_facts)
from .store import ReasoningStore

logger = logging.getLogger(__name__)

# cross-entity condition keys — presence in ANY effective rule means we must load neighbourhoods.
_CROSS_ENTITY_KEYS = {"neighbor_has_obs", "neighbor_no_obs", "neighbor_fact"}
_VERIFIED_STAKEHOLDER_FIELDS = frozenset({
    "contact.verified_recipient",
    "person.verified_recipient",
    "stakeholder.verified",
    "stakeholder.verified_recipient",
    "relationship.verified",
})


def _rules_need_neighbors(rules) -> bool:
    for r in rules:
        # A rule clocking off a neighbour-derived path (deal.last_inbound) is just as
        # dependent on the index as an explicit edge_count/neighbor_fact condition — and
        # far easier to miss, because nothing in its `when` mentions a neighbour.
        if r.urgency.get("path") in NEIGHBOR_DERIVED_PATHS:
            return True
        for c in r.when:
            if c.get("fn") == "edge_count" or _CROSS_ENTITY_KEYS & set(c.keys()):
                return True
            if c.get("path") in NEIGHBOR_DERIVED_PATHS:
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
                "f.fact_version_id, "
                "  (select min(sr.source_ref_id) from graph_source_refs sr "
                "   where sr.org_id=f.org_id and sr.fact_version_id=f.fact_version_id) "
                "   as source_ref_id, "
                "  (select min(sr.source) from graph_source_refs sr "
                "   where sr.org_id=f.org_id and sr.fact_version_id=f.fact_version_id) "
                "   as source_group, "
                "  (select count(distinct sr.source) from graph_source_refs sr "
                "   join graph_facts fv on fv.fact_version_id=sr.fact_version_id and fv.org_id=f.org_id "
                "   where fv.fact_id=f.fact_id) as src_count "
                "from graph_facts f "
                "where f.org_id=:o and f.subject_node_id=:n and f.valid_to is null "
                "and f.status='active' "
                "order by f.field, f.authority_rank desc nulls last, "
                "f.confidence desc nulls last, "
                "f.occurred_at desc nulls last, f.fact_version_id desc"),
                {"o": org_id, "n": node_id}):
            if r.field in facts:
                continue
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            facts[r.field] = {"value": v,
                              "confidence": (float(r.confidence)
                                             if r.confidence is not None else 0.5),
                              "authority_rank": int(r.authority_rank or 1),
                              "occurred_at": r.occurred_at,
                              "fact_version_id": r.fact_version_id,
                              "source_ref_id": r.source_ref_id,
                              "independence_group": (f"source:{r.source_group}"
                                                     if r.source_group else "unattributed"),
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
    node_types: dict = {}   # node_id -> current graph node type
    obs_idx: dict = {}      # node_id -> set(observation kinds)
    fact_idx: dict = {}     # node_id -> {field: latest value}
    with store.engine.connect() as c:
        # NB: do NOT alias to_node_id as `t` — Row.t is a reserved SQLAlchemy attribute and shadows it.
        for r in c.execute(text(
                "select e.from_node_id, e.to_node_id, nf.node_type as from_node_type, "
                "nt.node_type as to_node_type from graph_edges e "
                "join graph_nodes nf on nf.org_id=e.org_id and nf.node_id=e.from_node_id "
                "and nf.valid_to is null join graph_nodes nt on nt.org_id=e.org_id "
                "and nt.node_id=e.to_node_id and nt.valid_to is null "
                "where e.org_id=:o and e.valid_to is null"), {"o": org_id}):
            adj.setdefault(r.from_node_id, set()).add(r.to_node_id)
            adj.setdefault(r.to_node_id, set()).add(r.from_node_id)
            node_types[r.from_node_id] = r.from_node_type
            node_types[r.to_node_id] = r.to_node_type
        for r in c.execute(text("select subject_node_id nid, kind from graph_observations "
                                "where org_id=:o and status='active'"), {"o": org_id}):
            obs_idx.setdefault(r.nid, set()).add(r.kind)
        for r in c.execute(text(
                                "select subject_node_id nid, field, value, occurred_at, "
                                "authority_rank, confidence from graph_facts "
                                "where org_id=:o and valid_to is null and status='active' "
                                "order by subject_node_id, field, authority_rank desc nulls last, "
                                "confidence desc nulls last, occurred_at desc nulls last, "
                                "fact_version_id desc"),
                           {"o": org_id}):
            d = fact_idx.setdefault(r.nid, {})
            if r.field in d:  # first is the highest-authority/confidence current claim
                continue
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            d[r.field] = (v, r.occurred_at, int(r.authority_rank or 1),
                          float(r.confidence or 0))
    return adj, node_types, obs_idx, fact_idx


def _verified_stakeholder_count(node_id, adj, node_types, fact_idx) -> int:
    """Count distinct adjacent people carrying an explicit current verification fact.

    Generic edges (company, meeting, commitment, competitor, etc.) are graph structure, not proof
    of customer stakeholder coverage. A relationship is counted only when the neighbour is a
    person-like node and its latest active facts explicitly mark the recipient/stakeholder true.
    """
    count = 0
    for neighbor_id in adj.get(node_id, set()):
        if node_types.get(neighbor_id) not in {"person", "contact", "stakeholder"}:
            continue
        facts = fact_idx.get(neighbor_id, {})
        verified = False
        for field in _VERIFIED_STAKEHOLDER_FIELDS:
            if field not in facts:
                continue
            record = facts[field]
            raw = record[0]
            authority_rank = int(record[2]) if len(record) > 2 else 1
            confidence = float(record[3]) if len(record) > 3 else 0
            if (authority_rank >= 2 and math.isfinite(confidence) and confidence >= 0.8
                    and (raw is True
                         or (isinstance(raw, str) and raw.strip().lower() == "true"))):
                verified = True
                break
        if verified:
            count += 1
    return count


def _neighborhood(node_id, adj, obs_idx, fact_idx):
    """Per-node 1-hop neighbourhood from the bulk index → (edge_count, neighbor_obs, neighbor_facts).
    neighbor_facts holds the LATEST value per field ACROSS all neighbours (by occurred_at), so the
    result is deterministic — not whichever neighbour set-iteration happened to visit first."""
    nbrs = adj.get(node_id, set())
    neighbor_obs: set = set()
    best: dict = {}          # field -> (value, occurred_at, source_node_id)
    # A graph neighbourhood is a set, so iteration order is intentionally undefined. Always
    # traverse by stable node id and retain that id in the tie-break state; otherwise two equal-time
    # facts can produce different decisions under a different PYTHONHASHSEED.
    for n in sorted(nbrs):
        neighbor_obs |= obs_idx.get(n, set())
        for f, record in fact_idx.get(n, {}).items():
            v, ts = record[0], record[1]
            cur = best.get(f)
            # Prefer the newer occurred_at; a dated fact beats an undated one. Equal timestamps
            # resolve by lexical source node id, never by set/row order.
            if (cur is None
                    or (ts is not None and cur[1] is None)
                    or (ts is not None and cur[1] is not None and ts > cur[1])
                    or (ts == cur[1] and n < cur[2])):
                best[f] = (v, ts, n)
    neighbor_facts = {f: v for f, (v, _ts, _nid) in best.items()}
    return len(nbrs), neighbor_obs, neighbor_facts


def _recent_signal(store, org_id, rule_id, node_id, cooldown_hours, eval_time,
                   config_snapshot_id, pack_id, pack_version) -> bool:
    with store.engine.connect() as c:
        return c.execute(text(
            "select 1 from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            " where s.org_id=:o and s.rule_id=:r and s.subject_node_id=:n "
            "and s.pack_id=:p and s.pack_version=:pv "
            "and s.status='open' and s.config_snapshot_id=:cfg "
            "and s.created_at > :since and " + AUTHORITATIVE_SIGNAL_PREDICATE + " limit 1"),
            {"o": org_id, "r": rule_id, "n": node_id,
             "p": pack_id, "pv": pack_version,
             "cfg": config_snapshot_id, "authority_time": eval_time,
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
        tier = str(c.execute(text(
            "select subscription_tier from orgs where id=:o"),
            {"o": org_id}).scalar() or "trial").lower()
    licensed = {"trial": 2, "startup": 5, "growth": 15, "scale": 50}.get(tier, 2)
    return max(1, min(int(n or 0), licensed))


def _graph_version(store, org_id: str) -> int:
    """Bind every reasoning snapshot to the exact persisted graph version it observed."""
    with store.engine.connect() as c:
        return int(c.execute(text(
            "select coalesce(max(graph_version),0) from graph_versions where org_id=:o"),
            {"o": org_id}).scalar() or 0)


def _pack_authority_revision(store, org_id: str, pack_id: str) -> int | None:
    with store.engine.connect() as c:
        value = c.execute(text(
            "select authority_revision from tenant_packs where org_id=:o and pack_id=:p"),
            {"o": org_id, "p": pack_id}).scalar()
    return int(value) if value is not None else None


@contextmanager
def _graph_version_guard(store, org_id: str, expected: int, *, pack_id: str | None = None,
                         pack_authority_revision: int | None = None,
                         evaluation_time: datetime | None = None):
    """Hold the tenant version row stable while signals are published and composed.

    Every graph writer bumps ``graph_versions`` in its graph transaction. PostgreSQL's
    ``FOR SHARE`` therefore gives this short publication phase a tenant-scoped read barrier:
    a writer either commits before the lock (and fails the equality check) or after the
    publication transaction releases it. It cannot commit a mixed graph in between.
    """
    with store.engine.begin() as c:
        publication_fresh = True
        if evaluation_time is not None:
            c.execute(text(
                "insert into reasoning_publication_watermarks "
                "(org_id,last_evaluation_time) values (:o,:et) on conflict (org_id) do nothing"),
                {"o": org_id, "et": evaluation_time})
            watermark = c.execute(text(
                "select last_evaluation_time from reasoning_publication_watermarks "
                "where org_id=:o for update"), {"o": org_id}).scalar()
            publication_fresh = watermark is None or evaluation_time >= watermark
            if publication_fresh:
                c.execute(text(
                    "update reasoning_publication_watermarks set "
                    "last_evaluation_time=greatest(last_evaluation_time,:et),"
                    "updated_at=clock_timestamp() where org_id=:o"),
                    {"o": org_id, "et": evaluation_time})
        locked = c.execute(text(
            "select graph_version from graph_versions where org_id=:o for share"),
            {"o": org_id}).scalar()
        current = int(locked or 0)
        pack_stable = True
        if pack_id is not None:
            # Exclusive row lock serializes publication for this exact tenant/pack. A second
            # cron/manual sweep may reason concurrently, but it cannot re-spend budget or replace
            # the first sweep's fresh signal until it rechecks both under this lock.
            held_revision = c.execute(text(
                "select authority_revision from tenant_packs "
                "where org_id=:o and pack_id=:p for update"),
                {"o": org_id, "p": pack_id}).scalar()
            pack_stable = (held_revision is not None
                           and int(held_revision) == pack_authority_revision)
        yield current == expected and pack_stable and publication_fresh


def _suppress(store, org_id, rule_id, node_id, reason, eval_time, detail=None) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into signal_suppression_log (org_id, rule_id, subject_node_id, "
            "reason_code, detail, eval_time) values (:o,:r,:n,:rc,cast(:d as jsonb),:e)"),
            {"o": org_id, "r": rule_id, "n": node_id, "rc": reason,
             "d": json.dumps(detail or {}, default=str), "e": eval_time})


def _emit(store, org_id, rule, node_id, S, inputs, evidence, eval_time, snapshot_id,
          reasoning_run_id, reasoning_candidate_id, reasoning_decision_hash,
          authority_expires_at, selected_play_id, authority_pack_revision,
          pack_id, pack_version) -> str | None:
    """Emit signal.v1. ON CONFLICT DO NOTHING against the partial-unique index (one OPEN signal
    per org/rule/node) → a concurrent run that already emitted this signal makes us a no-op
    instead of a duplicate. Returns the id, or None if a concurrent run beat us to it."""
    sid = new_id("sig")
    with store.engine.begin() as c:
        retired = c.execute(text(
            "update signals set status='expired' where org_id=:o and rule_id=:r "
            "and pack_id=:p and pack_version=:pv "
            "and subject_node_id=:n and status='open' returning signal_id"),
            {"o": org_id, "r": rule.id, "n": node_id,
             "p": pack_id, "pv": pack_version}).fetchall()
        if retired:
            c.execute(text(
                "update cards set state='expired' where org_id=:o and signal_id=any(:ids) "
                "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
                {"o": org_id, "ids": [item.signal_id for item in retired]})
        row = c.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, "
            "rule_version, level, "
            "subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
            "config_snapshot_id, reasoning_run_id, reasoning_candidate_id, "
            "reasoning_decision_hash, authority_expires_at, authority_pack_revision, "
            "authority_binding_version) "
            "values (:id,:o,:pack,:packv,:r,:v,:lv,:n,:s,cast(:si as jsonb),:rc,"
            "cast(:ev as jsonb),:play,:et,"
            ":cs,:rr,:candidate,:decision_hash,:expires,:pack_revision,1) "
            "on conflict (org_id,pack_id,pack_version,rule_id,subject_node_id) "
            "where status='open' do nothing "
            "returning signal_id"),
            {"id": sid, "o": org_id, "pack": pack_id, "packv": pack_version,
             "r": rule.id, "v": rule.version, "lv": rule.level,
             "n": node_id, "s": S, "si": json.dumps(inputs, default=str),
             "rc": rule.reason_code, "ev": json.dumps(evidence, default=str),
             "play": selected_play_id, "et": eval_time, "cs": snapshot_id,
             "rr": reasoning_run_id, "candidate": reasoning_candidate_id,
             "decision_hash": reasoning_decision_hash, "expires": authority_expires_at,
             "pack_revision": authority_pack_revision}).first()
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
                value = float(str(r.value).strip('"'))
                if math.isfinite(value):
                    vals.append(value)
            except (ValueError, TypeError):
                pass
    if len(vals) < min_deals:
        return None
    vals.sort()
    return round(vals[min(len(vals) - 1, int(math.ceil(0.9 * len(vals)) - 1))], 2)


def _muted_rules(store, org_id: str, pack_id: str, pack_version: str) -> set[str]:
    """Active auto-mutes, read from the rule_mutes table the learning layer (L7) writes.
    Learned state flows to reasoning as DATA (this table, and rule_offsets via lvl3_config)
    — never as an upward code import; the layer-topology test enforces that. Mutes deliberately
    persist across threshold-only authority epochs within one immutable pack version; their exact
    source capability/revision remains in the audit row, and a pack-version change stops them."""
    with store.engine.connect() as c:
        return {r.rule_id for r in c.execute(text(
            "select rule_id from rule_mutes where org_id=:o and pack_id=:p "
            "and pack_version=:pv and active"),
            {"o": org_id, "p": pack_id, "pv": pack_version})}


def run(*, org_id: str, store: GraphStore, eval_time: datetime | None = None,
        registry: PackRegistry | None = None, pack_id: str = DEFAULT_PACK_ID) -> dict:
    eval_time = eval_time or datetime.now(timezone.utc)

    # L4 — resolve the tenant's effective config (rules + scoring + gate + budget + snapshot id).
    registry = registry or make_registry()
    ensure_default(registry, org_id)                       # design-partner default: sales.v1
    pack_authority_revision = _pack_authority_revision(store, org_id, pack_id)
    effective, snapshot_id = registry.effective(org_id, pack_id)
    if effective is None:                                  # no pack applied → L3 does nothing
        return {"nodes": 0, "outcomes": {}, "eval_time": eval_time.isoformat(),
                "pack": None}
    if (pack_authority_revision is None
            or _pack_authority_revision(store, org_id, pack_id) != pack_authority_revision):
        return {"nodes": 0, "outcomes": {"pack_changed_retry": 1},
                "eval_time": eval_time.isoformat(), "retry_required": True,
                "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                         "snapshot_id": snapshot_id}}
    reasoning_store = ReasoningStore(engine=store.engine)
    execution_mode = (ExecutionMode.LIVE if effective.get("state") == "active"
                      else ExecutionMode.SHADOW)
    # Native manifests remain explicitly shadow-first until a separate activation decision and
    # delivery adapter exist. They still execute and persist full traces in the real runner.
    native_capabilities = tuple(
        capability for capability in BUILTIN_CAPABILITIES
        if capability.domain == effective["pack_id"]
    )

    scoring_cfg = effective["scoring"]
    # Capture BEFORE the first graph-derived runtime overlay. Previously the capture happened
    # after P90 + baselines, allowing a mixed P90 snapshot to be stamped as if it belonged to the
    # later graph version.
    graph_version = _graph_version(store, org_id)
    _p90 = _tenant_deal_p90(store, org_id)                  # learn deal-value P90 from THIS tenant
    if _graph_version(store, org_id) != graph_version:
        return {"nodes": 0, "outcomes": {"graph_changed_retry": 1},
                "eval_time": eval_time.isoformat(), "retry_required": True,
                "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                         "snapshot_id": snapshot_id, "graph_version": graph_version}}
    if _p90:
        scoring_cfg = {**scoring_cfg,
                       "impact": {**scoring_cfg.get("impact", {}), "p90_default": _p90}}
        effective = {**effective, "scoring": scoring_cfg}
        snapshot_id = registry.persist_effective_snapshot(
            org_id, pack_id, effective, cause="runtime_tenant_p90")
    budget_per_day = int(scoring_cfg.get("budget_per_user_day", 7))
    all_rules = [rule_from_dict(r) for r in effective["rules"]]
    # Capability compilation depends on pack/config, not entity context. Compile once per rule per
    # sweep instead of rebuilding and rehashing the same manifest for every graph node.
    legacy_capabilities = {
        rule.id: legacy_capability_manifest(
            rule=rule,
            scoring=scoring_cfg,
            pack_id=effective["pack_id"],
            pack_version=effective["version"],
            play_config=(effective.get("plays") or {}).get(rule.play, {}),
            config_snapshot_id=snapshot_id,
        ) for rule in all_rules
    }

    build_baselines(store, org_id, eval_time)              # C9: refresh baselines (+C1 momentum/engagement)
    # Baseline construction is another multi-query graph read. Keep the original capture and
    # reject the sweep if that read crossed a graph commit.
    if _graph_version(store, org_id) != graph_version:
        return {"nodes": 0, "outcomes": {"graph_changed_retry": 1},
                "eval_time": eval_time.isoformat(), "retry_required": True,
                "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                         "snapshot_id": snapshot_id, "graph_version": graph_version}}
    need_neighbors = (_rules_need_neighbors(all_rules) or bool(native_capabilities))
    nbr_adj = nbr_node_types = nbr_obs_idx = nbr_fact_idx = None
    if need_neighbors:
        nbr_adj, nbr_node_types, nbr_obs_idx, nbr_fact_idx = _neighbor_index(store, org_id)
    muted = _muted_rules(store, org_id, effective["pack_id"], effective["version"])
    out: Counter = Counter()
    fired: set[tuple[str, str]] = set()
    indeterminate: set[tuple[str, str]] = set()             # evaluation failed: never auto-resolve
    candidates: list = []                                  # gated signals, ranked before spending
    native_candidates: list = []                           # authorized native decisions, unspent
    graph_drifted = False
    with store.engine.connect() as c:
        nodes = c.execute(text("select node_id, node_type from graph_nodes "
                               "where org_id=:o and valid_to is null order by node_id"),
                          {"o": org_id}).fetchall()
    for nd in nodes:
        rules = rules_for_scope(all_rules, nd.node_type)
        node_capabilities = tuple(capability for capability in native_capabilities
                                  if capability.root_entity_type == nd.node_type)
        if not rules and not node_capabilities:
            continue
        ctx = _load_context(store, org_id, nd.node_id, nd.node_type)
        baselines, derived = load_node_metrics(store, org_id, nd.node_id)  # C1: one query, both
        ctx.baselines = baselines
        ctx.facts.update(derived)                          # derived.momentum / derived.engagement
        ctx.facts.update(sentiment_facts(ctx.obs, eval_time))  # derived.sentiment (90d window)
        if nd.node_type == "deal":                         # F1: deal.status/value from deal.stage/amount
            ctx.facts.update(deal_facts(ctx.facts))
        if need_neighbors:
            ctx.edge_count, ctx.neighbor_obs, ctx.neighbor_facts = \
                _neighborhood(nd.node_id, nbr_adj, nbr_obs_idx, nbr_fact_idx)
            if nd.node_type == "deal":
                # cross-tool join: the CRM knows the deal, email knows the conversation.
                # Only fills what is ABSENT, so a real CRM/human value always wins.
                for path, fact in deal_activity_facts(
                        nd.node_id, nbr_adj, nbr_node_types, nbr_fact_idx).items():
                    ctx.facts.setdefault(path, fact)
                ctx.facts["relationship.verified_stakeholder_count"] = {
                    "value": _verified_stakeholder_count(
                        nd.node_id, nbr_adj, nbr_node_types, nbr_fact_idx),
                    "confidence": 1,
                    "authority_rank": 2,
                    "independence_group": "graph:verified_stakeholders",
                    "src_count": 1,
                }
        if _graph_version(store, org_id) != graph_version:
            graph_drifted = True
            out["graph_changed_retry"] += 1
            for rule in rules:
                indeterminate.add((rule.id, nd.node_id))
            break
        for capability in node_capabilities:
            native_rule = native_rule_id(capability.capability_id)
            try:
                native_execution = reason_native_capability(
                    org_id=org_id,
                    context=ctx,
                    capability=capability,
                    evaluation_time=eval_time,
                    graph_version=graph_version,
                    config_snapshot_id=snapshot_id,
                    mode=execution_mode,
                )
                if _graph_version(store, org_id) != graph_version:
                    graph_drifted = True
                    out["graph_changed_retry"] += 1
                    break
                persisted_native = persist_execution(
                    store=reasoning_store,
                    execution=native_execution,
                )
            except Exception as exc:
                logger.exception("Native Layer 4 capability failed for %s:%s:%s",
                                 org_id, capability.capability_id, nd.node_id)
                _suppress(store, org_id, native_rule, nd.node_id,
                          "native_reasoning_failed", eval_time,
                          {"error_type": type(exc).__name__,
                           "capability_id": capability.capability_id})
                # A capability that could not reason has said nothing about this subject, so its
                # previous claim must not be retired as though it had cleared.
                indeterminate.add((native_rule, nd.node_id))
                out["native_failed"] += 1
                continue
            out[f"native_{native_execution.decision.outcome.value}"] += 1
            native_run_id = persisted_native["run"]["run_id"]
            if native_execution.decision.outcome in {
                    DecisionOutcome.FAILED, DecisionOutcome.INSUFFICIENT_CONTEXT}:
                _suppress(store, org_id, native_rule, nd.node_id,
                          "native_reasoning_failed", eval_time,
                          {"reasoning_run_id": native_run_id,
                           "outcome": native_execution.decision.outcome.value,
                           "uncertainty": list(native_execution.decision.uncertainty)})
                indeterminate.add((native_rule, nd.node_id))
                continue
            publication = build_native_publication(
                execution=native_execution, audit_bundle=persisted_native)
            if publication is None:
                # Every non-publishing outcome is recorded with the reason it did not publish.
                # "Reasoned and stayed silent" and "never reasoned" are different facts, and an
                # operator reading the log during rollout needs to tell them apart.
                _suppress(store, org_id, native_rule, nd.node_id,
                          "native_not_authorized", eval_time,
                          {"reasoning_run_id": native_run_id,
                           "outcome": native_execution.decision.outcome.value,
                           "execution_mode": native_execution.request.mode.value,
                           "live_delivery_enabled": capability.live_delivery_enabled})
                out["native_suppressed"] += 1
                continue
            # An authorized decision keeps its subject alive for lifecycle even if budget or
            # cooldown stops it publishing this sweep — the claim is still true.
            fired.add((native_rule, nd.node_id))
            if _recent_signal(store, org_id, native_rule, nd.node_id,
                              publication.cooldown_hours, eval_time, snapshot_id,
                              effective["pack_id"], effective["version"]):
                _suppress(store, org_id, native_rule, nd.node_id, "cooldown", eval_time,
                          {"reasoning_run_id": native_run_id, "native": True})
                out["native_cooldown"] += 1
                continue
            native_candidates.append((publication, native_run_id))
        if graph_drifted:
            break
        for rule in rules:
            if rule.id in muted:                          # L6 auto-mute — rule is harmful, silence it
                out["muted"] += 1
                continue
            try:
                reasoned = reason_legacy_rule(
                    org_id=org_id,
                    context=ctx,
                    rule=rule,
                    evaluation_time=eval_time,
                    scoring=scoring_cfg,
                    config_snapshot_id=snapshot_id,
                    pack_id=effective["pack_id"],
                    pack_version=effective["version"],
                    play_config=(effective.get("plays") or {}).get(rule.play, {}),
                    graph_version=graph_version,
                    capability=legacy_capabilities[rule.id],
                    mode=execution_mode,
                )
            except Exception as exc:
                logger.exception("Layer 4 input normalization failed for %s:%s:%s",
                                 org_id, rule.id, nd.node_id)
                _suppress(store, org_id, rule.id, nd.node_id,
                          "reasoning_input_invalid", eval_time,
                          {"error_type": type(exc).__name__})
                indeterminate.add((rule.id, nd.node_id))
                out["reasoning_input_invalid"] += 1
                continue
            if _graph_version(store, org_id) != graph_version:
                graph_drifted = True
                indeterminate.add((rule.id, nd.node_id))
                _suppress(store, org_id, rule.id, nd.node_id, "graph_changed_retry", eval_time,
                          {"captured_graph_version": graph_version})
                out["graph_changed_retry"] += 1
                break
            try:
                # Persist every deterministic outcome—not only recommendations that survive the
                # delivery gate. This makes no-action, insufficient-context, blocked, and failed
                # executions available for audit/replay while authorizing none of them.
                audit_bundle = persist_execution(
                    store=reasoning_store,
                    execution=reasoned.execution,
                )
                reasoning_run_id = audit_bundle["run"]["run_id"]
            except Exception as exc:
                logger.exception("Layer 4 audit persistence failed for %s:%s:%s",
                                 org_id, rule.id, nd.node_id)
                _suppress(store, org_id, rule.id, nd.node_id, "audit_failed", eval_time,
                          {"error_type": type(exc).__name__,
                           "trace_run_id": reasoned.execution.trace.run_id})
                indeterminate.add((rule.id, nd.node_id))
                out["audit_failed"] += 1
                continue
            if reasoned.execution.decision.outcome in {
                    DecisionOutcome.FAILED, DecisionOutcome.INSUFFICIENT_CONTEXT}:
                outcome = reasoned.execution.decision.outcome.value
                _suppress(store, org_id, rule.id, nd.node_id, "reasoning_failed", eval_time,
                          {"outcome": outcome,
                           "uncertainty": reasoned.execution.decision.uncertainty,
                           "run_id": reasoned.execution.trace.run_id})
                indeterminate.add((rule.id, nd.node_id))
                out[outcome] += 1
                continue
            if reasoned.execution.decision.outcome == DecisionOutcome.BLOCKED:
                _suppress(store, org_id, rule.id, nd.node_id, "reasoning_blocked", eval_time,
                          {"reasoning_run_id": reasoning_run_id,
                           "checks": [check.reason_code
                                      for candidate in reasoned.execution.candidates
                                      for check in candidate.checks
                                      if check.outcome.value == "eliminate"]})
                out["below_gate"] += 1
                continue
            if not reasoned.matched:
                continue
            out["detected"] += 1
            S, inputs = reasoned.score, reasoned.score_inputs
            if not reasoned.execution.authorizes_delivery:
                _suppress(store, org_id, rule.id, nd.node_id, "shadow", eval_time,
                          {"reasoning_run_id": reasoning_run_id,
                           "execution_mode": reasoned.execution.request.mode.value,
                           "live_delivery_enabled":
                               reasoned.execution.request.capability.live_delivery_enabled})
                out["shadow"] += 1
                continue
            selected = reasoned.execution.selected_candidate
            if selected is None:
                indeterminate.add((rule.id, nd.node_id))
                out["authority_invalid"] += 1
                continue
            S = projected_score(selected.utility_bp)
            # A shadow or non-deliverable run must not keep a prior live signal alive.  Only a
            # currently authorized match participates in lifecycle preservation.
            fired.add((rule.id, nd.node_id))
            if _recent_signal(store, org_id, rule.id, nd.node_id, rule.cooldown_hours,
                              eval_time, snapshot_id, effective["pack_id"], effective["version"]):
                _suppress(store, org_id, rule.id, nd.node_id, "cooldown", eval_time,
                          {"reasoning_run_id": reasoning_run_id})
                out["cooldown"] += 1
                continue
            evidence = [{"field": f, "value": (ctx.facts.get(f) or {}).get("value")}
                        for f in rule.evidence_fields]
            candidates.append((
                S, inputs, rule, nd.node_id, evidence, reasoning_run_id,
                audit_bundle["output"]["selected_candidate_id"],
                audit_bundle["output"]["decision_hash"],
                reasoned.execution.decision.expires_at, selected.play_id,
            ))
        if graph_drifted:
            break

    if not graph_drifted and _graph_version(store, org_id) != graph_version:
        graph_drifted = True
        out["graph_changed_retry"] += 1

    if graph_drifted:
        # Persisted immutable shadow/audit inputs are harmless, but no signal or lifecycle mutation
        # may cross the authority boundary until a fresh stable sweep succeeds.
        return {"nodes": len(nodes), "outcomes": dict(out),
                "eval_time": eval_time.isoformat(),
                "retry_required": True,
                "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                         "snapshot_id": snapshot_id, "graph_version": graph_version}}

    # Acquire a short tenant-scoped read barrier for the complete authority transition: ranked
    # signal emission, composite reasoning/emission, and lifecycle resolution. All graph writers
    # update this same row transactionally, so no graph commit can split this window.
    with _graph_version_guard(
            store, org_id, graph_version, pack_id=pack_id,
            pack_authority_revision=pack_authority_revision,
            evaluation_time=eval_time) as stable:
        if not stable or _graph_version(store, org_id) != graph_version:
            graph_drifted = True
            out["graph_changed_retry"] += 1
        else:
            # Rank by S, then spend a SEAT-SCALED daily budget on the best first (was: per-org cap
            # of 7 in node-scan order). Stable total order: score desc, then rule and entity ids.
            candidates.sort(key=lambda x: (-x[0], x[2].id, x[3]))
            remaining = max(0, budget_per_day * _active_seats(store, org_id)
                            - _budget_used(store, org_id, eval_time))
            for i, (S, inputs, rule, node_id, evidence, reasoning_run_id,
                    reasoning_candidate_id, reasoning_decision_hash,
                    authority_expires_at, selected_play_id) in enumerate(candidates):
                if i >= remaining:
                    _suppress(store, org_id, rule.id, node_id, "budget", eval_time,
                              {"S": S, "rank": i, "reasoning_run_id": reasoning_run_id})
                    out["budget"] += 1
                    continue
                # A concurrent sweep may have passed the earlier read-only cooldown check before
                # this sweep published. Recheck after acquiring the exclusive pack publication
                # lock; otherwise the second worker can expire and replace the first worker's
                # just-created signal while also exceeding the daily budget.
                if _recent_signal(store, org_id, rule.id, node_id, rule.cooldown_hours,
                                  eval_time, snapshot_id,
                                  effective["pack_id"], effective["version"]):
                    _suppress(store, org_id, rule.id, node_id, "cooldown", eval_time,
                              {"reasoning_run_id": reasoning_run_id,
                               "phase": "publication_recheck"})
                    out["cooldown"] += 1
                    continue
                sid = _emit(
                    store, org_id, rule, node_id, S, inputs, evidence, eval_time,
                    snapshot_id, reasoning_run_id, reasoning_candidate_id,
                    reasoning_decision_hash, authority_expires_at, selected_play_id,
                    pack_authority_revision, effective["pack_id"], effective["version"])
                out["emitted" if sid else "duplicate_race"] += 1

            # Native capabilities publish after the legacy rules and out of the same daily
            # reservation, which `_budget_used` re-reads from the signals table so the spend above
            # is already counted. Legacy therefore wins a contested budget. That ordering is a
            # rollout decision, not a ranking claim: the shipped baseline keeps its seat while a
            # candidate roster proves itself, and reversing it is a one-line move once it has.
            native_candidates.sort(key=lambda item: (-item[0].score, item[0].rule_id,
                                                     item[0].subject_node_id))
            native_remaining = max(0, budget_per_day * _active_seats(store, org_id)
                                   - _budget_used(store, org_id, eval_time))
            for position, (publication, native_run_id) in enumerate(native_candidates):
                if position >= native_remaining:
                    _suppress(store, org_id, publication.rule_id, publication.subject_node_id,
                              "budget", eval_time,
                              {"S": publication.score, "rank": position,
                               "reasoning_run_id": native_run_id, "native": True})
                    out["native_budget"] += 1
                    continue
                # Same publication-time cooldown recheck the legacy path performs: a concurrent
                # sweep may have published this subject between the read-only check and this lock.
                if _recent_signal(store, org_id, publication.rule_id,
                                  publication.subject_node_id, publication.cooldown_hours,
                                  eval_time, snapshot_id,
                                  effective["pack_id"], effective["version"]):
                    _suppress(store, org_id, publication.rule_id, publication.subject_node_id,
                              "cooldown", eval_time,
                              {"reasoning_run_id": native_run_id, "native": True,
                               "phase": "publication_recheck"})
                    out["native_cooldown"] += 1
                    continue
                native_sid = publish_native_signal(
                    store, org_id=org_id, publication=publication, eval_time=eval_time,
                    config_snapshot_id=snapshot_id,
                    pack_id=effective["pack_id"], pack_version=effective["version"],
                    authority_pack_revision=pack_authority_revision)
                out["native_emitted" if native_sid else "native_duplicate_race"] += 1

            # Recheck at the emission/composition boundary. The shared lock makes this invariant
            # stable in PostgreSQL; the explicit check also fails closed for test doubles and any
            # future backend that cannot provide equivalent row-lock semantics.
            if _graph_version(store, org_id) != graph_version:
                graph_drifted = True
                out["graph_changed_retry"] += 1
            else:
                # C3 — compound deal-health reasoning over the just-emitted audited signals.
                if effective["pack_id"] == "sales":
                    daily_cap = budget_per_day * _active_seats(store, org_id)
                    composite_budget = max(0, daily_cap - _budget_used(store, org_id, eval_time))
                    comp = compose_deal_health(
                        store, org_id, eval_time, snapshot_id, adj=nbr_adj, fired=fired,
                        reasoning_store=reasoning_store, execution_mode=execution_mode,
                        graph_version=graph_version,
                        pack_authority_revision=pack_authority_revision,
                        pack_id=effective["pack_id"], pack_version=effective["version"],
                        new_signal_budget=composite_budget)
                    out["composite"] += comp["emitted"]
                    out["composite_budget"] += comp.get("budget_held", 0)
                    out["composite_audit_failed"] += comp.get("audit_failed", 0)
                    for nid in comp["active"]:
                        fired.add((_COMPOSITE_RULE_ID, nid))

            if not graph_drifted and _graph_version(store, org_id) != graph_version:
                graph_drifted = True
                out["graph_changed_retry"] += 1

            if not graph_drifted:
                # lifecycle (C7) — only this pack retires its own signals whose rule cleared.
                # Native capabilities own their projected rule ids too. Without them the first
                # native signal a subject received would stay open forever: the legacy sweep only
                # claims pack rule ids, so nothing would ever be entitled to retire it.
                pack_owns = {r.id for r in all_rules} | native_rule_ids(native_capabilities)
                with store.engine.connect() as c:
                    open_sigs = c.execute(text(
                        "select signal_id, rule_id, subject_node_id from signals "
                        "where org_id=:o and pack_id=:p and pack_version=:pv "
                        "and status='open'"),
                        {"o": org_id, "p": effective["pack_id"],
                         "pv": effective["version"]}).fetchall()
                for sig in open_sigs:
                    key = (sig.rule_id, sig.subject_node_id)
                    if (sig.rule_id in pack_owns and key not in fired
                            and key not in indeterminate):
                        with store.engine.begin() as c:
                            resolved = c.execute(text(
                                "update signals set status='resolved' where org_id=:o "
                                "and signal_id=:id and status='open' returning signal_id"),
                                {"o": org_id, "id": sig.signal_id}).first()
                            if resolved is not None:
                                c.execute(text(
                                    "update cards set state='expired' where org_id=:o "
                                    "and signal_id=:id and state in "
                                    "('queued','surfaced','snoozed','claimed','delivered')"),
                                    {"o": org_id, "id": sig.signal_id})
                                out["resolved"] += 1

    if graph_drifted:
        return {"nodes": len(nodes), "outcomes": dict(out),
                "eval_time": eval_time.isoformat(), "retry_required": True,
                "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                         "snapshot_id": snapshot_id, "graph_version": graph_version}}
    return {"nodes": len(nodes), "outcomes": dict(out), "eval_time": eval_time.isoformat(),
            "pack": {"pack_id": effective["pack_id"], "version": effective["version"],
                     "snapshot_id": snapshot_id}}


def run_all(*, org_id: str, store: GraphStore, eval_time: datetime | None = None,
           registry: PackRegistry | None = None) -> dict:
    """Evaluate EVERY pack applied to the org (sales + general by default), sequentially. Each
    pack's own run() re-reads the daily budget from the signals table, which already counts every
    org signal regardless of which pack emitted it — so the budget is shared across packs, not
    additive, with zero extra bookkeeping here. Outcomes merge; callers that only care about one
    pack can still call run() directly."""
    eval_time = eval_time or datetime.now(timezone.utc)
    registry = registry or make_registry()
    ensure_defaults(registry, org_id)
    with store.engine.connect() as c:
        pack_ids = [r[0] for r in c.execute(text(
            "select pack_id from tenant_packs where org_id=:o "
            "and state in ('active','shadow') order by pack_id"),
            {"o": org_id})]
    combined: Counter = Counter()
    nodes = 0
    for pid in pack_ids:
        res = run(org_id=org_id, store=store, eval_time=eval_time, registry=registry, pack_id=pid)
        nodes = max(nodes, res["nodes"])
        for k, v in res["outcomes"].items():
            combined[k] += v
    return {"nodes": nodes, "outcomes": dict(combined), "eval_time": eval_time.isoformat(),
            "packs": pack_ids}
