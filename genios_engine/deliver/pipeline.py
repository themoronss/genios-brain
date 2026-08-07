from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_default, make_registry
from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)

from .card_builder import build_draft
from .render import render_copy
from .router import budget_full
from .store import CardStore

# Card presentation pipeline. New cards are built only for validated Layer 5 executions; a raw
# signal can no longer create an independently deliverable object. Layer 5.2 owns all outward
# routing through its execution-bound outbox.


def _open_signals_without_cards(graph, org_id: str,
                                evaluation_time: datetime | None = None) -> list[dict]:
    as_of = authority_time(evaluation_time)
    with graph.engine.connect() as c:
        rows = c.execute(text(
            "select s.signal_id, " + AUTHORITATIVE_REASON_CODE_SQL +
            " as reason_code, 'prescriptive' as level, s.subject_node_id, "
            + AUTHORITATIVE_SCORE_SQL + " as score, " +
            AUTHORITATIVE_SCORE_INPUTS_SQL + " as score_inputs, "
            "coalesce(authority_payload.payload->'evidence', selected_rc.evidence_refs) "
            "as evidence, authority_payload.payload->'facts'->'signals.open' "
            "as composite_members, "
            "selected_rc.play_id as play, s.config_snapshot_id, "
            "authority_cfg.effective as effective_config, "
            "authority_cfg.pack_id, s.authority_expires_at as decision_expires_at, "
            "s.reasoning_run_id, s.reasoning_candidate_id, s.reasoning_decision_hash, "
            "x.execution_id "
            "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            " join executions x on x.org_id=s.org_id and x.signal_id=s.signal_id "
            "and x.closed_at is null and x.state in ('pending','running','waiting','blocked') "
            " left join reasoning_context_payloads authority_payload "
            "on authority_payload.org_id=authority_ctx.org_id and "
            "authority_payload.context_snapshot_id=authority_ctx.context_snapshot_id "
            " left join cards k on k.signal_id=s.signal_id and k.org_id=s.org_id "
            "where s.org_id=:o and s.status='open' and k.card_id is null and " +
            AUTHORITATIVE_SIGNAL_PREDICATE +
            " order by selected_rc.final_utility_bp desc, s.signal_id asc"),
            {"o": org_id, "authority_time": as_of}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for jf in ("score_inputs", "evidence", "composite_members"):
            if isinstance(d.get(jf), str):
                try:
                    d[jf] = json.loads(d[jf])
                except (ValueError, TypeError):
                    d[jf] = {} if jf == "score_inputs" else []
        out.append(d)
    return out


def build_cards_for_org(*, graph, card_store: CardStore, org_id: str, llm=None,
                        registry=None, eval_time: datetime | None = None) -> dict:
    """E0→E1→E3→persist for every open, un-carded signal. Returns delivery counts."""
    eval_time = eval_time or datetime.now(timezone.utc)
    registry = registry or make_registry()
    ensure_default(registry, org_id)
    out = {"built": 0, "already_built": 0, "build_in_progress": 0,
           "llm": 0, "raw_slot": 0, "unrouted": 0,
           "over_budget_no_push": 0,
           "pushed": 0, "agent_pushed": 0}
    from .bands import band
    for sig in _open_signals_without_cards(graph, org_id, eval_time):
        claim_token = card_store.claim_build(
            org_id, sig["signal_id"], eval_time=eval_time)
        if claim_token is None:
            out["build_in_progress"] += 1
            continue
        try:
            effective = sig.pop("effective_config", {})
            if isinstance(effective, str):
                effective = json.loads(effective or "{}")
            if not isinstance(effective, dict):
                continue
            bands_cfg = effective.get("scoring", {}).get("bands")
            budget = int(effective.get("scoring", {}).get("budget_per_user_day", 7))
            draft = build_draft(graph, org_id, sig, effective, eval_time)         # E0
            copy = render_copy(                                                    # E1
                reason_code=draft["_reason_code"], template=draft["_template"],
                facts=draft["_facts"], slots=draft["_slots"], llm=llm,
                cost_sink=graph.record_cost, org_id=org_id)
            # artifact_ready must reflect the REAL render — a raw-slot fallback has an empty body,
            # so Run Play must not advertise a ready draft.
            ready = bool((copy.get("artifact") or {}).get("body"))
            for action in draft["actions"]:
                if action.get("type") == "run_play":
                    action["artifact_ready"] = ready
            draft["_authority"] = {
                "reasoning_run_id": sig["reasoning_run_id"],
                "reasoning_candidate_id": sig["reasoning_candidate_id"],
                "reasoning_decision_hash": sig["reasoning_decision_hash"],
                "config_snapshot_id": sig["config_snapshot_id"],
            }
            draft["_execution_id"] = sig["execution_id"]
            draft["_authority_time"] = eval_time
            over_budget = budget_full(card_store, org_id, draft["assignee"], eval_time, budget)
            if over_budget:
                out["over_budget_no_push"] += 1
            card_id, created = card_store.insert_card(
                draft, copy, build_claim_token=claim_token)
            if card_id is None or not created:
                if card_id is not None:
                    out["already_built"] += 1
                continue
            out["built"] += 1
            out["llm" if copy["render_mode"] == "llm" else "raw_slot"] += 1
            # Agent delivery uses the same execution-linked outbox, policy, retry, dedupe and
            # DeliveryResult path as every other destination. No synchronous side channel here.
            if draft["assignee"] is None:
                out["unrouted"] += 1
            if (band(int(sig["score"]), bands_cfg) in ("high", "critical")
                    and draft["assignee"] and not over_budget
                    and card_store.transition(
                        card_id, org_id, "surfaced", "card.surfaced", cause="push",
                        allowed_from=("queued",))):
                out["pushed"] += 1
        finally:
            card_store.release_build(org_id, sig["signal_id"], claim_token)
    return out
