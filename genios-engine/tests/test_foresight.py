from __future__ import annotations

from genios_engine.reason.foresight import (
    deal_close_probability,
    wilson_lower_bound,
)

# C4 foresight — pure math (the DB base-rate/win-rate queries are proven live against Supabase).


def test_wilson_lower_bound_penalises_small_samples():
    # 1/1 must NOT read as 100% — the lower bound is far below the point estimate
    assert wilson_lower_bound(1, 1) < 0.85
    # more evidence at the same rate → a tighter (higher) lower bound
    assert wilson_lower_bound(50, 50) > wilson_lower_bound(5, 5)
    assert wilson_lower_bound(0, 0) == 0.0
    assert 0.0 <= wilson_lower_bound(7, 10) <= 1.0


def test_close_probability_moves_with_signals_and_stays_bounded():
    base = 0.5
    # negative concerns drag it down
    down = deal_close_probability(base, ["objection_open", "competitor_in_live_deal"])
    assert down["probability"] < base
    assert down["slip_risk"] == round(1 - down["probability"], 3)
    assert {d["signal"] for d in down["drivers"]} == {"objection_open", "competitor_in_live_deal"}
    # a buying signal lifts it
    up = deal_close_probability(base, ["buying_signal"])
    assert up["probability"] > base


def test_close_probability_is_clamped():
    piled = ["objection_open", "competitor_in_live_deal", "going_dark_after_proposal",
             "deal_sentiment_negative", "stalled_deal", "single_threaded_deal"]
    assert deal_close_probability(0.3, piled)["probability"] >= 0.05    # floor, never negative
    assert deal_close_probability(0.9, ["buying_signal"] * 5)["probability"] <= 0.95  # ceil


def test_unknown_signals_are_ignored():
    assert deal_close_probability(0.4, ["some_unmodelled_code"])["probability"] == 0.4
