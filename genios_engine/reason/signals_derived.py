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

# qualitative observation polarity — the vocabulary is CONTEXT-owned (the L2 normalizer
# emits it), so the sets live in context/vocabulary.py and reason imports them DOWNWARD.
# Re-exported under the old names for existing callers.
from genios_engine.context.vocabulary import OBS_NEGATIVE as NEG_OBS
from genios_engine.context.vocabulary import OBS_POSITIVE as POS_OBS

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


SENTIMENT_WINDOW_DAYS = 90


def _in_window(o, eval_time, window_days: int) -> bool:
    if eval_time is None:
        return True
    ts = o.get("occurred_at")
    if ts is None:
        return True                       # undated obs: keep (never silently drop data)
    if not hasattr(ts, "tzinfo"):
        return True
    if ts.tzinfo is None:
        from datetime import timezone as _tz
        ts = ts.replace(tzinfo=_tz.utc)
    from datetime import timedelta as _td
    return ts >= eval_time - _td(days=window_days)


def sentiment_facts(obs, eval_time=None, window_days: int = SENTIMENT_WINDOW_DAYS) -> dict:
    """derived.sentiment/obs_pos/obs_neg/obs_count from the node's observations (already
    loaded). WINDOWED: only observations from the trailing `window_days` count — a single
    14-month-old pricing objection must not pin a contact negative forever (sentiment is
    a trajectory, not a life sentence). obs_count stays all-time (it measures history)."""
    kinds_all = [o.get("kind") for o in obs]
    recent = [o.get("kind") for o in obs if _in_window(o, eval_time, window_days)]
    pos = sum(1 for k in recent if k in POS_OBS)
    neg = sum(1 for k in recent if k in NEG_OBS)
    out = {"derived.obs_count": _f(len(kinds_all))}
    if pos or neg:
        out["derived.sentiment"] = _f(round((pos - neg) / float(pos + neg), 3))
        out["derived.obs_pos"] = _f(pos)
        out["derived.obs_neg"] = _f(neg)
    return out
