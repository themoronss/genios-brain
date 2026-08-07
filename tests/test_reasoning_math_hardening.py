from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.reason import scoring
from genios_engine.reason.engine import NodeContext, _freshness, evaluate
from genios_engine.reason.foresight import deal_close_probability, wilson_lower_bound
from genios_engine.reason.rules import Rule


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_public_scoring_math_rejects_non_finite_values(bad):
    calls = [
        lambda: scoring.rhu(bad),
        lambda: scoring.urgency("elapsed", bad, 3),
        lambda: scoring.urgency("elapsed", 4, bad),
        lambda: scoring.impact(bad, 100),
        lambda: scoring.impact(100, bad),
        lambda: scoring.recency(bad),
        lambda: scoring.recency(1, half_life=bad),
        lambda: scoring.confidence(bad),
        lambda: scoring.confidence(0.8, freshness=bad),
        lambda: scoring.score(bad, 50, 50, 50),
    ]
    for call in calls:
        with pytest.raises(ValueError):
            call()


def test_bounded_scoring_inputs_are_clamped_and_outputs_stay_bounded():
    assert scoring.urgency("elapsed", -5, 3, floor=-20) == 0
    assert scoring.urgency("elapsed", 0, 3, floor=500) == 100
    assert scoring.impact(-500, 100, linked_deal=False) == 0
    assert scoring.impact(500, 100, linked_deal=False, tier_mult=-2) == 0
    assert scoring.confidence(5, freshness=-2, corroboration=4) == 70

    result, inputs = scoring.score(-10, 120, 500, 130)
    assert result == 55
    assert inputs == {"U": 0, "I": 100, "R": 100, "C": 100, "terms_bp": 5500}


def test_score_curves_have_their_expected_monotonic_direction():
    assert [scoring.urgency("elapsed", h, 12) for h in (0, 6, 12, 48)] == sorted(
        scoring.urgency("elapsed", h, 12) for h in (0, 6, 12, 48))
    recencies = [scoring.recency(h) for h in (0, 24, 72, 240)]
    assert recencies == sorted(recencies, reverse=True)
    impacts = [scoring.impact(v, 100, linked_deal=False) for v in (0, 25, 50, 100, 200)]
    assert impacts == sorted(impacts)

    base, _ = scoring.score(20, 40, 60, 80)
    more_urgent, _ = scoring.score(21, 40, 60, 80)
    more_confident, _ = scoring.score(20, 40, 60, 81)
    assert more_urgent >= base
    assert more_confident >= base


def test_invalid_weight_vectors_and_curve_parameters_are_rejected():
    with pytest.raises(ValueError, match="sum to 100"):
        scoring.score(50, 50, 50, 50, {"u": 50, "i": 50, "r": 50})
    with pytest.raises(ValueError, match="sum to 100"):
        scoring.confidence(0.8, c_weights={"conf": 50, "fresh": 50, "corr": 50})
    with pytest.raises(ValueError, match="greater than zero"):
        scoring.recency(10, half_life=0)
    with pytest.raises(ValueError, match="kind"):
        scoring.urgency("mystery", 10, 3)


@pytest.mark.parametrize("occurred_at", ["not-a-timestamp", math.nan, math.inf])
def test_malformed_freshness_fails_closed(occurred_at):
    assert _freshness(occurred_at, NOW) == 0.0


def test_future_freshness_fails_closed_and_valid_freshness_still_decays():
    assert _freshness(NOW + timedelta(seconds=1), NOW) == 0.0
    assert _freshness(NOW, NOW) == 1.0
    assert 0.0 < _freshness(NOW - timedelta(days=30), NOW) < 1.0


@pytest.mark.parametrize("op", ["=", "!=", ">", ">=", "<", "<="])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_fact_values_cannot_fire_numeric_rules(op, bad):
    ctx = NodeContext(node_id="deal_1", node_type="deal",
                      facts={"deal.value": {"value": bad}})
    rule = Rule(id="finite_only", level="predictive", scope="deal",
                when=[{"path": "deal.value", "op": op, "value": 10}],
                urgency={"type": "elapsed", "path": "deal.last_inbound", "h": 3},
                reason_code="finite_only")
    assert evaluate(ctx, rule, NOW) is False


def test_foresight_is_duplicate_invariant_and_preserves_first_seen_driver_order():
    unique = deal_close_probability(
        0.6, ["objection_open", "buying_signal", "competitor_in_live_deal"])
    duplicated = deal_close_probability(
        0.6, ["objection_open", "objection_open", "buying_signal", "buying_signal",
              "competitor_in_live_deal", "objection_open"])
    assert duplicated == unique
    assert [d["signal"] for d in duplicated["drivers"]] == [
        "objection_open", "buying_signal", "competitor_in_live_deal"]


def test_foresight_validates_and_clamps_its_numeric_boundaries():
    assert deal_close_probability(-10, [])["probability"] == 0.05
    assert deal_close_probability(10, [])["probability"] == 0.95
    with pytest.raises(ValueError):
        deal_close_probability(math.nan, [])
    with pytest.raises(ValueError):
        deal_close_probability(0.5, ["buying_signal", 42])
    with pytest.raises(ValueError):
        wilson_lower_bound(2, 1)
    with pytest.raises(ValueError):
        wilson_lower_bound(-1, 10)
    with pytest.raises(ValueError):
        wilson_lower_bound(1, 10, z=math.inf)
