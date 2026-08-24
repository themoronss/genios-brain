"""Layer 5.2 · Phase 2 — the Delivery Orchestrator's resolve step.

Composes the seven responsibilities into one materialised ``DeliveryObject``: resolve the current
recipient and gate it on the evidence ACL (audience), read the expiring context lease (presence),
build the lawful route ladder and pick the format (routing), and stamp the scheduling priority.
It resolves; it does not send — the outbox spine (Phase 3) claims and dispatches. Pure over its
injected directory/presence, so a resolution is replayable and unit-testable without a database.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from genios_engine.contracts.delivery import (
    DeliveryObject,
    priority_from_band,
)
from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.deliver.audience import ResolvedRecipient, resolve_recipient
from genios_engine.deliver.presence import PresenceContext
from genios_engine.deliver.routing import NoRouteError, build_route_ladder, plan_format
from genios_engine.executive.assignment import SeatDirectory

_CHANNEL_CLASS: dict[str, ChannelClass] = {
    "slack": ChannelClass.CHAT, "teams": ChannelClass.CHAT, "webhook": ChannelClass.CHAT,
    "in_app": ChannelClass.IN_APP, "dashboard": ChannelClass.IN_APP,
    "api": ChannelClass.AGENT, "agent_push": ChannelClass.AGENT,
    "email": ChannelClass.EMAIL,
}


def channel_class_of(channel: str) -> ChannelClass:
    """The physics of a concrete channel — used to derive format and intrusiveness."""
    return _CHANNEL_CLASS.get(channel, ChannelClass.IN_APP)


class Unroutable(Exception):
    """The delivery cannot be lawfully routed — the caller writes a materialization failure."""

    def __init__(self, reason_code: str, recipient: ResolvedRecipient | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.recipient = recipient


def resolve(*, org_id: str, delivery_id: str, execution_id: str, execution_hash: str,
            band: str, interrupt: bool, audience: AudienceClass, recipient: str | None,
            dedupe_key: str, directory: SeatDirectory,
            available_channels: list[str], can_view: Callable[[str], bool],
            now: datetime, presence: PresenceContext | None = None,
            agent_route: str | None = None, restricted: bool = False,
            destination: str | None = None, daily_budget: int | None = None,
            source: dict | None = None,
            authority_expires_at: datetime | None = None) -> DeliveryObject:
    """Resolve one commitment/event into a v2 DeliveryObject, or raise ``Unroutable``."""
    rr = resolve_recipient(recipient=recipient, audience=audience, directory=directory,
                           can_view=can_view)
    if not rr.authorized and audience is not AudienceClass.ADMIN_QUEUE:
        # No current, ACL-authorised person/agent to receive → fail closed (law 7).
        raise Unroutable(rr.reason_code, rr)

    # Presence removes the *interruption*, not the delivery. Default is "interruptible" when there
    # is no live lease — we only downgrade a push to a pull surface on a KNOWN focus/busy signal.
    # Scheduling priority is Layer 5's intent and is NOT lowered by presence: a busy person's
    # critical item is still critical, it just waits on a durable surface instead of a push.
    interruptible = presence.interruptible(now) if (presence and presence.is_live(now)) else True

    ladder = build_route_ladder(
        audience=audience, band=band, interrupt=interrupt,
        available_channels=available_channels, agent_route=agent_route,
        restricted=restricted, recipient_authorized=rr.authorized, push_allowed=interruptible)

    channel = ladder[0]
    cclass = channel_class_of(channel)
    return DeliveryObject(
        org_id=org_id, delivery_id=delivery_id, execution_id=execution_id,
        execution_hash=execution_hash, audience=audience, channel=channel, channel_class=cclass,
        fmt=plan_format(channel, cclass), priority=priority_from_band(band, interrupt),
        band=band, dedupe_key=dedupe_key, route_ladder=ladder, recipient=rr.recipient,
        destination=destination, daily_budget=daily_budget, source=source or {},
        authority_expires_at=authority_expires_at)


__all__ = ["Unroutable", "channel_class_of", "resolve"]
