from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import scoring
from .rules import Rule

# L3 evaluator (C2) — pure eval over a node's typed facts + the passed eval_time. No LLM,
# no text parsing, no system clock. Whitelisted funcs only (days_since / hours_since /
# comparisons / exists / obs-presence). Then closed-form scoring (C5).


@dataclass
class NodeContext:
    node_id: str
    node_type: str
    facts: dict[str, dict] = field(default_factory=dict)   # field -> {value, confidence, authority_rank}
    obs: list[dict] = field(default_factory=list)          # [{kind, occurred_at}]
    baselines: dict[str, float] = field(default_factory=dict)   # e.g. {"reply_cadence": 2.1}
    # cross-entity substrate (C1) — the 1-hop neighbourhood over graph_edges, so a rule on a deal can
    # read the account's contacts/competitor-obs (single-threaded / competitor-in-account reasoning).
    edge_count: int = 0                                    # number of current edges on this node
    neighbor_obs: set = field(default_factory=set)         # union of neighbours' observation kinds
    neighbor_facts: dict = field(default_factory=dict)     # field -> latest value across neighbours
    #: The Layer 2 situation anchored on this node, if L2 correlated one.
    #:
    #: L2 computes a whole substrate — thread families, dormancy, coverage, a five-dimension
    #: confidence vector — writes it to `context_situations`, and until now NOTHING on the live
    #: decision path read a single row of it. Cards were built from one person row's facts, so
    #: everything L2 knew (that 68 Boardy events are one thread family, that a situation went
    #: dormant, that coverage is 50%, that confidence_overall is 33) had zero effect on what the
    #: founder saw.
    #:
    #: `None` means L2 correlated no situation for this node, which is itself information and
    #: must stay distinguishable from "a situation with nothing in it".
    situation: dict | None = None


def _resolve_value(ctx: NodeContext, value):
    """A threshold may be a literal, or baseline-derived: {baseline, mult, floor} →
    max(floor, mult · baseline). Cold-start baselines fall back to the floor."""
    if isinstance(value, dict) and "baseline" in value:
        base = ctx.baselines.get(value["baseline"])
        floor = float(value.get("floor", 0))
        if base is None:
            return floor
        return max(floor, float(value.get("mult", 1)) * base)
    return value


def _parse_ts(v) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _num(v):
    try:
        n = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _cmp(a, op, b) -> bool:
    # A non-finite numeric fact is malformed, not a valid categorical value. In particular,
    # `nan != threshold` would otherwise be True and could fire a rule on corrupt input.
    if ((isinstance(a, (int, float)) and not isinstance(a, bool) and _num(a) is None)
            or (isinstance(b, (int, float)) and not isinstance(b, bool) and _num(b) is None)):
        return False
    if op == "=":
        return a == b
    if op == "!=":
        return a != b
    if op == "IN":
        return a in b if isinstance(b, (list, tuple, set)) else False
    an, bn = _num(a), _num(b)
    if an is None or bn is None:
        return False
    return {">": an > bn, ">=": an >= bn, "<": an < bn, "<=": an <= bn}.get(op, False)


def _hours_since(ctx: NodeContext, path: str, eval_time: datetime) -> float | None:
    f = ctx.facts.get(path)
    if not f:
        return None
    ts = _parse_ts(f.get("value"))
    if ts is None:
        return None
    return (eval_time - ts).total_seconds() / 3600.0


def _eval_condition(ctx: NodeContext, cond: dict, eval_time: datetime) -> bool:
    if "exists" in cond:
        return cond["exists"] in ctx.facts
    if "absent" in cond:
        return cond["absent"] not in ctx.facts
    if "present" in cond:
        # "we have actually captured this fact" — the counterpart to `absent`, and the guard a
        # rule needs when its imperative presumes a RELATIONSHIP exists. `missing_ok` makes an
        # absent fact PASS a negative check, which is right for narrowing a population and wrong
        # as the only gate on a rule: closed_lost_risk fired on newsletter senders because
        # `ball_in_court != them, missing_ok` passes for people we have never exchanged a word
        # with, and "save the deal now" needs a deal before it needs saving.
        return cond["present"] in ctx.facts
    if "has_obs" in cond:
        return any(o.get("kind") == cond["has_obs"] for o in ctx.obs)
    if "no_obs" in cond:
        return not any(o.get("kind") == cond["no_obs"] for o in ctx.obs)
    # cross-entity ops (C1) — read the neighbourhood loaded into ctx, not just this node.
    if "neighbor_has_obs" in cond:
        return cond["neighbor_has_obs"] in ctx.neighbor_obs
    if "neighbor_no_obs" in cond:
        return cond["neighbor_no_obs"] not in ctx.neighbor_obs
    if "neighbor_fact" in cond:
        v = ctx.neighbor_facts.get(cond["neighbor_fact"])
        return _cmp(v, cond["op"], _resolve_value(ctx, cond["value"])) if v is not None else False
    fn = cond.get("fn")
    if fn == "edge_count":
        return _cmp(ctx.edge_count, cond["op"], _resolve_value(ctx, cond["value"]))
    if fn in ("days_since", "hours_since"):
        hrs = _hours_since(ctx, cond["path"], eval_time)
        if hrs is None:
            return False
        val = hrs / 24.0 if fn == "days_since" else hrs
        return _cmp(val, cond["op"], _resolve_value(ctx, cond["value"]))
    if "path" in cond:
        f = ctx.facts.get(cond["path"])
        if f is None:
            # A missing fact fails a positive check (unchanged default). But a NEGATIVE guard —
            # "fire unless the fact is explicitly X" — must PASS when the fact is absent, or it
            # would silently suppress every node that never captured the fact (e.g. ball_in_court
            # exists on <5% of persons). `missing_ok` opts a single condition into absent→pass;
            # conditions without it keep the strict absent→False behaviour.
            return bool(cond.get("missing_ok"))
        return _cmp(f.get("value"), cond["op"], _resolve_value(ctx, cond["value"]))
    return False


