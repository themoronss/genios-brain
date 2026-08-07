"""/v1/intelligence/* — the active intelligence query (the Ask page + extension on-demand).

Grounding-first Envelope with a graph_version-keyed decision cache: a repeat question on an
unchanged graph returns the stored Envelope with ZERO LLM cost. Credits are charged only here.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.contracts.validators import freeze_mapping, require_identifier
from genios_engine.platform.auth import AuthCtx, get_current_org, require_scope
from genios_engine.platform.cache import get_cache
from genios_engine.platform.canonical import stable_id
from genios_engine.platform.db import lock_tenant_for_mutation
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import (make_graph_store, make_llm_client,
                                           make_pack_registry)
from genios_engine.reason.intelligence import (current_graph_version, normalize_question,
                                               run_query)
from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)
from genios_engine.reason.store import ReasoningStore

router = APIRouter()
_log = get_logger("intelligence")

_graph = make_graph_store()
_llm = make_llm_client()
_registry = make_pack_registry()


class QueryBody(BaseModel):
    module_id: str = "sales"
    query: dict = {}
    facts: dict | None = None
    user_id: str | None = None


# bump when the reasoning logic changes so the decision cache doesn't serve pre-upgrade envelopes.
_REASONER_VERSION = "r4-deterministic-authority"


def _cache_key(org_id: str, module_id: str, question: str, gv: int,
               extra_facts: dict | None = None, config_snapshot_id: str | None = None,
               variant: str = "query", authority_epoch: str = "none") -> str:
    facts = json.dumps(extra_facts or {}, sort_keys=True, separators=(",", ":"), default=str)
    raw = (f"{org_id}|{module_id}|{normalize_question(question)}|{gv}|{authority_epoch}|"
           f"{config_snapshot_id or 'none'}|{variant}|{facts}|{_REASONER_VERSION}")
    return hashlib.sha256(raw.encode()).hexdigest()


def _authority_epoch(org_id: str, evaluation_time: datetime | None = None) -> str:
    """Content hash of the exact, total-ordered authoritative signal set."""
    as_of = authority_time(evaluation_time)
    with _graph.engine.begin() as c:
        rows = c.execute(text(
            "select s.signal_id, s.reasoning_run_id, s.reasoning_candidate_id, "
            "s.reasoning_decision_hash, s.config_snapshot_id, selected_rc.play_id, "
            "selected_rc.final_utility_bp, s.authority_expires_at "
            "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            " where s.org_id=:o and s.status='open' and " +
            AUTHORITATIVE_SIGNAL_PREDICATE +
            " order by s.signal_id, s.reasoning_run_id, s.reasoning_candidate_id"),
            {"o": org_id, "authority_time": as_of}).mappings().all()
    encoded = json.dumps([dict(row) for row in rows], sort_keys=True, separators=(",", ":"),
                         default=str, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_stable_query_inputs(*, org_id: str, module_id: str, graph_version: int,
                                 authority_epoch: str,
                                 config_snapshot_id: str | None) -> None:
    """Reject a mixed read if graph, signal authority, or config changed mid-query."""
    if current_graph_version(_graph, org_id) != graph_version:
        raise HTTPException(409, "the context graph changed while reasoning; please retry")
    if _authority_epoch(org_id) != authority_epoch:
        raise HTTPException(409, "recommendation authority changed while reasoning; please retry")
    if _registry is not None:
        _effective, current_snapshot_id = _registry.effective(org_id, module_id)
        if current_snapshot_id != config_snapshot_id:
            raise HTTPException(409, "the effective configuration changed while reasoning; please retry")


def _persist_decision_envelope(*, org_id: str, module_id: str, question: str,
                               envelope: dict, graph_version: int, cache_key: str,
                               triggered_by: str) -> None:
    """Durably bind the exact returned envelope to its content-derived decision id.

    ``ON CONFLICT DO NOTHING`` is safe only when the held row is byte-for-byte the same semantic
    envelope.  We therefore read it back in the same transaction and fail closed on any collision
    (including a theoretically impossible cross-tenant collision).
    """
    encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str,
                         allow_nan=False)
    try:
        with _graph.engine.begin() as c:
            c.execute(text(
                "insert into decisions (decision_id, org_id, module_id, question, envelope, "
                "confidence, route, graph_version, cache_key, triggered_by) "
                "values (:d, :o, :m, :q, cast(:e as jsonb), :c, :r, :gv, :k, :t) "
                "on conflict (decision_id) do nothing"),
                {"d": envelope["decision_id"], "o": org_id, "m": module_id, "q": question,
                 "e": encoded, "c": envelope["confidence"], "r": envelope["route"],
                 "gv": graph_version, "k": cache_key, "t": triggered_by})
            held = c.execute(text(
                "select org_id, module_id, question, envelope, graph_version, cache_key, "
                "triggered_by from decisions where decision_id=:d"),
                {"d": envelope["decision_id"]}).first()
            if held is None:
                raise RuntimeError("decision insert was not observable")
            held_env = held.envelope if isinstance(held.envelope, dict) else json.loads(held.envelope)
            held_encoded = json.dumps(held_env, sort_keys=True, separators=(",", ":"),
                                      default=str, allow_nan=False)
            if (held.org_id != org_id or held.module_id != module_id or held.question != question
                    or int(held.graph_version or 0) != int(graph_version)
                    or held.cache_key != cache_key or held.triggered_by != triggered_by
                    or held_encoded != encoded):
                raise RuntimeError("decision id is already bound to different semantics")
    except Exception as exc:      # authoritative Layer 4 output must have a durable exact trace
        _log.exception("decision persist failed for %s", org_id)
        raise HTTPException(503, "decision could not be recorded safely; please retry") from exc


# Query spend guard — the ONE credit-billable surface. Monthly credit allowance + a per-minute burst
# cap, checked BEFORE the LLM call (cached queries never reach it → always free). Both fail-open on
# infra errors so a Redis/DB blip never blocks a legitimate query. (Was the gap: spend was recorded
# after the fact, incr_window was defined-but-never-called → unbounded LLM spend / retry loops.)
_CREDIT_LIMIT = {"trial": 100, "startup": 2000, "growth": 10000, "scale": 50000}
_RPM_LIMIT = 20                        # billable intelligence queries / org / minute (burst guard)


def _enforce_query_budget(org_id: str) -> None:
    from datetime import datetime, timezone
    try:                                                    # RPM burst (Noop cache → 0 → no cap)
        n = get_cache().incr_window(f"rpm:iq:{org_id}", 60)
        if n and int(n) > _RPM_LIMIT:
            raise HTTPException(429, "too many queries this minute — retry shortly")
    except HTTPException:
        raise
    except Exception:                                       # noqa: BLE001 — cache blip never blocks
        pass
    try:                                                    # monthly credit allowance
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        with _graph.engine.connect() as c:
            tier = (c.execute(text("select subscription_tier from orgs where id=:o"),
                              {"o": org_id}).scalar() or "trial").lower()
            used = c.execute(text("select count(*) from decisions where org_id=:o and created_at>=:s"),
                             {"o": org_id, "s": month_start}).scalar() or 0
        limit = _CREDIT_LIMIT.get(tier, 100)
        if int(used) >= limit:
            raise HTTPException(402, f"monthly credit limit reached ({limit}) — upgrade or wait for reset")
    except HTTPException:
        raise
    except Exception:                                       # noqa: BLE001 — DB blip never blocks
        pass


@router.post("/v1/intelligence/query")
def intelligence_query(body: QueryBody, org_id: str = Depends(get_current_org)) -> dict:
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    question = str((body.query or {}).get("question") or "").strip()
    if not question:
        raise HTTPException(422, "query.question is required")
    module_id = body.module_id or "sales"
    evaluation_time = datetime.now(timezone.utc)
    gv = current_graph_version(_graph, org_id)
    config_snapshot_id = None
    if _registry is not None:
        _effective, config_snapshot_id = _registry.effective(org_id, module_id)
    authority_epoch = _authority_epoch(org_id, evaluation_time)
    ckey = _cache_key(org_id, module_id, question, gv, body.facts or {}, config_snapshot_id,
                      authority_epoch=authority_epoch)

    # decision cache — same question, unchanged graph → return the stored Envelope, no LLM.
    with _graph.engine.connect() as c:
        hit = c.execute(text("select envelope from decisions where org_id=:o and cache_key=:k "
                             "order by created_at desc limit 1"), {"o": org_id, "k": ckey}).first()
    if hit is not None:
        _require_stable_query_inputs(
            org_id=org_id, module_id=module_id, graph_version=gv,
            authority_epoch=authority_epoch, config_snapshot_id=config_snapshot_id)
        env = hit.envelope if isinstance(hit.envelope, dict) else json.loads(hit.envelope)
        env["cached"] = True
        return env

    _enforce_query_budget(org_id)          # RPM + monthly credit guard before any LLM spend
    env, res = run_query(org_id=org_id, module_id=module_id, question=question,
                         extra_facts=body.facts or {}, store=_graph, llm=_llm,
                         registry=_registry, graph_version=gv, eval_time=evaluation_time)

    # record LLM spend (only the final-synthesis call, if it ran)
    if res is not None:
        try:
            _graph.record_cost(org_id=org_id, model=res.model, purpose="intelligence_query",
                               input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                               success=res.ok, error=getattr(res, "error", None))
        except Exception:      # noqa: BLE001 — never let cost logging break the answer
            _log.warning("intelligence cost log failed for %s", org_id)

    _require_stable_query_inputs(
        org_id=org_id, module_id=module_id, graph_version=gv,
        authority_epoch=authority_epoch, config_snapshot_id=config_snapshot_id)

    _persist_decision_envelope(
        org_id=org_id, module_id=module_id, question=question, envelope=env,
        graph_version=gv, cache_key=ckey, triggered_by="query")

    return env


# ── proactive: /v1/insights — the engine's already-computed recommendations (L5 cards) mapped into
# the shape the extension + dashboard expect. Cheap: no LLM at read time, cards were built by L3→L5.
def _band_label(score) -> str:
    s = float(score) if score is not None else 0.0
    return "high" if s >= 0.7 else ("medium" if s >= 0.4 else "low")


def _insight_type(band: str | None) -> str:
    return "risk" if (band or "").lower() in ("now", "urgent", "high", "today") else "opportunity"


# 'surfaced' and 'claimed' ARE open states — the engine writes them on every push and
# agent claim, and this tuple once omitted them: pushed HIGH/CRITICAL cards (the ones
# that matter most) were invisible in the feed while low-priority queued ones showed.
# 'delivered' is kept for legacy rows.
_OPEN_STATES = ("queued", "surfaced", "delivered", "snoozed", "claimed")
_RESOLVED_STATES = ("acted", "resolved")
# A card is "reply-shaped" (Draft-able) when it's about a specific person AND the wording is about
# owing/sending a message — vs a risk/advice card, which gets Advice, not a pointless draft.
_DRAFT_KW = ("reply", "respond", "follow up", "follow-up", "reach out", "message", "email",
             "waiting on", "waiting for", "owed", "get back", "send ", "unanswered", "ping")


def _wants_draft(entity, head: str, sit: str) -> bool:
    if not entity:
        return False
    t = f"{head} {sit}".lower()
    return any(k in t for k in _DRAFT_KW)


# Real source labels for context_tags (app:gmail → "Gmail"). This is the PROVENANCE the card
# actually carries — not the pack_id, which was mislabeling every card "sales".
_APP_LABEL = {"gmail": "Gmail", "gcal": "Calendar", "calendar": "Calendar", "hubspot": "HubSpot",
              "notion": "Notion", "outlook": "Outlook", "stripe": "Stripe", "slack": "Slack"}


def _provenance(context_tags) -> tuple[list[str], list[str]]:
    """From a card's context_tags (['app:gmail','url_domain:x.com', …]) → (source apps, company
    domains). The apps are the REAL 'where it came from' (Gmail/HubSpot); domains identify the org."""
    tags = context_tags if isinstance(context_tags, list) else []
    apps, domains = [], []
    for t in tags:
        if not isinstance(t, str):
            continue
        if t.startswith("app:"):
            a = t.split(":", 1)[1].lower()
            apps.append(_APP_LABEL.get(a, a.title()))
        elif t.startswith("url_domain:"):
            domains.append(t.split(":", 1)[1])
    return apps, domains


# sales_v1's rules are a mix: some are genuinely about a DEAL (pipeline/pricing/competitor), others
# are generic relationship hygiene (an overdue reply, a missed follow-up) that fire for ANY contact,
# sales or not. The pack_id can't tell them apart (it's "sales" for both) — the reason_code can.
_DEAL_REASON_CODES = {
    "stalled_deal", "buying_signal", "cooling_deal", "single_threaded_deal",
    "competitor_in_live_deal", "going_dark_after_proposal", "deal_sentiment_negative",
    "objection_open", "deal_health",
    # v1.5.0–1.7.0 deep lifecycle rules — categorise as sales (else they'd show as 'general')
    "pricing_objection", "verbal_yes_not_closed", "contract_requested", "security_review_pending",
    "champion_left", "budget_freeze", "discount_pressure", "legal_in_review", "timeline_slip",
    "demo_requested", "proposal_no_response", "closed_lost_risk",
}


def _category(reason_code: str | None) -> str:
    return "sales" if reason_code in _DEAL_REASON_CODES else "general"


# Manager mode — the card's button says the SPECIFIC move, not a generic "Advice". Keyed off the
# rule's `play` (already stored in a card's actions[] as run_play.play_id), so it's one dict shared
# by every pack instead of a per-reason_code table that drifts out of sync with the packs.
_PLAY_LABEL = {
    "follow_up": "Re-engage", "re_engage": "Re-engage", "handle_objection": "Handle objection",
    "advance_deal": "Advance deal", "multi_thread": "Widen contacts",
    "defend_position": "Defend position", "review_deal": "Review deal",
    "deliver_commitment": "Deliver it", "reply": "Reply now", "send_recap": "Send recap",
}


def _action_label(actions) -> str | None:
    if not isinstance(actions, list):
        return None
    for a in actions:
        if isinstance(a, dict) and a.get("type") == "run_play":
            return _PLAY_LABEL.get(a.get("play_id"))
    return None


@router.get("/v1/insights")
def list_insights(limit: int = 50, state: str = "open",
                  ctx: AuthCtx = Depends(require_scope("insights.read"))) -> dict:
    """Extension feed. state=open (default) → cards needing action; state=resolved → acted/resolved
    (the inbox's Resolved tab). Same card shape either way."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    org_id = ctx.org_id
    states = _RESOLVED_STATES if state == "resolved" else _OPEN_STATES
    with _graph.engine.begin() as c:
        # join through the signal to the subject node → the contact/deal NAME the extension needs for
        # page-matching + resolving Draft/Advice. Left joins so a card without a node still returns.
        params = {"o": org_id, "states": list(states),
                  "l": max(1, min(int(limit), 100))}
        seat_filter = ""
        if ctx.scopes is not None:
            params["assignee"] = ctx.actor_id or ctx.agent_id
            seat_filter = " and k.assignee=:assignee "
        if state == "resolved":
            # Resolved is an audit/history tab, not an execution surface. Its records intentionally
            # survive decision expiry and later graph/config changes.
            rows = c.execute(text(
                "select k.card_id, k.headline, k.situation, k.score, k.domain, k.urgency_band, "
                "k.context_tags, k.created_at, k.actions, n.display_name as entity, s.reason_code "
                "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
                "left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=k.org_id "
                "and n.valid_to is null where k.org_id=:o and k.state = any(:states) " +
                seat_filter +
                "order by k.score desc nulls last, k.created_at desc, k.card_id limit :l"),
                params).fetchall()
        else:
            params["authority_time"] = datetime.now(timezone.utc)
            lock_tenant_for_mutation(c, org_id)
            c.execute(text(
                "select graph_version from graph_versions where org_id=:o for share"),
                {"o": org_id})
            rows = c.execute(text(
                "select k.card_id, k.headline, k.situation, " + AUTHORITATIVE_SCORE_SQL +
                " as score, k.domain, k.urgency_band, k.context_tags, k.created_at, k.actions, "
                "n.display_name as entity, " + AUTHORITATIVE_REASON_CODE_SQL + " as reason_code "
                "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id " +
                AUTHORITATIVE_SIGNAL_JOINS +
                "left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=k.org_id "
                "and n.valid_to is null "
                "where k.org_id=:o and k.state = any(:states) and s.status='open' " +
                seat_filter +
                "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE + " "
                "order by selected_rc.final_utility_bp desc, k.created_at desc, "
                "k.card_id limit :l for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,"
                "authority_cfg,authority_pack"),
                params).fetchall()
            # The impression and its current authority/state proof commit together. It is an
            # audited learning input, not a best-effort analytics ping.
            if rows:
                c.execute(text(
                    "insert into card_events (id, card_id, org_id, kind, cause, actor_id) "
                    "select 'cevs_' || k.card_id, k.card_id, :o, 'card.surfaced', 'pull', 'extension' "
                    "from cards k where k.org_id=:o and k.card_id = any(:ids) "
                    "and not exists (select 1 from card_events ce where ce.org_id=k.org_id "
                    "and ce.card_id=k.card_id and ce.kind='card.surfaced') on conflict do nothing"),
                    {"o": org_id, "ids": [r.card_id for r in rows]})
    insights = []
    for r in rows:
        head, sit = (r.headline or "Recommendation"), (r.situation or "")
        sc = float(r.score) if r.score is not None else 50.0
        sc01 = round(sc / 100, 3) if sc > 1 else round(sc, 3)   # card score is 0-100 → normalize 0-1
        priority = "high" if r.urgency_band in ("high", "critical") else "medium"
        apps, domains = _provenance(r.context_tags)
        actions = r.actions if isinstance(r.actions, list) else json.loads(r.actions or "[]")
        insights.append({
            "id": r.card_id, "type": _insight_type(r.urgency_band),
            "priority": priority,                # extension fires notifications on priority=='high'
            "title": head,                       # extension card + notification title
            "contact_name": r.entity,            # extension page-match + Draft/Advice target
            "genios_view": (f"{head} — {sit}" if sit else head),
            "detail": sit, "memory_view": head,
            "action_label": _action_label(actions),   # manager mode: the specific move (e.g. "Reply now")
            "confidence_score": sc01,
            # category from the fired RULE (reason_code), not r.domain (the pack_id, always
            # "sales" — one pack exists — which mislabeled every card regardless of content).
            "scores": {"confidence": _band_label(sc01), "category": _category(r.reason_code)},
            "draft_needed": _wants_draft(r.entity, head, sit),   # reply-shaped → show the Draft hero
            "source_tools": apps,                # real provenance (Gmail/HubSpot/Calendar)
            "sources": domains,                  # company domains from context_tags
            "generated_at": r.created_at.isoformat() if r.created_at else "",
        })
    return {"insights": insights, "count": len(insights)}


@router.get("/v1/insights/stats")
def insight_stats(days: int = 7, org_id: str = Depends(get_current_org)) -> dict:
    """Dashboard ActionsCard — honest counts from the cards + card_events ledger (ROI / intervention
    rate stay null until the feedback→L6 loop of Phase 4 records outcomes)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    with _graph.engine.connect() as c:
        fired = int(c.execute(text("select count(*) from cards where org_id=:o"),
                              {"o": org_id}).scalar() or 0)
        acted = int(c.execute(text(
            "select count(*) from card_events where org_id=:o and kind in "
            "('run_play','do_it_myself','card.acted','card.done')"), {"o": org_id}).scalar() or 0)
    return {"insights_fired": fired, "actions_taken": acted, "outcomes_recorded": 0,
            "value_recovered_inr": 0, "intervention_rate": None,
            "headline": (f"{fired} insight(s) surfaced" if fired else "No insights yet")}


# ── Phase 4: explain (derivation trace) + feedback (→ L6 via card_events) ──────────
@router.get("/v1/intelligence/decisions/{decision_id}/explain")
def explain_decision(decision_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """The audit trace of a stored decision — which rules fired, at what confidence, as-of which
    graph version. Built from the derivation we persisted with the Envelope."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    with _graph.engine.connect() as c:
        row = c.execute(text("select envelope from decisions where decision_id=:d and org_id=:o"),
                        {"d": decision_id, "o": org_id}).first()
    if row is None:
        raise HTTPException(404, "decision not found")
    env = row.envelope if isinstance(row.envelope, dict) else json.loads(row.envelope)
    deriv = env.get("derivation", []) or []
    run_ids = tuple(dict.fromkeys(d.get("reasoning_run_id") for d in deriv
                                  if d.get("reasoning_run_id")))
    bundles: list[tuple[str, dict]] = []
    missing_run_ids: list[str] = []
    reasoning_store = ReasoningStore(engine=_graph.engine)
    for run_id in run_ids:
        try:
            bundle = reasoning_store.load_bundle(org_id=org_id, run_id=run_id)
            if bundle is None:
                missing_run_ids.append(run_id)
            else:
                bundles.append((run_id, bundle))
        except Exception:  # legacy decisions remain explainable from their stored envelope
            missing_run_ids.append(run_id)
            _log.warning("reasoning trace load failed for %s:%s", org_id, run_id)
    rules = [{"id": d.get("rule_id"), "priority": i + 1,
              "matched_facts": d.get("matched_facts", {}), "conclusion": d.get("conclusion", ""),
              "reasoning_run_id": d.get("reasoning_run_id")}
             for i, d in enumerate(deriv)]
    if bundles:
        run_views = []
        all_sources = []
        all_checks = []
        confidence_by_run = {}
        for run_id, bundle in bundles:
            results = bundle.get("reasoner_results") or []
            checks = bundle.get("candidate_checks") or []
            source_manifest = (bundle.get("context_snapshot") or {}).get("source_manifest") or []
            decision_path = " → ".join(item.get("reasoner_id", "") for item in results)
            confidence_bp = int((bundle.get("output") or {}).get("confidence_bp") or 0)
            confidence_by_run[run_id] = confidence_bp
            tagged_sources = [({**item, "reasoning_run_id": run_id}
                               if isinstance(item, dict)
                               else {"value": item, "reasoning_run_id": run_id})
                              for item in source_manifest]
            tagged_checks = [({**item, "reasoning_run_id": run_id}
                              if isinstance(item, dict)
                              else {"value": item, "reasoning_run_id": run_id})
                             for item in checks]
            all_sources.extend(tagged_sources)
            all_checks.extend(tagged_checks)
            run_views.append({
                "reasoning_run_id": run_id,
                "decision_path": decision_path,
                "source_facts": source_manifest,
                "confidence_basis_points": confidence_bp,
                "constraints_checked": checks,
            })
        paths = [view["decision_path"] for view in run_views]
        aggregate_path = (paths[0] if len(paths) == 1 else " | ".join(
            f"{view['reasoning_run_id']}[{view['decision_path']}]" for view in run_views))
        response = {
            "decision_id": decision_id, "org_id": org_id,
            "reasoning_run_ids": list(run_ids), "reasoning_runs": run_views,
            "missing_reasoning_run_ids": missing_run_ids,
            "decision_path": aggregate_path, "source_facts": all_sources,
            "rules_fired": rules, "edge_path": [],
            # The public envelope confidence is the deterministic aggregate used by the query
            # adapter.  Per-run basis points remain explicit; we never invent a multi-run formula.
            "confidence_overall": env.get("confidence", 0),
            "confidence_breakdown": {"deterministic_basis_points_by_run": confidence_by_run},
            "constraints_checked": all_checks, "as_of": env.get("as_of", {}),
        }
        if len(run_ids) == 1:  # backward-compatible singular alias only when it is unambiguous
            response["reasoning_run_id"] = run_ids[0]
        return response
    return {"decision_id": decision_id, "org_id": org_id,
            "reasoning_run_ids": list(run_ids), "reasoning_runs": [],
            "missing_reasoning_run_ids": missing_run_ids,
            "decision_path": " → ".join(d.get("conclusion", "") for d in deriv) or "direct",
            "source_facts": [], "rules_fired": rules, "edge_path": [],
            "confidence_overall": env.get("confidence", 0),
            "confidence_breakdown": {"grounding": env.get("confidence", 0)},
            "constraints_checked": [], "as_of": env.get("as_of", {})}


class FeedbackBody(BaseModel):
    user_id: str | None = None
    action: str
    decision_id: str | None = None
    insight_id: str | None = None
    edit_diff: dict | None = None


# Map judgment-bearing extension verbs to the canonical cause vocabulary L6 reads.  Snooze is the
# deliberate exception: it remains an idempotent timing audit signal and never enters the versioned
# verdict cohort.  Previously thumbs logged kind='wrong'/'helpful' with no cause, making every
# extension judgment invisible to the calibration loop.
_FB_CAUSE = {"thumbs_up": "do_it_myself", "edit": "do_it_myself",
             "thumbs_down": "wrong", "never_show": "wrong", "snooze": "snooze"}
_FB_REASON = {"thumbs_down": "not_relevant", "never_show": "not_relevant",
              "snooze": "bad_timing"}


@router.post("/v1/intelligence/feedback")
def intelligence_feedback(
        body: FeedbackBody,
        ctx: AuthCtx = Depends(require_scope("feedback.write"))) -> dict:
    """Human feedback on a recommendation.

    Judgment-bearing actions version the card's canonical L6 verdict (cause + closed reason);
    timing-only snooze writes an idempotent audit event and cannot lower recommendation quality.
    Returns the correction id.
    """
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    if body.action not in _FB_CAUSE:
        raise HTTPException(422, "unsupported feedback action")
    if not body.insight_id or body.decision_id is not None:
        raise HTTPException(
            422,
            "feedback requires exactly one supported target: insight_id",
        )
    org_id = ctx.org_id
    actor_id = ctx.actor_id or ctx.agent_id or "authenticated_principal"
    fid = stable_id("fb", {
        "org_id": org_id,
        "card_id": body.insight_id or "",
        "decision_id": body.decision_id or "",
    })
    routed = False
    changed = False
    verdict_version = None
    if body.insight_id:      # an insight IS a card → bind feedback to its frozen authority
        detail = dict(body.edit_diff or {})
        raw_preference = detail.get("preference")
        organization_authorized = False
        if raw_preference is not None:
            if body.action != "edit":
                raise HTTPException(422, "structured preference requires the edit action")
            if not isinstance(raw_preference, dict):
                raise HTTPException(422, "preference must be an object")
            allowed = {"key", "value", "scope", "category"}
            if set(raw_preference) - allowed:
                raise HTTPException(422, "preference contains unsupported fields")
            if set(raw_preference) != allowed:
                raise HTTPException(422, "preference requires key, value, scope and category")
            try:
                key = require_identifier(raw_preference["key"], "preference key")
                category = require_identifier(raw_preference["category"], "preference category")
                freeze_mapping({"value": raw_preference["value"]})  # canonical/float validation
                value = raw_preference["value"]
            except (TypeError, ValueError) as exc:
                raise HTTPException(422, str(exc)) from exc
            scope = raw_preference["scope"]
            if scope not in {"user", "organization"}:
                raise HTTPException(422, "preference scope must be user or organization")
            if scope == "organization" and ctx.scopes is not None:
                raise HTTPException(403, "organization preference requires owner authority")
            organization_authorized = scope == "organization" and ctx.scopes is None
            detail["preference"] = {"key": key, "value": value, "scope": scope,
                                    "category": category}
        if body.action in _FB_REASON:
            # Relevance/fact reasons enter the precision denominator; timing remains neutral.
            detail["reason"] = _FB_REASON[body.action]
        try:
            encoded_detail = json.dumps(
                detail, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, "feedback detail must be valid finite JSON") from exc
        if len(encoded_detail.encode("utf-8")) > 16_384:
            raise HTTPException(413, "feedback detail is too large")
        as_of = authority_time()
        with _graph.engine.begin() as c:
            # Feedback changes future scoring. Bind it to a currently actionable audited card and
            # hold the graph/config proof stable until the idempotent ledger write commits.
            lock_tenant_for_mutation(c, org_id)
            c.execute(text(
                "select graph_version from graph_versions where org_id=:o for share"),
                {"o": org_id})
            card = c.execute(text(
                "select k.card_id, k.assignee, authority_cfg.pack_id, "
                "authority_cfg.effective->>'version' as pack_version, "
                "s.authority_pack_revision, "
                "rr.capability_id, rr.capability_version, "
                "regexp_replace(rr.capability_id, '^.*\\.', '') as rule_id "
                "from cards k "
                "join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
                + AUTHORITATIVE_SIGNAL_JOINS +
                " where k.card_id=:card and k.org_id=:o "
                "and k.state in ('queued','surfaced','snoozed','delivered') "
                "and k.expires_at > :authority_time and s.status='open' and "
                + AUTHORITATIVE_SIGNAL_PREDICATE +
                " for update of k, s for share of rr, ro, selected_rc, rcap, authority_ctx, "
                "authority_cfg, authority_pack"),
                {"card": body.insight_id, "o": org_id,
                 "authority_time": as_of}).first()
            if card is None:
                raise HTTPException(409, "insight is expired, claimed, revoked, or unauthorized")
            if (ctx.scopes is not None and card.assignee is not None
                    and card.assignee not in {actor_id, ctx.agent_id}):
                raise HTTPException(403, "insight is assigned to a different seat")

            cause = _FB_CAUSE[body.action]
            # Timing feedback is deliberately not a verdict on the rule. Keep one idempotent
            # audit event, but do not put it into the calibration cohort.
            if cause == "snooze":
                event_id = stable_id("cev", {
                    "org_id": org_id, "card_id": body.insight_id,
                    "source": "intelligence.feedback", "action": body.action,
                })
                inserted = c.execute(text(
                    "insert into card_events "
                    "(id,card_id,org_id,kind,cause,actor_id,detail,occurred_at) "
                    "values (:id,:card,:o,'human.feedback_signal',:cause,:actor,"
                    "cast(:d as jsonb),:at) "
                    "on conflict (id) do nothing returning id"),
                    {"id": event_id, "card": body.insight_id, "o": org_id,
                     "cause": cause, "actor": actor_id, "d": encoded_detail,
                     "at": as_of}).first()
                fid = event_id
                changed = inserted is not None
            else:
                reason = detail.get("reason") if cause == "wrong" else None
                inserted = c.execute(text(
                    "insert into card_feedback_verdicts "
                    "(feedback_id,org_id,card_id,pack_id,pack_version,authority_pack_revision,"
                    "capability_id,"
                    "capability_version,rule_id,cause,reason,detail,actor_id,verdict_version,"
                    "occurred_at) "
                    "values (:id,:o,:card,:p,:pv,:pr,:cap,:capv,:r,:cause,:reason,"
                    "cast(:d as jsonb),:actor,1,:at) "
                    "on conflict (org_id,card_id) do nothing returning verdict_version"),
                    {"id": fid, "o": org_id, "card": body.insight_id,
                     "p": card.pack_id, "pv": card.pack_version,
                     "pr": int(card.authority_pack_revision),
                     "cap": card.capability_id, "capv": card.capability_version,
                     "r": card.rule_id, "cause": cause, "reason": reason,
                     "d": encoded_detail, "actor": actor_id, "at": as_of}).first()
                if inserted is not None:
                    verdict_version = int(inserted.verdict_version)
                    changed = True
                else:
                    updated = c.execute(text(
                        "update card_feedback_verdicts set cause=:cause,reason=:reason,"
                        "detail=cast(:d as jsonb),actor_id=:actor,"
                        "verdict_version=verdict_version+1,occurred_at=:at "
                        "where org_id=:o and card_id=:card and "
                        "((cause,reason,detail) is distinct from "
                        "(:cause,:reason,cast(:d as jsonb)) or ("
                        ":owner and cast(:d as jsonb)->'preference'->>'scope'='organization' "
                        "and not coalesce((select r.organization_authorized "
                        "from card_feedback_revisions r where r.org_id=:o "
                        "and r.card_id=:card order by r.verdict_version desc limit 1),false))) "
                        "returning feedback_id,verdict_version"),
                        {"o": org_id, "card": body.insight_id, "cause": cause,
                         "reason": reason, "d": encoded_detail, "actor": actor_id,
                         "owner": organization_authorized, "at": as_of}).first()
                    if updated is not None:
                        fid = updated.feedback_id
                        verdict_version = int(updated.verdict_version)
                        changed = True
                    else:
                        existing = c.execute(text(
                            "select feedback_id,verdict_version from card_feedback_verdicts "
                            "where org_id=:o and card_id=:card"),
                            {"o": org_id, "card": body.insight_id}).first()
                        if existing is None:
                            raise RuntimeError("feedback verdict disappeared while card was locked")
                        fid = existing.feedback_id
                        verdict_version = int(existing.verdict_version)
                if changed:
                    revision_id = stable_id("fbrev", {
                        "feedback_id": fid, "verdict_version": verdict_version})
                    c.execute(text(
                        "insert into card_feedback_revisions "
                        "(revision_id,feedback_id,org_id,card_id,verdict_version,cause,reason,"
                        "detail,actor_id,occurred_at,organization_authorized) values "
                        "(:rid,:fid,:o,:card,:v,:cause,:reason,cast(:d as jsonb),:actor,"
                        ":at,:owner)"),
                        {"rid": revision_id, "fid": fid, "o": org_id,
                         "card": body.insight_id, "v": verdict_version, "cause": cause,
                         "reason": reason, "d": encoded_detail, "actor": actor_id,
                         "owner": organization_authorized, "at": as_of})
        routed = True
    return {"feedback_id": fid,
            "correction_id": fid if body.action in ("thumbs_down", "never_show", "edit") else None,
            "routed_to_g_i_3": routed, "changed": changed,
            "verdict_version": verdict_version}


# ── extension parity: auth-derived-org /v1/* wrappers (the extension auths with an API key, so it
# can't use the dashboard's /api/org/{org}/* path-scoped routes). Thin over existing logic. ─────────

def _card_event(org_id: str, card_id: str, kind: str, detail: dict) -> bool:
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    try:
        with _graph.engine.begin() as c:
            lock_tenant_for_mutation(c, org_id)
            owns = c.execute(text("select 1 from cards where card_id=:c and org_id=:o"),
                             {"c": card_id, "o": org_id}).first()
            if owns is None:
                return False
            c.execute(text("insert into card_events (id, card_id, org_id, kind, actor_id, detail) "
                           "values (:i,:c,:o,:k,'extension',cast(:d as jsonb))"),
                      {"i": new_id("cev"), "c": card_id, "o": org_id, "k": kind,
                       "d": json.dumps(detail or {}, default=str)})
        return True
    except Exception:      # noqa: BLE001
        _log.warning("card_event %s failed for %s", kind, org_id)
        return False


@router.post("/v1/insights/{insight_id}/dismiss")
def dismiss_insight(insight_id: str,
                    ctx: AuthCtx = Depends(require_scope("cards.act"))) -> dict:
    """Extension dismiss — expire the card + log the event (feeds L6's ignore-rate)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    org_id = ctx.org_id
    actor_id = ctx.actor_id or ctx.agent_id or "authenticated_principal"
    as_of = authority_time()
    with _graph.engine.begin() as c:
        lock_tenant_for_mutation(c, org_id)
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        card = c.execute(text(
            "select k.assignee from cards k join signals s "
            "on s.signal_id=k.signal_id and s.org_id=k.org_id " +
            AUTHORITATIVE_SIGNAL_JOINS +
            "where k.card_id=:card and k.org_id=:o and s.status='open' "
            "and k.state in ('queued','surfaced','snoozed','delivered') "
            "and k.expires_at>:authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE +
            " for update of k,s for share of rr,ro,selected_rc,rcap,authority_ctx,"
            "authority_cfg,authority_pack"),
            {"card": insight_id, "o": org_id, "authority_time": as_of}).first()
        if card is None:
            raise HTTPException(409, "insight is no longer actionable")
        if (ctx.scopes is not None and card.assignee is not None
                and card.assignee not in {actor_id, ctx.agent_id}):
            raise HTTPException(403, "insight is assigned to a different seat")
        c.execute(text(
            "update cards set state='expired' where card_id=:card and org_id=:o"),
            {"card": insight_id, "o": org_id})
        event_id = stable_id("cev", {"org_id": org_id, "card_id": insight_id,
                                     "kind": "card.dismissed"})
        c.execute(text(
            "insert into card_events (id,card_id,org_id,kind,cause,actor_id,detail) "
            "values (:id,:card,:o,'card.dismissed','extension',:actor,"
            "'{\"via\":\"extension\"}'::jsonb) on conflict (id) do nothing"),
            {"id": event_id, "card": insight_id, "o": org_id, "actor": actor_id})
    return {"ok": True, "dismissed": True}


class OutcomeBody(BaseModel):
    outcome: str


@router.post("/v1/insights/{insight_id}/outcome")
def insight_outcome(insight_id: str, body: OutcomeBody,
                    ctx: AuthCtx = Depends(require_scope("feedback.write"))) -> dict:
    org_id = ctx.org_id
    actor_id = ctx.actor_id or ctx.agent_id or "authenticated_principal"
    outcome = body.outcome.strip()
    if not outcome or len(outcome) > 128:
        raise HTTPException(422, "outcome must be between 1 and 128 characters")
    with _graph.engine.begin() as c:
        lock_tenant_for_mutation(c, org_id)
        card = c.execute(text(
            "select assignee from cards where card_id=:card and org_id=:o for share"),
            {"card": insight_id, "o": org_id}).first()
        if card is None:
            raise HTTPException(404, "insight not found")
        if (ctx.scopes is not None and card.assignee is not None
                and card.assignee not in {actor_id, ctx.agent_id}):
            raise HTTPException(403, "insight is assigned to a different seat")
        event_id = stable_id("cev", {"org_id": org_id, "card_id": insight_id,
                                     "kind": "outcome", "outcome": outcome})
        c.execute(text(
            "insert into card_events (id,card_id,org_id,kind,cause,actor_id,detail) "
            "values (:id,:card,:o,'outcome','extension',:actor,cast(:d as jsonb)) "
            "on conflict (id) do nothing"),
            {"id": event_id, "card": insight_id, "o": org_id, "actor": actor_id,
             "d": json.dumps({"outcome": outcome, "via": "extension"})})
    return {"ok": True, "outcome": outcome, "event_id": event_id}


class HandoffBody(BaseModel):
    draft: str | None = None          # optional reviewed draft/action text to execute
    instruction: str | None = None    # or a free-form "what to do"


@router.post("/v1/insights/{insight_id}/handoff")
def handoff_insight(insight_id: str, body: HandoffBody | None = None,
                    ctx: AuthCtx = Depends(require_scope("actions.handoff"))) -> dict:
    """Fail-closed boundary for external execution.

    The former implementation broadcast caller-authored instructions to every webhook and could
    duplicate irreversible work on retry. Handoff stays disabled until a single-agent claim,
    approval artifact and transactional outbox/idempotency protocol are implemented.
    """
    del insight_id, body, ctx
    raise HTTPException(
        501,
        "executor handoff is disabled until the idempotent single-executor approval protocol is available",
    )


@router.get("/v1/morning-brief")
def morning_brief_v1(org_id: str = Depends(get_current_org)) -> dict:
    from genios_engine.api import workspace_routes as W
    return W.morning_brief(org_id, org=org_id)


@router.get("/v1/tasks")
def list_tasks_v1(status: str = "open", org_id: str = Depends(get_current_org)) -> dict:
    from genios_engine.api import workspace_routes as W
    return W.list_tasks(org_id, status=status, org=org_id)


class TaskCreateV1(BaseModel):
    text: str
    target_entity: str | None = None


@router.post("/v1/tasks")
def create_task_v1(body: TaskCreateV1, org_id: str = Depends(get_current_org)) -> dict:
    from genios_engine.api import workspace_routes as W
    return W.create_task(org_id, W.TaskCreate(text=body.text, target_entity=body.target_entity),
                         org=org_id)


class TaskUpdateV1(BaseModel):
    status: str


@router.patch("/v1/tasks/{task_id}")
def update_task_v1(task_id: str, body: TaskUpdateV1,
                   org_id: str = Depends(get_current_org)) -> dict:
    from genios_engine.api import workspace_routes as W
    return W.update_task(org_id, task_id, W.TaskUpdate(status=body.status), org=org_id)


# ── Phase 5: extension — analyze (on-demand recommendation) + draft (reply) ────────
def _resolve_contact_facts(org_id: str, contact: str):
    with _graph.engine.connect() as c:
        node = c.execute(text(
            "select node_id, display_name, node_type from graph_nodes where org_id=:o "
            "and valid_to is null and (lower(display_name)=lower(:n) or lower(canonical_key)=lower(:n) "
            "or display_name ilike :like) order by (lower(display_name)=lower(:n)) desc, "
            "length(display_name) asc, lower(display_name) asc, node_id asc limit 1"),
            {"o": org_id, "n": contact, "like": f"%{contact}%"}).first()
        facts = {}
        if node is not None:
            for f in c.execute(text("select field, value from graph_facts where org_id=:o "
                                    "and subject_node_id=:n and valid_to is null and status='active' "
                                    "order by occurred_at desc nulls last, field asc, "
                                    "fact_version_id asc limit 20"),
                               {"o": org_id, "n": node.node_id}):
                facts.setdefault(f.field, str(f.value).strip('"'))
    return node, facts


_deep_llm_cache: dict = {}


def _deep_llm():
    """Sonnet client for `deep=true` analysis (default is Haiku). Built lazily, cached; None if no
    key is configured (then analyze falls back to the standard client)."""
    if "c" not in _deep_llm_cache:
        try:
            from genios_engine.context.llm.client import LLMClient
            from genios_engine.platform.config import get_settings
            s = get_settings()
            _deep_llm_cache["c"] = (LLMClient(api_key=s.anthropic_api_key, model="claude-sonnet-5")
                                    if s.use_real_llm and s.anthropic_api_key else None)
        except Exception:      # noqa: BLE001
            _deep_llm_cache["c"] = None
    return _deep_llm_cache["c"]


@router.get("/v1/intelligence/analyze")
def analyze_contact(contact: str, deep: bool = False, situation: str = "",
                    org_id: str = Depends(get_current_org)) -> dict:
    """Extension on-demand: for the contact the user is looking at, the next-best-action — returned
    in the insight shape the extension card renders. `deep=true` uses a stronger model (Sonnet)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    evaluation_time = datetime.now(timezone.utc)
    gv = current_graph_version(_graph, org_id)
    q = (situation or "").strip() or f"What is the next best action for {contact}?"
    full_question = f"{q} (contact: {contact})"
    config_snapshot_id = None
    if _registry is not None:
        _effective, config_snapshot_id = _registry.effective(org_id, "sales")
    authority_epoch = _authority_epoch(org_id, evaluation_time)
    ckey = _cache_key(
        org_id, "sales", full_question, gv, {}, config_snapshot_id,
        variant="analyze:deep" if deep else "analyze:standard",
        authority_epoch=authority_epoch)
    with _graph.engine.connect() as c:
        hit = c.execute(text("select envelope from decisions where org_id=:o and cache_key=:k "
                             "order by created_at desc limit 1"), {"o": org_id, "k": ckey}).first()
    res = None
    needs_persist = False
    if hit is not None:
        _require_stable_query_inputs(
            org_id=org_id, module_id="sales", graph_version=gv,
            authority_epoch=authority_epoch, config_snapshot_id=config_snapshot_id)
        env = hit.envelope if isinstance(hit.envelope, dict) else json.loads(hit.envelope)
    else:
        _enforce_query_budget(org_id)
        llm = (_deep_llm() or _llm) if deep else _llm       # deep → Sonnet
        env, res = run_query(
            org_id=org_id, module_id="sales", question=full_question, extra_facts={},
            store=_graph, llm=llm, registry=_registry, graph_version=gv,
            triggered_by="analyze", eval_time=evaluation_time)
        needs_persist = True
    if res is not None:
        try:
            _graph.record_cost(org_id=org_id, model=res.model, purpose="intelligence_analyze",
                               input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                               success=res.ok, error=getattr(res, "error", None))
        except Exception:      # noqa: BLE001
            pass
    _require_stable_query_inputs(
        org_id=org_id, module_id="sales", graph_version=gv,
        authority_epoch=authority_epoch, config_snapshot_id=config_snapshot_id)
    if needs_persist:
        _persist_decision_envelope(
            org_id=org_id, module_id="sales", question=full_question, envelope=env,
            graph_version=gv, cache_key=ckey, triggered_by="analyze")
    # real provenance: which connected tool(s) actually fed THIS contact's facts (was hardcoded "Gmail")
    _node, _ = _resolve_contact_facts(org_id, contact)
    src_tools: list[str] = []
    if _node is not None:
        try:
            _TL = {"gmail": "Gmail", "gcal": "Calendar", "hubspot": "HubSpot", "notion": "Notion",
                   "jira": "Jira", "stripe": "Stripe", "human": "You"}
            with _graph.engine.connect() as c:
                src_tools = [_TL.get(r.source, (r.source or "").title()) for r in c.execute(text(
                    "select distinct sr.source from graph_source_refs sr join graph_facts f "
                    "on f.fact_version_id=sr.fact_version_id and f.org_id=sr.org_id "
                    "where sr.org_id=:o and f.subject_node_id=:n and f.valid_to is null "
                    "and sr.source is not null order by sr.source asc limit 5"),
                    {"o": org_id, "n": _node.node_id})]
        except Exception:      # noqa: BLE001
            pass
    src_tools = [s for s in src_tools if s] or ["Gmail"]
    rec = env["recommendation"]
    action = str(rec.get("action", ""))
    view = f"{rec.get('headline', '')} — {action}".strip(" —")
    draft_needed = any(w in (view + action).lower() for w in ("email", "reply", "respond", "send", "message"))
    # category from whichever rule(s) actually fired for this contact (env["derivation"]), same
    # reason_code-based split as /v1/insights — not a blanket "sales" regardless of the contact.
    fired_codes = {d.get("conclusion") for d in (env.get("derivation") or [])}
    category = "sales" if fired_codes & _DEAL_REASON_CODES else "general"
    return {"id": env["decision_id"], "type": "risk" if env["route"] == "flag" else "opportunity",
            "genios_view": view, "detail": str(rec.get("reasoning", "")),
            # extension 'Advice' reads suggestion/note (its card renders these directly)
            "suggestion": view, "note": str(rec.get("reasoning", "")),
            "confidence_score": env["confidence"],
            "scores": {"confidence": _band_label(env["confidence"]), "category": category},
            "draft_needed": draft_needed, "source_tools": src_tools,
            "generated_at": env["as_of"]["timestamp"]}


@router.get("/v1/intelligence/draft")
def draft_reply(contact: str, instruction: str = "", org_id: str = Depends(get_current_org)) -> dict:
    """Extension 'Draft reply' — a send-ready reply for the contact, grounded in their facts. LLM
    runs ONLY here (on the explicit click), never speculatively. GeniOS never auto-sends."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    node, facts = _resolve_contact_facts(org_id, contact)
    if node is None:
        raise HTTPException(404, "contact not found in context")
    if _llm is None:
        raise HTTPException(503, "LLM not configured")
    prompt = (
        f"Write a short, warm, professional reply to {node.display_name}. Ground it ONLY in these "
        f"known facts; do not invent specifics.\nFACTS: {json.dumps(facts, default=str)[:1500]}\n"
        f"WHAT TO WRITE: {instruction or 'an appropriate follow-up'}\n"
        f'Return STRICT JSON only: {{"draft": "<the full reply text, 3-6 sentences>"}}'
    )
    res = _llm.call(prompt, max_tokens=500)
    try:
        _graph.record_cost(org_id=org_id, model=res.model, purpose="intelligence_draft",
                           input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                           success=res.ok, error=getattr(res, "error", None))
    except Exception:      # noqa: BLE001
        pass
    draft = (res.parsed or {}).get("draft") if res.ok else None
    if not draft:
        raise HTTPException(502, "draft generation failed")
    return {"draft": draft, "contact": node.display_name}
