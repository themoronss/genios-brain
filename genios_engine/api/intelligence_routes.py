"""/v1/intelligence/* — the active intelligence query (the Ask page + extension on-demand).

Grounding-first Envelope with a graph_version-keyed decision cache: a repeat question on an
unchanged graph returns the stored Envelope with ZERO LLM cost. Credits are charged only here.
"""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.cache import get_cache
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import (make_graph_store, make_llm_client,
                                           make_pack_registry)
from genios_engine.reason.intelligence import (current_graph_version, normalize_question,
                                               run_query)

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
_REASONER_VERSION = "r3-foresight"   # bump invalidates the decision cache when reasoning changes


def _cache_key(org_id: str, module_id: str, question: str, gv: int) -> str:
    raw = f"{org_id}|{module_id}|{normalize_question(question)}|{gv}|{_REASONER_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()


# L7 spend guard — the ONE credit-billable surface. Monthly credit allowance + a per-minute burst
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
    gv = current_graph_version(_graph, org_id)
    ckey = _cache_key(org_id, module_id, question, gv)

    # decision cache — same question, unchanged graph → return the stored Envelope, no LLM.
    with _graph.engine.connect() as c:
        hit = c.execute(text("select envelope from decisions where org_id=:o and cache_key=:k "
                             "order by created_at desc limit 1"), {"o": org_id, "k": ckey}).first()
    if hit is not None:
        env = hit.envelope if isinstance(hit.envelope, dict) else json.loads(hit.envelope)
        env["cached"] = True
        return env

    _enforce_query_budget(org_id)          # L7: RPM + monthly credit guard before any LLM spend
    env, res = run_query(org_id=org_id, module_id=module_id, question=question,
                         extra_facts=body.facts or {}, store=_graph, llm=_llm,
                         registry=_registry, graph_version=gv)

    # record LLM spend (only the final-synthesis call, if it ran)
    if res is not None:
        try:
            _graph.record_cost(org_id=org_id, model=res.model, purpose="intelligence_query",
                               input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                               success=res.ok, error=getattr(res, "error", None))
        except Exception:      # noqa: BLE001 — never let cost logging break the answer
            _log.warning("intelligence cost log failed for %s", org_id)

    # persist the decision (for explain / feedback / cache)
    try:
        with _graph.engine.begin() as c:
            c.execute(text(
                "insert into decisions (decision_id, org_id, module_id, question, envelope, "
                "confidence, route, graph_version, cache_key, triggered_by) "
                "values (:d, :o, :m, :q, cast(:e as jsonb), :c, :r, :gv, :k, 'query')"),
                {"d": env["decision_id"], "o": org_id, "m": module_id, "q": question,
                 "e": json.dumps(env, default=str), "c": env["confidence"], "r": env["route"],
                 "gv": gv, "k": ckey})
    except Exception:      # noqa: BLE001 — a persistence failure must not lose the answer
        _log.warning("decision persist failed for %s", org_id)

    return env


# ── proactive: /v1/insights — the engine's already-computed recommendations (L5 cards) mapped into
# the shape the extension + dashboard expect. Cheap: no LLM at read time, cards were built by L3→L5.
def _band_label(score) -> str:
    s = float(score) if score is not None else 0.0
    return "high" if s >= 0.7 else ("medium" if s >= 0.4 else "low")


def _insight_type(band: str | None) -> str:
    return "risk" if (band or "").lower() in ("now", "urgent", "high", "today") else "opportunity"