def evaluate(ctx: NodeContext, rule: Rule, eval_time: datetime) -> bool:
    """The pure function: all `when` conditions true over this node at eval_time."""
    return all(_eval_condition(ctx, c, eval_time) for c in rule.when)


def _activation_threshold_hours(rule: Rule) -> float:
    """The rule's episode-flip point: the days/hours_since threshold on the urgency path that
    made the condition become true. R is 100 AT the flip and decays after — so a deal that just
    crossed 7 days ranks fresh, while a 40-day-stale one decays toward 0 (was: R constant 100)."""
    path = rule.urgency.get("path")
    for c in rule.when:
        if c.get("path") == path and c.get("fn") in ("days_since", "hours_since"):
            v = c.get("value")
            if isinstance(v, (int, float)):
                return float(v) * (24.0 if c["fn"] == "days_since" else 1.0)
    return 0.0                    # no explicit threshold → treat the trigger moment as the flip


def _freshness(occurred_at, eval_time, *, half_life_days: float = 30.0) -> float:
    """Data-age decay of the trigger fact: today ≈ 1.0, an old fact decays toward 0. Feeds the
    30%-freshness slot of the confidence term (was hardcoded 1.0 — stale data scored as if fresh)."""
    if occurred_at is None:
        # Preserve the v0.3 treatment for derived/legacy facts that have no separate observation
        # timestamp. Explicitly malformed or future timestamps below fail closed instead.
        return 1.0
    occurred = _parse_ts(occurred_at)
    evaluated = _parse_ts(eval_time)
    half_life = _num(half_life_days)
    if occurred is None or evaluated is None or half_life is None or half_life <= 0:
        return 0.0
    age_days = (evaluated - occurred).total_seconds() / 86400.0
    if not math.isfinite(age_days) or age_days < 0:
        return 0.0
    return math.exp(-age_days / max(1.0, half_life))


def score_rule(ctx: NodeContext, rule: Rule, eval_time: datetime,
               scoring_cfg: dict | None = None) -> tuple[int, dict]:
    """Closed-form S with score.inputs — ALL constants from the pack's scoring config
    (weights, impact floor/p90, r half-life, c-weights, corroboration ladder)."""
    sc = scoring_cfg or {}
    hrs = _hours_since(ctx, rule.urgency["path"], eval_time) or 0.0
    elapsed_days = hrs / 24.0
    # HOT-signal fix: a rule with NO time gate in `when` (buying_signal, contract_requested,
    # objection, competitor…) fires the moment the signal lands → elapsed=0 → U=0 → it would sit
    # below the gate for days, missing the hot moment. Its signal IS the urgency, so floor U at the
    # trigger. Explicit rule.urgency.floor wins; else immediate non-`slow` rules get the pack's
    # immediate_urgency_floor (default 65). Time-gated rules (stalled/unanswered/overdue) keep U=0→grow.
    ufloor = float(rule.urgency.get("floor", 0))
    if ufloor == 0 and not rule.urgency.get("slow") and not any(
            c.get("fn") in ("days_since", "hours_since") for c in rule.when):
        ufloor = float((scoring_cfg or {}).get("immediate_urgency_floor", 65))
    U = scoring.urgency(rule.urgency.get("type", "elapsed"), elapsed_days,
                        float(rule.urgency.get("h", 3)), ufloor)

    imp = sc.get("impact", {})
    deal_val = _num((ctx.facts.get("deal.value") or {}).get("value"))
    linked = rule.linked_deal and imp.get("i_floor_scope", "deal_linked") == "deal_linked"
    I = scoring.impact(deal_val, imp.get("p90_default"), linked_deal=linked,
                       floor=imp.get("i_floor", 40))

    hl = sc.get("r_half_life", {})
    hrs_since_flip = max(0.0, hrs - _activation_threshold_hours(rule))   # real recency decay
    R = scoring.recency(hrs_since_flip, half_life=float(hl.get("elapsed_h", 72)))

    trig = ctx.facts.get(rule.urgency["path"]) or {}
    ext_conf = float(trig.get("confidence") or 0.9)
    corr_cfg = sc.get("corroboration", {})
    src = int(trig.get("src_count") or 1)          # distinct sources asserting this fact (real count)
    if (int(trig.get("authority_rank") or 1) >= 3 and corr_cfg.get("rank3_full", True)) or src >= 3:
        corr = corr_cfg.get("three_plus", 100) / 100.0
    elif src == 2:
        corr = corr_cfg.get("two", 85) / 100.0     # was DEAD — two independent sources now count
    else:
        corr = corr_cfg.get("one", 60) / 100.0
    fresh = _freshness(trig.get("occurred_at"), eval_time,
                       half_life_days=float(sc.get("freshness_half_life_days", 30)))
    C = scoring.confidence(ext_conf, freshness=fresh, corroboration=corr, c_weights=sc.get("c_weights"))

    return scoring.score(U, I, R, C, sc.get("weights"))
