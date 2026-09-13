"""The plan table is ONE table, and the numbers in it cannot contradict each other.

These are the regressions that made the money lane wrong, each pinned so it cannot come back:

* the tier vocabulary was defined FOUR times — `PLAN_PRICES`/`PLAN_CREDITS` in billing.py,
  `_CREDIT_LIMIT`/`_SEAT_LIMIT` in account_routes and `_DAILY_QUERIES` in intelligence_routes —
  and the four disagreed. `early` (a real Rs.4,500/mo plan) was missing from two of them, so a
  paying Early customer fell to a 100-credit allowance and a 3-seat cap; `startup` was 100,000
  credits in one file and 2,000 in another; `growth`/`scale` were sellable in none of them;
* the daily ceiling was a second, stricter price: trial got 200 queries/day against a 15-day,
  10,000-credit trial, so 7,000 granted credits could not be spent by anyone;
* the action price was a flat 1 credit for calls whose model spend differs ~4x.

Hermetic — no DB, no network, no model.
"""

from __future__ import annotations

import pytest

from genios_engine.platform import billing as B

pytestmark = pytest.mark.unit


def test_every_tier_has_a_complete_row():
    for tier, plan in B.PLANS.items():
        assert plan.tier == tier
        assert plan.credits > 0, tier
        assert plan.seats > 0, tier
        assert plan.period_days > 0, tier
        assert plan.ingest_usd_day > 0, tier


def test_the_two_meters_are_separate_and_both_bounded():
    """Credits meter INTELLIGENCE (what the user clicks); `sync_messages` meters INGESTION (mail
    that arrives whether they want it or not). They are not one meter because one email costs
    MORE to process than one question costs to answer — the L2 extraction prompt is ~2,950 tokens,
    so a message is ~Rs 0.16 against a query's ~Rs 0.12, about 1.3 credits. Charged in credits, a
    3,000-message mailbox would burn ~4,000 credits before the product said anything."""
    for tier, plan in B.PLANS.items():
        assert plan.sync_messages > 0, tier
        assert plan.domains > 0, tier
    assert not any("sync" in action or "ingest" in action or "capture" in action
                   for action in B.COSTS), "ingestion must never appear in the credit price table"


def test_a_plan_can_ingest_more_messages_than_it_can_afford_to_ask_about():
    """The point of the second meter: reading the mailbox must not be rationed by the question
    budget. Every plan ingests a substantial mailbox and still keeps its credits for questions."""
    for tier, plan in B.PLANS.items():
        assert plan.sync_messages >= 1_000, tier


def test_the_plan_ladder_never_goes_backwards():
    """Every axis has to grow with price, or an upgrade takes something away."""
    ladder = ["trial", "individual", "startup", "growth", "enterprise"]
    for lower, higher in zip(ladder, ladder[1:]):
        low, high = B.PLANS[lower], B.PLANS[higher]
        for axis in ("credits", "seats", "domains", "sync_messages", "ingest_usd_day"):
            assert getattr(high, axis) >= getattr(low, axis), f"{axis}: {lower} -> {higher}"


def test_the_free_plan_is_the_smallest_of_everything():
    free = B.PLANS["trial"]
    assert free.credits == 3_000
    assert free.price_inr is None, "the free plan must not be purchasable"
    for tier, plan in B.PLANS.items():
        if tier != "trial":
            assert plan.credits >= free.credits


def test_the_priced_tiers_carry_the_credit_allowances_we_sell():
    assert B.PLANS["individual"].credits == 10_000
    assert B.PLANS["startup"].credits == 100_000


def test_domain_and_seat_limits_match_the_pricing_page():
    assert (B.PLANS["individual"].seats, B.PLANS["individual"].domains) == (1, 1)
    assert (B.PLANS["startup"].seats, B.PLANS["startup"].domains) == (5, 3)
    assert (B.PLANS["growth"].seats, B.PLANS["growth"].domains) == (15, 10)


def test_the_old_tier_names_still_resolve():
    """Live rows carry `early` and `hustler`. Falling to the trial row would silently downgrade a
    paying customer to 3,000 credits and one seat."""
    assert B.plan_of("early").tier == "individual"
    assert B.plan_of("hustler").tier == "individual"
    assert B.plan_of("early").credits == 10_000


def test_only_priced_tiers_are_purchasable():
    """`trial` is granted at signup and `enterprise` is sold by hand. Neither may appear in the
    checkout list, or the upgrade page offers a plan the order route will refuse."""
    assert set(B.PLAN_PRICES) == {"individual", "startup"}
    for tier, price in B.PLAN_PRICES.items():
        assert price["inr"] > 0, tier
        assert price["credits"] == B.PLANS[tier].credits


def test_the_back_compat_views_are_derived_not_typed():
    assert B.PLAN_CREDITS == {t: p.credits for t, p in B.PLANS.items()}
    assert B.TRIAL_DAYS == B.PLANS["trial"].period_days


def test_no_route_keeps_a_rival_plan_table():
    """The specific bug: three modules each carried their own dict of what a tier is worth."""
    from genios_engine.api import account_routes, intelligence_routes
    for module in (account_routes, intelligence_routes):
        for name in ("_CREDIT_LIMIT", "_SEAT_LIMIT", "_DAILY_QUERIES", "_DAILY_QUERIES_DEFAULT"):
            assert not hasattr(module, name), f"{module.__name__} defines a rival {name}"


