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
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import text

from genios_engine.contracts.reasoning import (ContextSnapshot, EvidenceRef, ExecutionMode,
                                               ReasoningRequest)
from genios_engine.packs.capabilities import DEAL_HEALTH_V1
from genios_engine.platform.canonical import stable_id
from genios_engine.platform.ids import new_id
from genios_engine.reason.adapters.legacy_context import semantic_legacy_value
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    projected_score,
)
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.store import ReasoningStore

COMPOSITE_RULE_ID = "deal_health"
COMPOSITE_REASON = "deal_health"
COMPOSITE_PLAY = "review_deal"
_ORCHESTRATOR = ReasoningOrchestrator(default_registry())
logger = logging.getLogger(__name__)


def _bounded_percent(value, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not amount.is_finite() or not 0 <= amount <= 100:
        raise ValueError(f"{label} must be finite and between 0 and 100")
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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
        return s.get(k) if isinstance(s, dict) else getattr(s, k, None)

    by_subject: dict = {}
    for s in signals:
        by_subject.setdefault(_g(s, "subject_node_id"), []).append(s)

    plans = []
    for deal_id in deal_ids:
        cluster = {deal_id} | set(adj.get(deal_id, set()))
        members = [s for nid in sorted(cluster) for s in by_subject.get(nid, [])]
        # Strongest driver first with an explicit total-order tie-break. Database/set order is not
        # semantic input and must never change a composite decision or its hash.
        members.sort(key=lambda m: (-_bounded_percent(_g(m, "score"), "signal score"),
                                    str(_g(m, "reason_code") or ""),
                                    str(_g(m, "subject_node_id") or ""),
                                    str(_g(m, "rule_id") or ""),
                                    str(_g(m, "signal_id") or "")))
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
        semantic_members = tuple(semantic_legacy_value({
            "signal_id": _g(member, "signal_id"),
            "rule_id": _g(member, "rule_id"),
            "reason_code": _g(member, "reason_code"),
            "subject_node_id": _g(member, "subject_node_id"),
            "score": _bounded_percent(_g(member, "score"), "signal score"),
            "score_inputs": (_g(member, "score_inputs")
                             if isinstance(_g(member, "score_inputs"), dict)
                             else json.loads(_g(member, "score_inputs") or "{}")),
            "reasoning_run_id": _g(member, "reasoning_run_id"),
            "config_snapshot_id": _g(member, "config_snapshot_id"),
        }) for member in members)
        member_ids = tuple(str(item["signal_id"]) for item in semantic_members
                           if item["signal_id"])
        parent_runs = tuple(sorted({str(item["reasoning_run_id"])
                                    for item in semantic_members
                                    if item["reasoning_run_id"]}))
        plans.append({
            "deal_id": deal_id,
            "score": _bounded_percent(_g(top, "score"), "signal score"),
            "codes": codes,
            "evidence": [{"field": "signal", "value": rc} for rc in codes],
            "inputs": {**inputs, "composite_of": codes,
                       "composite_member_ids": member_ids,
                       "parent_reasoning_run_ids": parent_runs},
            "members": semantic_members,
        })
    return plans


def _reason_composite(*, org_id: str, plan: dict, eval_time, snapshot_id: str,
                      graph_version: int, mode: ExecutionMode):
    members = tuple(plan["members"])
    evidence = tuple(EvidenceRef(
        evidence_id=stable_id("evidence", {
            "org_id": org_id,
            "deal_id": plan["deal_id"],
            "signal_id": member["signal_id"],
            "reasoning_run_id": member["reasoning_run_id"],
        }),
        field="signals.open",
        value=member,
        source_ref_id=str(member["signal_id"]),
        fact_version_id=str(member["reasoning_run_id"]),
        confidence_bp=max(0, min(10_000, int(
            (member.get("score_inputs") or {}).get("C", 50)) * 100)),
        authority_rank=2,
        independence_group=str(member["reasoning_run_id"]),
    ) for member in members)
    context = ContextSnapshot(
        org_id=org_id,
        graph_version=graph_version,
        root_entity_id=plan["deal_id"],
        root_entity_type="deal",
        evaluation_time=eval_time,
        selector_version="sales.deal_health.selector.v1",
        facts={"signals.open": members},
        evidence=evidence,
        metadata={"parent_reasoning_run_ids": plan["inputs"]["parent_reasoning_run_ids"]},
    )
    request = ReasoningRequest(
        org_id=org_id,
        capability=DEAL_HEALTH_V1,
        context=context,
        evaluation_time=eval_time,
        trigger_kind="signal.composition",
        trigger_ref=plan["deal_id"],
        mode=mode,
        config_snapshot_id=snapshot_id,
    )
    return _ORCHESTRATOR.execute(request)


def compose_deal_health(store, org_id: str, eval_time, snapshot_id, adj: dict | None = None,
                        fired: set | None = None, *, reasoning_store: ReasoningStore | None = None,
                        execution_mode: ExecutionMode = ExecutionMode.LIVE,
                        graph_version: int = 0,
                        pack_authority_revision: int | None = None,
                        pack_id: str = "sales", pack_version: str = "1.7.0",
                        new_signal_budget: int | None = None) -> dict:
    """Emit/refresh composite deal_health signals. Returns {'emitted': n, 'active': {deal_node_id,…}}
    where `active` is every deal that still qualifies — the runner adds these to its `fired` set so
    the lifecycle sweep doesn't resolve a composite that's still true.

    `fired` (from the runner: the {(rule_id, node_id)} that fired THIS run) filters the member set to
    currently-firing signals, so a stale still-open signal whose rule stopped firing — not yet closed
    by the same-run lifecycle sweep — doesn't get folded into a fresh verdict."""
    if (isinstance(pack_authority_revision, bool)
            or not isinstance(pack_authority_revision, int)
            or pack_authority_revision <= 0):
        raise ValueError("pack_authority_revision must be a positive integer")
    with store.engine.connect() as c:
        deals = c.execute(text(
            "select node_id, display_name from graph_nodes where org_id=:o "
            "and node_type='deal' and valid_to is null"), {"o": org_id}).fetchall()
        sigs = c.execute(text(
            "select s.signal_id, regexp_replace(rr.capability_id, '^.*\\.', '') as rule_id, " +
            AUTHORITATIVE_REASON_CODE_SQL + " as reason_code, s.subject_node_id, "
            + AUTHORITATIVE_SCORE_SQL + " as score, "
            + AUTHORITATIVE_SCORE_INPUTS_SQL + " as score_inputs, "
            "s.level, s.reasoning_run_id, s.config_snapshot_id "
            "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            "where s.org_id=:o and s.status='open' and s.rule_id <> :rc "
            "and s.pack_id=:pack and s.pack_version=:packv "
            "and s.config_snapshot_id=:cfg and " + AUTHORITATIVE_SIGNAL_PREDICATE),
            {"o": org_id, "rc": COMPOSITE_RULE_ID, "cfg": snapshot_id,
             "pack": pack_id, "packv": pack_version,
             "authority_time": eval_time}).fetchall()
        if adj is None:
            adj = _adjacency(c, org_id)

    if fired is not None:      # keep only signals whose rule actually fired this run (not stale-open)
        sigs = [s for s in sigs if (s.rule_id, s.subject_node_id) in fired]

    plans = plan_composites([d.node_id for d in deals], sigs, adj)

    # existing open composites → so we can leave a still-accurate one alone but RESOLVE + re-emit one
    # whose member set has changed (evidence is stamped at emit time and never mutated in place).
    with store.engine.connect() as c:
        existing = {r.subject_node_id: dict(r._mapping)
                    for r in c.execute(text(
            "select signal_id, subject_node_id, evidence, score_inputs, config_snapshot_id "
            "from signals where org_id=:o "
            "and pack_id=:pack and pack_version=:packv "
            "and status='open' and rule_id=:rc"),
            {"o": org_id, "rc": COMPOSITE_RULE_ID,
             "pack": pack_id, "packv": pack_version})}
        valid_existing = {r.signal_id for r in c.execute(text(
            "select s.signal_id from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            " where s.org_id=:o and s.status='open' and s.rule_id=:rc "
            "and s.pack_id=:pack and s.pack_version=:packv "
            "and s.config_snapshot_id=:cfg and " + AUTHORITATIVE_SIGNAL_PREDICATE),
            {"o": org_id, "rc": COMPOSITE_RULE_ID, "cfg": snapshot_id,
             "pack": pack_id, "packv": pack_version,
             "authority_time": eval_time})}

    def _codes(ev):
        ev = ev if isinstance(ev, list) else (json.loads(ev) if ev else [])
        return [e.get("value") for e in ev]

    emitted = 0
    budget_held = 0
    audit_failed = 0
    active: set = set()
    reasoning_store = reasoning_store or ReasoningStore(engine=store.engine)
    planned_deals = {plan["deal_id"] for plan in plans}
    for p in plans:
        prev = existing.get(p["deal_id"])
        previous_inputs = (prev["score_inputs"]
                           if prev and isinstance(prev["score_inputs"], dict)
                           else json.loads(prev["score_inputs"] or "{}") if prev else {})
        if (prev and prev["signal_id"] in valid_existing
                and _codes(prev["evidence"]) == p["codes"]
                and tuple(previous_inputs.get("composite_member_ids") or ())
                == tuple(p["inputs"]["composite_member_ids"])):
            active.add(p["deal_id"])
            continue                                    # unchanged → leave the open composite as-is
        if new_signal_budget is not None and emitted >= max(0, int(new_signal_budget)):
            # The old composite no longer describes the current member set. Retire it, but do not
            # publish a replacement outside the org-wide daily reservation.
            if prev:
                with store.engine.begin() as c:
                    c.execute(text(
                        "update signals set status='resolved' where org_id=:o and signal_id=:id"),
                        {"o": org_id, "id": prev["signal_id"]})
                    c.execute(text(
                        "update cards set state='expired' where org_id=:o and signal_id=:id "
                        "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
                        {"o": org_id, "id": prev["signal_id"]})
            budget_held += 1
            continue
        try:
            execution = _reason_composite(
                org_id=org_id,
                plan=p,
                eval_time=eval_time,
                snapshot_id=snapshot_id,
                graph_version=graph_version,
                mode=execution_mode,
            )
            audit_bundle = persist_execution(store=reasoning_store, execution=execution)
            selected = execution.selected_candidate
            authorized = (execution.authorizes_delivery and selected is not None
                          and selected.play_id == COMPOSITE_PLAY)
        except Exception:
            logger.exception("Layer 4 composite audit failed for %s:%s", org_id, p["deal_id"])
            audit_failed += 1
            continue
        if not authorized:
            if prev:
                with store.engine.begin() as c:
                    c.execute(text(
                        "update signals set status='expired' where org_id=:o and signal_id=:id"),
                        {"o": org_id, "id": prev["signal_id"]})
                    c.execute(text(
                        "update cards set state='expired' where org_id=:o and signal_id=:id "
                        "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
                        {"o": org_id, "id": prev["signal_id"]})
            continue
        with store.engine.begin() as c:
            if prev:                                    # member set changed → resolve the stale one
                c.execute(text(
                    "update signals set status='resolved' where org_id=:o and signal_id=:id"),
                    {"o": org_id, "id": prev["signal_id"]})
                c.execute(text(
                    "update cards set state='expired' where org_id=:o and signal_id=:id "
                    "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
                    {"o": org_id, "id": prev["signal_id"]})
            row = c.execute(text(
                "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, "
                "rule_version, level, "
                "subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
                "config_snapshot_id, reasoning_run_id, reasoning_candidate_id, "
                "reasoning_decision_hash, authority_expires_at, authority_pack_revision, "
                "authority_binding_version) "
                "values (:id,:o,:pack,:packv,:r,:v,:lv,:n,:s,cast(:si as jsonb),:rc,"
                "cast(:ev as jsonb),:p,:et,"
                ":cs,:rr,:candidate,:decision_hash,:expires,:pack_revision,1) "
                "on conflict (org_id,pack_id,pack_version,rule_id,subject_node_id) "
                "where status='open' do nothing "
                "returning signal_id"),
                {"id": new_id("sig"), "o": org_id, "pack": pack_id, "packv": pack_version,
                 "r": COMPOSITE_RULE_ID, "v": 1, "lv": "prescriptive",
                 "n": p["deal_id"], "s": projected_score(selected.utility_bp),
                 "si": json.dumps(p["inputs"], default=str),
                 "rc": COMPOSITE_REASON, "ev": json.dumps(p["evidence"], default=str),
                 "p": COMPOSITE_PLAY, "et": eval_time, "cs": snapshot_id,
                 "rr": audit_bundle["run"]["run_id"],
                 "candidate": audit_bundle["output"]["selected_candidate_id"],
                 "decision_hash": audit_bundle["output"]["decision_hash"],
                 "expires": execution.decision.expires_at,
                 "pack_revision": pack_authority_revision}).first()
        if row:
            emitted += 1
            active.add(p["deal_id"])

    # A compound signal is no longer true once its parent plan disappears.  It is synthetic and
    # therefore is not covered by the legacy rule lifecycle; retire it explicitly here.
    stale = [item["signal_id"] for deal_id, item in existing.items()
             if deal_id not in planned_deals]
    if stale:
        with store.engine.begin() as c:
            c.execute(text(
                "update signals set status='resolved' where org_id=:o and signal_id=any(:ids)"),
                {"o": org_id, "ids": stale})
            c.execute(text(
                "update cards set state='expired' where org_id=:o and signal_id=any(:ids) "
                "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
                {"o": org_id, "ids": stale})
    result = {"emitted": emitted, "active": active, "audit_failed": audit_failed}
    if budget_held:
        result["budget_held"] = budget_held
    return result
