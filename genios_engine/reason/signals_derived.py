"""Derived continuous signals (C1) — deterministic per-node metrics injected into NodeContext.facts
under `derived.*` so pack rules read them like any typed fact (no LLM, no engine change).

Two families:
  • sentiment / obs-balance — aggregated from graph_observations already loaded on the node.
  • momentum / engagement    — trajectory of event gaps + volume, computed by the baseline builder
                               (reuses its per-person event scan) and loaded alongside baselines.

`derived.momentum`   : recent reply-gap ÷ this contact's own median gap. >1 = cooling, <1 = heating.
`derived.engagement` : events in the last 14d ÷ the prior 14d. <1 = interaction is thinning out.
`derived.sentiment`  : (positive obs − negative obs) ÷ total, −1..1.
"""
from __future__ import annotations

# qualitative observation vocabulary → polarity. Kept here (reason-layer), not the pack, because a
# derived metric is engine machinery; packs add rules that THRESHOLD these, they don't redefine them.
# Vocabulary is the canonical set the L2 obs-kind normalizer emits (context.pipeline.norm_obs_kind).
POS_OBS = {"budget_approved", "buying_intent", "pricing_discussed", "positive_reply",
           "champion_engaged", "next_step_agreed", "verbal_yes", "contract_requested",
           "demo_requested", "stakeholder_added", "security_review_started"}
NEG_OBS = {"objection", "objection_price", "objection_timing", "objection_security",
           "objection_authority", "objection_integration", "competitor", "going_dark",
           "churn_risk", "negative_reply", "price_pushback", "stakeholder_left",
           "discount_pressure", "budget_freeze", "champion_change", "timeline_slip",
           "closed_lost_mention"}

# closed-stage tells for deriving deal.status from the CRM's deal.stage.
_STAGE_WON = ("won", "closedwon", "closed_won")
_STAGE_LOST = ("lost", "closedlost", "closed_lost")


def deal_facts(facts: dict) -> dict:
    """F1 — derive `deal.status` and `deal.value` for a deal node so the pack rules (which read
    `deal.status`/`deal.value`) fire off the `deal.stage`/`deal.amount` the CRM structured lane
    actually writes. Eval-time engine-machinery (like sentiment), NOT a structured-commit change,
    so the domain-agnostic write path stays untouched. No-op unless the source facts exist and the
    derived field isn't already present (a human/CRM-set status wins)."""
    out: dict = {}
    stage_f = facts.get("deal.stage")
    if stage_f is not None and "deal.status" not in facts:
        s = str(stage_f.get("value") or "").strip().strip('"').lower()
        status = ("won" if any(w in s for w in _STAGE_WON)
                  else "lost" if any(w in s for w in _STAGE_LOST) else "open")
        out["deal.status"] = {"value": status,
                              "confidence": float(stage_f.get("confidence") or 0.9),
                              "authority_rank": stage_f.get("authority_rank") or 3,
                              "occurred_at": stage_f.get("occurred_at"),
                              "src_count": stage_f.get("src_count") or 1}
    amt_f = facts.get("deal.amount")
    if amt_f is not None and "deal.value" not in facts:
        out["deal.value"] = dict(amt_f)     # alias — same value/confidence/occurred_at
    return out


def _f(value):
    # fact-shaped so _load_context/scoring treat it uniformly; occurred_at None → freshness 1.0.
    return {"value": value, "confidence": 0.85, "authority_rank": 2,
            "occurred_at": None, "src_count": 1}


def sentiment_facts(obs) -> dict:
    """derived.sentiment/obs_pos/obs_neg/obs_count from the node's observations (already loaded)."""
    kinds = [o.get("kind") for o in obs]
    pos = sum(1 for k in kinds if k in POS_OBS)
    neg = sum(1 for k in kinds if k in NEG_OBS)
    out = {"derived.obs_count": _f(len(kinds))}
    if pos or neg:
        out["derived.sentiment"] = _f(round((pos - neg) / float(pos + neg), 3))
        out["derived.obs_pos"] = _f(pos)
        out["derived.obs_neg"] = _f(neg)
    return out