def test_a_granted_credit_is_always_reachable():
    """The daily ceiling is an abuse guard, never a second price: spending at the ceiling every
    day must be able to consume the whole allowance inside the period."""
    for tier, plan in B.PLANS.items():
        reachable = B.daily_credit_ceiling(tier) * plan.period_days      # points
        assert reachable >= B.plan_points(tier), (
            f"{tier}: {B.to_credits(reachable)} credits reachable against {plan.credits} granted")


def test_the_ceiling_still_binds_below_the_whole_allowance():
    """...and it must not be so loose that it stops being a guard — a single day may never
    drain a whole period."""
    for tier, plan in B.PLANS.items():
        if plan.period_days > B.DAILY_BURST:
            assert B.daily_credit_ceiling(tier) < B.plan_points(tier), tier


def test_seat_and_ingest_limits_answer_for_every_tier():
    for tier in B.PLANS:
        assert B.plan_seat_limit(tier) == B.PLANS[tier].seats
        assert B.plan_ingest_usd_cap(tier) == B.PLANS[tier].ingest_usd_day
        assert B.plan_domain_limit(tier) == B.PLANS[tier].domains
        assert B.plan_sync_messages(tier) == B.PLANS[tier].sync_messages


def test_an_unknown_or_missing_tier_falls_to_the_least_generous_row():
    """A retired tier must stay servable, but must not buy more than a known one."""
    for unknown in ("scale", "", None, "not_a_plan"):
        assert B.plan_of(unknown) is B.PLANS["trial"]
    assert B.plan_of("hustler") is B.PLANS["individual"]     # the documented alias still resolves


def test_a_trial_ingests_far_below_a_paying_tenant():
    """The trial used to inherit the paying tenant's $25/day ingestion ceiling — up to ~$375 of
    model spend to give the product away for 15 days."""
    assert B.plan_ingest_usd_cap("trial") < B.plan_ingest_usd_cap("startup")


def test_deep_analysis_costs_more_than_shallow():
    """Sonnet 5 is ~3.7x Haiku 4.5 per token on the same prompt shape. A flat 1 credit for both
    is how `deep=true` became the product's most expensive call and its cheapest."""
    assert B.cost_of("intelligence_analyze", deep=True) > B.cost_of("intelligence_analyze")
    assert B.cost_of("intelligence_draft") >= B.cost_of("intelligence_query")


def test_an_unpriced_action_is_cheap_never_free():
    """A silent zero is how `analyze` ran free for months without anyone noticing."""
    assert B.cost_of("some_new_endpoint") == B.POINTS_PER_CREDIT
    assert all(price > 0 for price in B.COSTS.values())


# ── the unit table ───────────────────────────────────────────────────────────────────────────
#
# One rule decides every row: the customer pays for WORK THAT PRODUCED SOMETHING FOR THEM.

def test_a_credit_is_divisible_and_the_store_is_whole_numbers():
    """Reading one email is a fifth of a credit. An integer credit rounds that to free or to the
    price of a whole question; points are to credits what paise are to rupees."""
    assert B.POINTS_PER_CREDIT == 100
    assert B.to_credits(20) == 0.2
    assert B.to_points(0.2) == 20
    assert all(isinstance(p, int) for p in B.COSTS.values())


def test_a_charge_never_rounds_down_to_free():
    assert B.to_points(0.001) >= 1
    assert B.to_points(0.204) == 20


def test_junk_duplicates_and_cache_hits_cost_nothing():
    """A gate that filtered spam did work and gave the customer nothing. A noisy mailbox must
    not cost more than a clean one."""
    for unit in B.FREE_UNITS:
        assert B.cost_of(unit) == 0
        assert B.cost_of(unit, units=10_000) == 0


def test_reading_a_message_costs_a_fraction_of_asking_a_question():
    """Ingestion is included in the shape of the product, not a second question budget."""
    assert B.cost_of("message_read") < B.cost_of("intelligence_query")
    assert B.cost_of("message_read") == B.to_points(0.2)
    assert B.cost_of("document_page") == B.to_points(0.3)


def test_nothing_costs_more_than_two_credits():
    """A single click that costs five of something is a click people stop making."""
    for action, points in B.COSTS.items():
        assert points <= 2 * B.POINTS_PER_CREDIT, action


def test_units_multiply():
    assert B.cost_of("message_read", units=2_500) == 2_500 * B.cost_of("message_read")
    assert B.to_credits(B.cost_of("message_read", units=2_500)) == 500.0


def test_zero_units_is_free_not_a_minimum_charge():
    assert B.cost_of("message_read", units=0) == 0


def test_a_realistic_first_sync_leaves_the_free_plan_room_to_think():
    """5,000 messages arrive, ~2,500 are junk. The junk is free; the 2,500 read cost 500 credits
    of a 3,000-credit plan, leaving 2,500 for questions."""
    read = B.cost_of("message_read", units=2_500)
    junk = B.cost_of("message_dropped_as_junk", units=2_500)
    spent = B.to_credits(read + junk)
    assert spent == 500.0
    assert B.PLANS["trial"].credits - spent >= 2_000
