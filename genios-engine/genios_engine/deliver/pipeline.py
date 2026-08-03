from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_default, make_registry

from .card_builder import build_draft
from .render import render_copy
from .router import budget_full
from .store import CardStore

# L5 pipeline — turn gated signals into delivered cards. Runs after L3 (in-process background, no
# Celery). One card per open signal: E0 compose → E1 render (one temp-0 call, validated) → E3
# budget → persist at 'queued'. Cards only build from signals that already passed L3's gate, so
# the model runs at most budget_per_day times per org — cheap by construction.


def _open_signals_without_cards(graph, org_id: str) -> list[dict]:
    with graph.engine.connect() as c:
        rows = c.execute(text(
            "select s.signal_id, s.reason_code, s.level, s.subject_node_id, s.score, "
            "s.score_inputs, s.evidence, s.play, s.config_snapshot_id "
            "from signals s left join cards k on k.signal_id = s.signal_id "
            "where s.org_id=:o and s.status='open' and k.card_id is null "
            "order by s.score desc"),           # highest-value first → per-assignee push budget spends on the best
            {"o": org_id}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for jf in ("score_inputs", "evidence"):
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
    effective, _snap = registry.effective(org_id)
    if effective is None:
        return {"built": 0, "reason": "no_pack"}

    from .bands import band
    bands_cfg = effective.get("scoring", {}).get("bands")
    budget = int(effective.get("scoring", {}).get("budget_per_user_day", 7))
    out = {"built": 0, "llm": 0, "raw_slot": 0, "unrouted": 0, "over_budget_no_push": 0,
           "pushed": 0, "agent_pushed": 0}
    for sig in _open_signals_without_cards(graph, org_id):
        draft = build_draft(graph, org_id, sig, effective, eval_time)         # E0
        copy = render_copy(reason_code=draft["_reason_code"], template=draft["_template"],   # E1
                           facts=draft["_facts"], slots=draft["_slots"], llm=llm,
                           cost_sink=graph.record_cost, org_id=org_id)
        # artifact_ready must reflect the REAL render — a raw-slot fallback has an empty body, so
        # Run Play should NOT advertise a ready draft (was hardcoded True, opened an empty preview).
        ready = bool((copy.get("artifact") or {}).get("body"))
        for a in draft["actions"]:
            if a.get("type") == "run_play":
                a["artifact_ready"] = ready
        over_budget = budget_full(card_store, org_id, draft["assignee"], eval_time, budget)
        if over_budget:
            out["over_budget_no_push"] += 1     # still lands on the dashboard, just no push
        card_id = card_store.insert_card(draft, copy)
        out["built"] += 1
        out["llm" if copy["render_mode"] == "llm" else "raw_slot"] += 1
        # Proactive push (§A) — fan this card out to any agent that registered a webhook_url. Org-wide,
        # independent of the human seat routing below; best-effort (never breaks the L5 pass).
        try:
            from .push import push_card_to_agents
            out["agent_pushed"] += push_card_to_agents(card_store, org_id, card_id)
        except Exception:                                  # noqa: BLE001
            pass
        if draft["assignee"] is None:
            out["unrouted"] += 1
        # push policy (§5.12): HIGH/CRITICAL bands surface immediately (card.surfaced cause=push —
        # the impression L6's precision denominator counts); STANDARD rotates client-side. Budget
        # caps the push, never the card (an over-budget card still lands on the dashboard).
        if band(int(sig["score"]), bands_cfg) in ("high", "critical") and draft["assignee"] and not over_budget:
            if card_store.transition(card_id, org_id, "surfaced", "card.surfaced", cause="push",
                                     allowed_from=("queued",)):
                out["pushed"] += 1
    return out
