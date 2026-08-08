"""Layer 5.2 · Phase 2 — scheduler, presence, audience and the orchestrator resolve step.

Pure/injected: a static directory and an explicit ``now`` stand in for the live org, so every
resolution is replayable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.delivery import DeliveryFormat, DeliveryObject, DeliveryPriority
from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.deliver.audience import resolve_recipient
from genios_engine.deliver.orchestrator import Unroutable, channel_class_of, resolve
from genios_engine.deliver.presence import PresenceContext, absent
from genios_engine.deliver.scheduler import effective_rank, schedule_order
from genios_engine.executive.assignment import StaticSeatDirectory

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
DIR = StaticSeatDirectory(seats={
    "seat_rep": {"email": "rep@x.com", "active": True, "role": "member", "manager_seat_id": "seat_mgr"},
    "seat_mgr": {"email": "mgr@x.com", "active": True, "role": "manager"},
    "seat_gone": {"email": "gone@x.com", "active": False, "role": "member"},
    "seat_admin": {"email": "admin@x.com", "active": True, "role": "admin"},
})
ALLOW_ALL = lambda seat: True


# ---- scheduler ------------------------------------------------------------------------------

def test_effective_rank_ages_a_waiting_row_upward():
    base = effective_rank(DeliveryPriority.BACKGROUND, queued_at=NOW, now=NOW)
    aged = effective_rank(DeliveryPriority.BACKGROUND, queued_at=NOW - timedelta(hours=9), now=NOW)
    assert aged > base                                   # two 4h steps => +2 classes
    capped = effective_rank(DeliveryPriority.CRITICAL, queued_at=NOW - timedelta(days=2), now=NOW)
    assert capped == effective_rank(DeliveryPriority.CRITICAL, queued_at=NOW, now=NOW)  # cap holds


def test_schedule_order_is_priority_then_fifo():
    rows = [
        {"id": "old_bg", "priority": DeliveryPriority.BACKGROUND, "queued_at": NOW - timedelta(hours=1)},
        {"id": "new_crit", "priority": DeliveryPriority.CRITICAL, "queued_at": NOW},
        {"id": "old_med", "priority": DeliveryPriority.MEDIUM, "queued_at": NOW - timedelta(hours=1)},
        {"id": "new_med", "priority": DeliveryPriority.MEDIUM, "queued_at": NOW},
    ]
    order = [r["id"] for r in schedule_order(rows, now=NOW)]
    assert order[0] == "new_crit"                        # highest priority first
    assert order.index("old_med") < order.index("new_med")  # within a class, oldest first


# ---- presence -------------------------------------------------------------------------------

def test_presence_stale_lease_is_not_interruptible():
    ctx = PresenceContext(seat_id="seat_rep", expires_at=NOW - timedelta(minutes=1), active=True,
                          current_surface="slack")
    assert not ctx.is_live(NOW)
    assert not ctx.interruptible(NOW)
    assert ctx.surface(NOW) is None                      # expired lease exposes no surface


def test_presence_focus_and_busy_block_interruption_but_lease_live():
    focus = PresenceContext(seat_id="s", expires_at=NOW + timedelta(minutes=5), focus=True)
    assert focus.is_live(NOW) and not focus.interruptible(NOW)
    busy = PresenceContext(seat_id="s", expires_at=NOW + timedelta(minutes=5),
                           busy_until=NOW + timedelta(minutes=30))
    assert not busy.interruptible(NOW)
    free = PresenceContext(seat_id="s", expires_at=NOW + timedelta(minutes=5), active=True,
                           current_surface="slack")
    assert free.interruptible(NOW) and free.surface(NOW) == "slack"


def test_absent_context_is_expired_immediately():
    assert not absent("seat_rep", NOW).is_live(NOW)


# ---- audience resolution + ACL gate ---------------------------------------------------------

def test_frozen_seat_cannot_receive():
    rr = resolve_recipient(recipient="seat_gone", audience=AudienceClass.OWNER, directory=DIR,
                           can_view=ALLOW_ALL)
    assert not rr.authorized and rr.reason_code == "recipient_inactive"


def test_acl_denied_fails_closed_not_to_an_admin():
    rr = resolve_recipient(recipient="seat_rep", audience=AudienceClass.OWNER, directory=DIR,
                           can_view=lambda seat: False)
    assert not rr.authorized and rr.reason_code == "acl_denied"


def test_agent_recipient_resolves_by_identity():
    rr = resolve_recipient(recipient="agent_7", audience=AudienceClass.AGENT, directory=DIR,
                           can_view=lambda seat: False)   # email-view does not apply to a machine
    assert rr.authorized and rr.recipient == "agent_7"


# ---- orchestrator.resolve -------------------------------------------------------------------

def _resolve(**over):
    base = dict(org_id="org_1", delivery_id="del_1", execution_id="exec_1", execution_hash="h",
                band="critical", interrupt=True, audience=AudienceClass.OWNER, recipient="seat_rep",
                dedupe_key="dk_1", directory=DIR, available_channels=["slack", "in_app"],
                can_view=ALLOW_ALL, now=NOW)
    base.update(over)
    return resolve(**base)


def test_resolve_builds_a_pushing_critical_delivery():
    obj = _resolve()
    assert isinstance(obj, DeliveryObject)
    assert obj.channel == "slack" and obj.priority is DeliveryPriority.CRITICAL
    assert obj.fmt is DeliveryFormat.CHAT_MESSAGE and obj.recipient == "seat_rep"
    assert obj.route_ladder[-1] == "in_app"             # push, then durable floor


def test_resolve_downgrades_to_pull_when_recipient_is_busy():
    busy = PresenceContext(seat_id="seat_rep", expires_at=NOW + timedelta(minutes=5),
                           busy_until=NOW + timedelta(minutes=30))
    obj = _resolve(presence=busy)
    # busy removes the interruption but not the delivery: it lands on the pull surface, and
    # scheduling priority is still CRITICAL (the work did not become less important).
    assert obj.channel == "in_app" and obj.priority is DeliveryPriority.CRITICAL


def test_resolve_fails_closed_when_acl_denies_every_seat():
    with pytest.raises(Unroutable):
        _resolve(can_view=lambda seat: False)


def test_resolve_agent_uses_agent_route_only():
    obj = _resolve(audience=AudienceClass.AGENT, recipient="agent_7", agent_route="api",
                   available_channels=["slack", "in_app"])
    assert obj.route_ladder == ("api",) and obj.channel == "api"


def test_channel_class_of_maps_physics():
    assert channel_class_of("slack") is ChannelClass.CHAT
    assert channel_class_of("in_app") is ChannelClass.IN_APP
    assert channel_class_of("api") is ChannelClass.AGENT
