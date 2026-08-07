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


# Node types that can carry a conversation clock for a deal. A deal's edges reach its
# contacts (structured/registry.py's contact_email bridge) and, through them, the threads
# those people are on.
_CONVERSANT_TYPES = frozenset({"person", "contact", "stakeholder", "thread"})

# The counterparty's clock, in preference order. thread.last_inbound is written by L2 on
# every inbound message; deal.close_date is a CRM-set date and is NOT activity, so it is
# deliberately absent.
_INBOUND_FIELDS = ("thread.last_inbound",)

# Paths that exist only because of this join. The runner uses this to decide it needs the
# neighbour index — a rule reading one of these gets NOTHING without it.
NEIGHBOR_DERIVED_PATHS = frozenset({"deal.last_inbound"})


def deal_activity_facts(node_id: str, adj: dict, node_types: dict, fact_idx: dict) -> dict:
    """THE CROSS-TOOL JOIN: derive `deal.last_inbound` for a deal node from the email
    activity of the people attached to it.

    The bug this closes: three rules — stalled_deal (the highest-scoring rule in the whole
    corpus), timeline_slip and champion_quiet — clock off `deal.last_inbound`, and NOTHING
    in the system has ever written that field. The CRM lane writes deal.stage/amount/
    close_date; L2 writes thread.last_inbound on the PERSON/THREAD node. Both halves were
    in the graph, joined by a real edge, and no one put them together — so the flagship
    "this deal went quiet" signal was unreachable regardless of scoring.

    A human reads it in one step: "HubSpot says this deal is open; the buyer last wrote 12
    days ago." That is exactly this function.

    Deterministic: the MAX inbound timestamp across all conversant neighbours (any
    stakeholder replying means the deal is alive), ties broken by node id, never by set
    iteration order. Authority is capped at rank 2 — the timestamp itself is hard fact, but
    "this thread is about this deal" is an inference from the edge, so it must not
    out-rank a system of record. A CRM- or human-set deal.last_inbound always wins,
    because the caller only fills a field that is absent.
    """
    best_ts = best_conf = None
    best_nid = ""
    for neighbor_id in sorted(adj.get(node_id, set())):
        if node_types.get(neighbor_id) not in _CONVERSANT_TYPES:
            continue
        facts = fact_idx.get(neighbor_id, {})
        for field in _INBOUND_FIELDS:
            record = facts.get(field)
            if not record:
                continue
            ts = record[1]                       # occurred_at of the inbound fact
            if ts is None:
                continue                         # an undated clock cannot drive elapsed time
            if best_ts is None or ts > best_ts or (ts == best_ts and neighbor_id < best_nid):
                conf = float(record[3]) if len(record) > 3 else 0.0
                best_ts, best_conf, best_nid = ts, conf, neighbor_id
    if best_ts is None:
        return {}
    return {"deal.last_inbound": {
        "value": best_ts.isoformat(),
        # never claim more confidence than the source fact carried, and never more than
        # rank 2 deserves — the join is an inference, the timestamp is not.
        "confidence": min(0.85, best_conf) if best_conf else 0.85,
        "authority_rank": 2,
        "occurred_at": best_ts,
        "independence_group": "graph:deal_conversation",
        "src_count": 1,
    }}


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
