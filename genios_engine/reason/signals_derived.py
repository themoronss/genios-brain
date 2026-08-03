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
POS_OBS = {"budget_approved", "buying_intent", "pricing_discussed", "positive_reply",
           "champion_engaged", "next_step_agreed"}
NEG_OBS = {"objection", "competitor", "going_dark", "churn_risk", "negative_reply",
           "price_pushback", "stakeholder_left"}


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