_OPEN_STATES = ("queued", "delivered", "snoozed")
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
def list_insights(limit: int = 50, state: str = "open", org_id: str = Depends(get_current_org)) -> dict:
    """Extension feed. state=open (default) → cards needing action; state=resolved → acted/resolved
    (the inbox's Resolved tab). Same card shape either way."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    states = _RESOLVED_STATES if state == "resolved" else _OPEN_STATES
    with _graph.engine.connect() as c:
        # join through the signal to the subject node → the contact/deal NAME the extension needs for
        # page-matching + resolving Draft/Advice. Left joins so a card without a node still returns.
        rows = c.execute(text(
            "select k.card_id, k.headline, k.situation, k.score, k.domain, k.urgency_band, "
            "k.context_tags, k.created_at, k.actions, n.display_name as entity, s.reason_code "
            "from cards k left join signals s on s.signal_id=k.signal_id "
            "left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=k.org_id "
            "and n.valid_to is null "
            "where k.org_id=:o and k.state = any(:states) "
            "order by k.score desc nulls last, k.created_at desc limit :l"),
            {"o": org_id, "states": list(states), "l": max(1, min(int(limit), 100))}).fetchall()
    # L6 impressions — log card.surfaced ONCE per shown card (deterministic id + dedup) so the
    # calibration precision loop has impressions to reach eligibility. Open feed only (not Resolved).
    if state != "resolved" and rows:
        try:
            with _graph.engine.begin() as c:
                c.execute(text(
                    "insert into card_events (id, card_id, org_id, kind, cause, actor_id) "
                    "select 'cevs_' || k.card_id, k.card_id, :o, 'card.surfaced', 'pull', 'extension' "
                    "from cards k where k.org_id=:o and k.card_id = any(:ids) "
                    "and not exists (select 1 from card_events ce where ce.card_id=k.card_id "
                    "                and ce.kind='card.surfaced') on conflict do nothing"),
                    {"o": org_id, "ids": [r.card_id for r in rows]})
        except Exception:      # noqa: BLE001 — impressions are best-effort, never block the feed
            pass
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
    rules = [{"id": d.get("rule_id"), "priority": i + 1,
              "matched_facts": d.get("matched_facts", {}), "conclusion": d.get("conclusion", "")}
             for i, d in enumerate(deriv)]
    return {"decision_id": decision_id, "org_id": org_id,
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


# Map the extension's feedback verbs to the CANONICAL card-action shape L6 precision reads
# (kind='human.card_action' + cause + detail.reason). Was the gap: it logged kind='wrong'/'helpful'
# with no cause, and precision_28d counts on ce.cause → every extension thumb was invisible to the
# calibration loop, so "it learns from you" couldn't demonstrably learn.
_FB_CAUSE = {"thumbs_up": "do_it_myself", "edit": "do_it_myself",
             "thumbs_down": "wrong", "never_show": "wrong", "snooze": "snooze"}
_FB_REASON = {"thumbs_down": "not_relevant", "never_show": "not_relevant"}


@router.post("/v1/intelligence/feedback")
def intelligence_feedback(body: FeedbackBody, org_id: str = Depends(get_current_org)) -> dict:
    """Human feedback on a recommendation. For an insight (a card) it logs a card_event in the
    canonical shape the L6 calibration loop reads (cause + reason) — repeated 'wrong' auto-mutes the
    rule. Returns the correction id."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    fid = new_id("fb")
    routed = False
    if body.insight_id:      # an insight IS a card → feed L6 through the card_events ledger
        try:
            detail = dict(body.edit_diff or {})
            if body.action in _FB_REASON:
                detail["reason"] = _FB_REASON[body.action]     # → precision denominator (rel_wrong)
            with _graph.engine.begin() as c:
                c.execute(text(
                    "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                    "values (:i, :c, :o, 'human.card_action', :cause, :a, cast(:d as jsonb))"),
                    {"i": new_id("cev"), "c": body.insight_id, "o": org_id,
                     "cause": _FB_CAUSE.get(body.action, body.action), "a": body.user_id or "user",
                     "d": json.dumps(detail, default=str)})
            routed = True
        except Exception:      # noqa: BLE001
            _log.warning("feedback card_event failed for %s", org_id)
    return {"feedback_id": fid,
            "correction_id": fid if body.action in ("thumbs_down", "never_show", "edit") else None,
            "routed_to_g_i_3": routed}


# ── extension parity: auth-derived-org /v1/* wrappers (the extension auths with an API key, so it
# can't use the dashboard's /api/org/{org}/* path-scoped routes). Thin over existing logic. ─────────

def _card_event(org_id: str, card_id: str, kind: str, detail: dict) -> bool:
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    try:
        with _graph.engine.begin() as c:
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
def dismiss_insight(insight_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """Extension dismiss — expire the card + log the event (feeds L6's ignore-rate)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    with _graph.engine.begin() as c:
        res = c.execute(text("update cards set state='expired' where card_id=:c and org_id=:o "
                             "and state in ('queued','surfaced','snoozed','delivered')"),
                        {"c": insight_id, "o": org_id})
        found = c.execute(text("select 1 from cards where card_id=:c and org_id=:o"),
                          {"c": insight_id, "o": org_id}).first() is not None
    _card_event(org_id, insight_id, "card.dismissed", {"via": "extension"})
    return {"ok": found, "dismissed": bool(res.rowcount)}


class OutcomeBody(BaseModel):
    outcome: str


@router.post("/v1/insights/{insight_id}/outcome")
def insight_outcome(insight_id: str, body: OutcomeBody,
                    org_id: str = Depends(get_current_org)) -> dict:
    ok = _card_event(org_id, insight_id, "outcome", {"outcome": body.outcome, "via": "extension"})
    return {"ok": ok, "outcome": body.outcome}


class HandoffBody(BaseModel):
    draft: str | None = None          # optional reviewed draft/action text to execute
    instruction: str | None = None    # or a free-form "what to do"


@router.post("/v1/insights/{insight_id}/handoff")
def handoff_insight(insight_id: str, body: HandoffBody | None = None,
                    org_id: str = Depends(get_current_org)) -> dict:
    """Hand this decision off to the org's connected EXECUTOR to act on (GeniOS advises; it never
    executes itself). Executor-agnostic: delivers to any agent in the org that registered a webhook
    (Hermes or the client's own tool), reusing the signed push transport. If none is connected,
    executors_notified=0 and the client should fall back to drafting."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    with _graph.engine.connect() as c:
        owns = c.execute(text("select 1 from cards where card_id=:c and org_id=:o"),
                         {"c": insight_id, "o": org_id}).first()
    if owns is None:
        raise HTTPException(404, "insight not found")
    from genios_engine.deliver.push import push_action_to_agents
    draft = body.draft if body else None
    instruction = body.instruction if body else None
    delivered = push_action_to_agents(_graph, org_id, insight_id, draft=draft, instruction=instruction)
    _card_event(org_id, insight_id, "card.handoff",
                {"executors_notified": delivered, "has_draft": bool(draft), "via": "extension"})
    return {"handed_off": delivered > 0, "executors_notified": delivered,
            "note": None if delivered else "No executor connected — draft it instead."}


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
            "length(display_name) asc limit 1"),
            {"o": org_id, "n": contact, "like": f"%{contact}%"}).first()
        facts = {}
        if node is not None:
            for f in c.execute(text("select field, value from graph_facts where org_id=:o "
                                    "and subject_node_id=:n and valid_to is null and status='active' "
                                    "limit 20"), {"o": org_id, "n": node.node_id}):
                facts[f.field] = str(f.value).strip('"')
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
    gv = current_graph_version(_graph, org_id)
    q = (situation or "").strip() or f"What is the next best action for {contact}?"
    llm = (_deep_llm() or _llm) if deep else _llm       # deep → Sonnet (was a silent no-op)
    env, res = run_query(org_id=org_id, module_id="sales", question=f"{q} (contact: {contact})",
                         extra_facts={}, store=_graph, llm=llm, registry=_registry, graph_version=gv)
    if res is not None:
        try:
            _graph.record_cost(org_id=org_id, model=res.model, purpose="intelligence_analyze",
                               input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                               success=res.ok, error=getattr(res, "error", None))
        except Exception:      # noqa: BLE001
            pass
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
            "draft_needed": draft_needed, "source_tools": ["Gmail"],
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
