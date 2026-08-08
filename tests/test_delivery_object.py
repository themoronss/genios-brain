"""Layer 5.2 · Phase 1 — the v2 DeliveryObject contract.

Pure tests: identity is content-addressed over what a delivery *is*, never its routing cursor or
clocks, so a fallback or a retry is the same delivery — the property the deduper and Layer 6 both
depend on.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.delivery import (
    DELIVERY_RESULT_VERSION,
    DeliveryFormat,
    DeliveryLifecycle,
    DeliveryObject,
    DeliveryPriority,
    delivery_can_transition,
    priority_from_band,
)
from genios_engine.contracts.execution import AudienceClass, ChannelClass


def _obj(**over) -> DeliveryObject:
    base = dict(
        org_id="org_1", delivery_id="del_1", execution_id="exec_1", execution_hash="h_abc",
        audience=AudienceClass.OWNER, channel="slack", channel_class=ChannelClass.CHAT,
        fmt=DeliveryFormat.CHAT_MESSAGE, priority=DeliveryPriority.HIGH, band="high",
        dedupe_key="dk_1", route_ladder=("slack", "in_app"), recipient="seat_1", daily_budget=20)
    base.update(over)
    return DeliveryObject(**base)


# ---- priority mapping (deterministic, no model) --------------------------------------------

def test_priority_from_band_is_the_full_deterministic_matrix():
    assert priority_from_band("critical", True) is DeliveryPriority.CRITICAL
    assert priority_from_band("critical", False) is DeliveryPriority.HIGH
    assert priority_from_band("high", True) is DeliveryPriority.HIGH
    assert priority_from_band("high", False) is DeliveryPriority.MEDIUM
    assert priority_from_band("standard", True) is DeliveryPriority.LOW
    assert priority_from_band("standard", False) is DeliveryPriority.BACKGROUND


def test_priority_from_band_rejects_an_unknown_band():
    with pytest.raises(ValueError):
        priority_from_band("apocalyptic", True)


def test_priority_rank_orders_weakest_first():
    assert _obj(priority=DeliveryPriority.CRITICAL).priority_rank > _obj(
        priority=DeliveryPriority.BACKGROUND).priority_rank


# ---- identity is stable across live-state moves --------------------------------------------

def test_semantic_hash_survives_fallback_and_retry():
    o = _obj()
    assert o.semantic_hash() == o.advanced().semantic_hash(), "a fallback is the same delivery"
    from dataclasses import replace
    assert o.semantic_hash() == replace(o, retry_generation=3).semantic_hash(), \
        "a retry is the same delivery"


def test_identity_excludes_cursor_retry_and_format():
    o = _obj()
    assert "route_cursor" not in o.identity and "retry_generation" not in o.identity
    assert "fmt" not in o.identity, "format is a rendering choice, not delivery identity"


def test_advanced_walks_the_ladder_then_refuses_past_the_end():
    o = _obj(route_ladder=("slack", "in_app", "email"))
    assert o.live_channel == "slack"
    step1 = o.advanced()
    assert step1.channel == "in_app" and step1.route_cursor == 1
    step2 = step1.advanced()
    assert step2.channel == "email" and step2.route_cursor == 2
    with pytest.raises(ValueError, match="exhausted"):
        step2.advanced()


# ---- construction guards -------------------------------------------------------------------

def test_version_defaults_to_the_result_projection():
    assert _obj().schema_version == DELIVERY_RESULT_VERSION == "delivery-result.v2"


def test_empty_route_ladder_is_not_a_deliverable():
    with pytest.raises(ValueError, match="route ladder"):
        _obj(route_ladder=())


def test_live_channel_must_be_a_rung_of_its_own_ladder():
    with pytest.raises(ValueError, match="own route ladder"):
        _obj(channel="teams", route_ladder=("slack", "in_app"))


def test_cursor_cannot_point_past_the_ladder():
    with pytest.raises(ValueError, match="past the end"):
        _obj(route_ladder=("slack",), route_cursor=1)


def test_negative_counters_are_rejected():
    with pytest.raises(ValueError):
        _obj(retry_generation=-1)
    with pytest.raises(ValueError):
        _obj(daily_budget=-5)


def test_bad_band_is_rejected():
    with pytest.raises(ValueError, match="band"):
        _obj(band="nuclear")


# ---- lifecycle vocabulary ------------------------------------------------------------------

def test_lifecycle_allows_the_engagement_path():
    assert delivery_can_transition(DeliveryLifecycle.QUEUED, DeliveryLifecycle.DELIVERED)
    assert delivery_can_transition(DeliveryLifecycle.DELIVERED, DeliveryLifecycle.VIEWED)
    assert delivery_can_transition(DeliveryLifecycle.VIEWED, DeliveryLifecycle.ACCEPTED)
    assert delivery_can_transition(DeliveryLifecycle.ACCEPTED, DeliveryLifecycle.EXECUTED)


def test_terminals_never_reopen():
    for terminal in (DeliveryLifecycle.EXECUTED, DeliveryLifecycle.SUPPRESSED,
                     DeliveryLifecycle.CANCELLED, DeliveryLifecycle.FAILED,
                     DeliveryLifecycle.IGNORED, DeliveryLifecycle.EXPIRED):
        assert not delivery_can_transition(terminal, DeliveryLifecycle.DELIVERED)


def test_suppressed_and_cancelled_are_distinct_terminals():
    # both terminal, but they are different facts with different fixes — never merged
    assert DeliveryLifecycle.SUPPRESSED != DeliveryLifecycle.CANCELLED
    assert not delivery_can_transition(DeliveryLifecycle.QUEUED, DeliveryLifecycle.VIEWED)


def test_semantic_dict_round_trips_the_identity_fields():
    o = _obj()
    d = o.to_semantic_dict()
    assert d["delivery_id"] == "del_1" and d["execution_hash"] == "h_abc"
    assert d["priority"] == "high" and d["fmt"] == "chat_message"
