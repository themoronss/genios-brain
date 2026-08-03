"""Symbolic signal detectors — PURE functions over graph-derived numbers. No LLM,
no DB (the runtime feeds them the numbers). Unit-testable in isolation.

- engagement_level : how live the relationship is (recency + volume)     0..1
- momentum         : warming(+) / cooling(-) trend over the last month  -1..1
- importance       : how much this subject matters (value/role/reach)     0..1
"""

from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def engagement_level(days_since_last_seen: float, fact_count: int) -> float:
    """Recent + active = high. Zero by ~45 days silent."""
    recency = _clamp(1.0 - days_since_last_seen / 45.0)
    volume = _clamp(fact_count / 10.0)  # saturates at 10 facts
    return round(0.6 * recency + 0.4 * volume, 4)


def momentum(recent_7d: int, prior_8_30d: int) -> float:
    """Trend: activity in the last 7d vs the prior 23d (per-day rate).
    >0 warming, <0 cooling. This is the 'went quiet after being active' signal."""
    recent_rate = recent_7d / 7.0
    prior_rate = prior_8_30d / 23.0
    if recent_rate == 0.0 and prior_rate == 0.0:
        return 0.0
    return round(_clamp((recent_rate - prior_rate) / max(prior_rate, 0.05), -1.0, 1.0), 4)


def importance(attributes: dict, edge_count: int) -> float:
    """How much this subject matters: deal value + role seniority + graph reach.
    A generic heuristic — the founder/sales modules refine the weights later."""
    base = 0.3
    amount_factor = 0.0
    amt = attributes.get("amount")
    if amt not in (None, ""):
        try:
            amount_factor = _clamp(float(str(amt).replace(",", "").replace("$", "")) / 100_000.0) * 0.3
        except (ValueError, TypeError):
            amount_factor = 0.0
    role = str(attributes.get("role") or "").lower()
    senior = ("founder", "ceo", "cto", "cfo", "vp", "head", "director", "partner", "decision", "owner")
    role_factor = 0.2 if any(k in role for k in senior) else 0.0
    conn_factor = _clamp(edge_count / 15.0) * 0.2  # more connected = more central
    return round(_clamp(base + amount_factor + role_factor + conn_factor), 4)
