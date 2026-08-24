"""Layer 5.2 · Phase 2 — the seven routing laws, as executable tests.

Pure: no DB, no model. Each law is a property of ``build_route_ladder`` / ``plan_format``.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.delivery import DeliveryFormat
from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.deliver.routing import (
    NoRouteError,
    build_route_ladder,
    is_agent_transport,
    plan_format,
)


# Law 1 — human delivery never uses the reserved agent transport.
def test_law1_human_ladder_never_contains_an_agent_transport():
    ladder = build_route_ladder(audience=AudienceClass.OWNER, band="critical", interrupt=True,
                                available_channels=["slack", "api", "agent_push", "in_app"])
    assert not any(is_agent_transport(c) for c in ladder)
    assert "slack" in ladder and "in_app" in ladder


# Law 2 — an agent gets only a signed push / API inbox, or no route at all.
def test_law2_agent_uses_only_an_agent_transport():
    assert build_route_ladder(audience=AudienceClass.AGENT, band="high", interrupt=True,
                              available_channels=["slack", "in_app"], agent_route="api") == ("api",)


def test_law2_agent_without_a_valid_agent_route_fails_closed():
    with pytest.raises(NoRouteError):
        build_route_ladder(audience=AudienceClass.AGENT, band="high", interrupt=True,
                           available_channels=["slack"], agent_route=None)
    with pytest.raises(NoRouteError):
        build_route_ladder(audience=AudienceClass.AGENT, band="high", interrupt=True,
                           available_channels=["slack"], agent_route="slack")  # not an agent route


# Law 3 — high/critical prefer an available push, then always the durable floor.
def test_law3_intrusive_prefers_push_then_falls_back_to_pull_surface():
    ladder = build_route_ladder(audience=AudienceClass.OWNER, band="critical", interrupt=True,
                                available_channels=["slack", "in_app"])
    assert ladder[0] == "slack" and ladder[-1] == "in_app"


def test_law3_intrusive_without_a_push_channel_still_reaches_the_pull_surface():
    ladder = build_route_ladder(audience=AudienceClass.OWNER, band="high", interrupt=True,
                                available_channels=["in_app"])
    assert ladder == ("in_app",)


# Law 4 — non-intrusive work lands only on the durable pull surface (no push).
def test_law4_non_intrusive_is_pull_only():
    for band, interrupt in [("standard", False), ("standard", True), ("high", False)]:
        ladder = build_route_ladder(audience=AudienceClass.OWNER, band=band, interrupt=interrupt,
                                    available_channels=["slack", "teams", "in_app"])
        assert ladder == ("in_app",), f"{band}/{interrupt} should be pull-only"


# Law 5 — one logical delivery: the ladder has no duplicated rung.
def test_law5_ladder_has_no_duplicate_rungs():
    ladder = build_route_ladder(audience=AudienceClass.OWNER, band="critical", interrupt=True,
                                available_channels=["slack", "slack", "in_app", "in_app"])
    assert len(ladder) == len(set(ladder))


# Law 6 — fallback advances along the same ladder (property proven on DeliveryObject.advanced,
# here we assert the ladder is an ordered sequence the cursor can walk).
def test_law6_ladder_is_ordered_for_fallback():
    ladder = build_route_ladder(audience=AudienceClass.MANAGER, band="critical", interrupt=True,
                                available_channels=["teams", "in_app"])
    assert ladder[0] == "teams" and "in_app" in ladder[1:]


# Law 7 — participants/private evidence with no authorised recipient fails closed (no admin fallback).
def test_law7_restricted_without_authorised_recipient_fails_closed():
    with pytest.raises(NoRouteError, match="authorised recipient"):
        build_route_ladder(audience=AudienceClass.OWNER, band="critical", interrupt=True,
                           available_channels=["slack", "in_app"],
                           restricted=True, recipient_authorized=False)


def test_law7_restricted_with_authorised_recipient_routes_normally():
    ladder = build_route_ladder(audience=AudienceClass.OWNER, band="critical", interrupt=True,
                                available_channels=["slack", "in_app"],
                                restricted=True, recipient_authorized=True)
    assert ladder[0] == "slack"


# Channel Planner — deterministic format table.
def test_plan_format_is_a_fixed_table():
    assert plan_format("slack", ChannelClass.CHAT) is DeliveryFormat.CHAT_MESSAGE
    assert plan_format("in_app", ChannelClass.IN_APP) is DeliveryFormat.CARD
    assert plan_format("webhook", ChannelClass.CHAT) is DeliveryFormat.WEBHOOK_PAYLOAD
    assert plan_format("api", ChannelClass.AGENT) is DeliveryFormat.AGENT_ENVELOPE
    assert plan_format("extension", ChannelClass.IN_APP) is DeliveryFormat.INLINE_SUGGESTION


def test_plan_format_unknown_channel_falls_back_on_intent_not_inference():
    assert plan_format("mystery", ChannelClass.CHAT) is DeliveryFormat.CHAT_MESSAGE
    assert plan_format("mystery", ChannelClass.AGENT) is DeliveryFormat.AGENT_ENVELOPE
