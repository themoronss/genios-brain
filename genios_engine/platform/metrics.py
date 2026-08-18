"""Metric dictionary — ONE definition per number.

Every analytics surface (the admin console today, the PostHog emitter next) reads its definitions
from here. This module exists because the previous analytics generation defined "active account",
"cost" and "revenue" separately in PostHog insights and in Python, so the two never agreed and the
numbers could not be put in front of an investor. A metric that is not defined here does not get a
tile.

Locked definitions (ANALYTICS_V3_PLAN.md §1):
  • Account          — one `orgs` row. Never called a "user": one org can hold many humans.
  • Internal account — `orgs.is_internal`. Excluded from every metric, no exceptions.
  • Active           — ≥1 real product action in the window (see ACTIVITY_ACTIONS), not a page open.
  • Activated        — the account has asked the product a question at least once
                       (`orgs.activated_at`, stamped on the first /v1/intelligence/query).
  • LLM cost (USD)   — tokens × model-family list price. The ledger stores tokens, never dollars,
                       so a price change re-prices history consistently everywhere.
  • Revenue (INR)    — settled `subscriptions` rows, in rupees.
  • MRR (INR)        — monthly-normalised plan price of every active paid account.
"""
from __future__ import annotations

from genios_engine.platform.billing import PLAN_PRICES, normalize_plan

# ── currency ────────────────────────────────────────────────────────────────────────────
# One conversion rate for the whole product. Revenue is earned in INR, model spend is billed in USD,
# and margin needs them in one unit — mixing them per-tile is how the old "gross margin" tile
# silently drifted from the money actually in the bank.
INR_PER_USD = 83.0

# ── LLM pricing (USD per token, by model family) ────────────────────────────────────────
# Keyed by substring so a dated model id (claude-sonnet-5-2026…) still prices correctly. Unknown
# models fall back to the CHEAPEST family, which under-reports rather than inflating spend — an
# analytics number should never flatter us by accident.
LLM_PRICE: dict[str, tuple[float, float]] = {
    "opus":   (15.0e-6, 75.0e-6),
    "sonnet": (3.0e-6,  15.0e-6),
    "haiku":  (0.80e-6, 4.0e-6),
}
_FALLBACK = "haiku"


def llm_price(model: str) -> tuple[float, float]:
    """(input $/token, output $/token) for a model id."""
    m = (model or "").lower()
    for family, price in LLM_PRICE.items():
        if family in m:
            return price
    return LLM_PRICE[_FALLBACK]


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pi, po = llm_price(model)
    return int(input_tokens or 0) * pi + int(output_tokens or 0) * po


def cost_usd_sql(table_alias: str = "") -> str:
    """The same pricing as `cost_usd`, as a SQL expression, so per-account rollups can be computed
    in one aggregate instead of pulling every ledger row into Python. Generated from LLM_PRICE —
    the Python and SQL paths cannot drift apart."""
    p = f"{table_alias}." if table_alias else ""
    cases = "".join(
        f" when lower({p}model) like '%{family}%' "
        f"then {p}input_tokens * {pi!r} + {p}output_tokens * {po!r}"
        for family, (pi, po) in LLM_PRICE.items())
    fi, fo = LLM_PRICE[_FALLBACK]
    return (f"sum(case{cases} else {p}input_tokens * {fi!r} + {p}output_tokens * {fo!r} end)")


# ── activity ────────────────────────────────────────────────────────────────────────────
# What counts as "the account used the product". Deliberately excludes page views: the old
# dashboards counted opens as activity and reported a DAU that no investor question survived.
ACTIVITY_ACTIONS = ("user_logged_in", "decision_made", "data_synced", "data_accessed")
ACTIVITY_ACTIONS_SQL = "(" + ",".join(f"'{a}'" for a in ACTIVITY_ACTIONS) + ")"

# Applied to every query that reports a number. Kept as a constant so "did we remember to exclude
# ourselves?" is answerable by grep rather than by reading each query.
REAL_ORGS = "coalesce(o.is_internal, false) = false"


# ── revenue ─────────────────────────────────────────────────────────────────────────────
def mrr_inr(tier: str | None, plan_status: str | None = "active") -> float:
    """Monthly recurring revenue in rupees for one account. Trial, expired and suspended accounts
    contribute 0 — a signed-up-but-unpaid account is growth, not revenue."""
    if (plan_status or "").lower() in {"suspended", "cancelled", "expired"}:
        return 0.0
    price = PLAN_PRICES.get(normalize_plan(tier or ""))
    if not price:
        return 0.0
    days = max(1, int(price.get("period_days") or 30))
    return (price["inr"] / 100.0) * (30.0 / days)


def plan_price_inr(tier: str | None) -> float:
    price = PLAN_PRICES.get(normalize_plan(tier or ""))
    return (price["inr"] / 100.0) if price else 0.0
