"""Layer 5.2 · Phase 2 — deterministic routing. No model ever chooses a route or a format.

This is the heart of the Destination Router + Channel Planner: given a resolved audience, the
evidence's visibility, the loudness and the channels actually available to a recipient, it builds
one stable primary→fallback **route ladder** and picks the concrete **format** for each rung —
by rule, never by inference. The seven routing laws from the spec live here as executable code so
they cannot drift into prose.

Purity: this module takes what it needs as arguments (available channels, the agent route, whether
the evidence is restricted) and returns a ladder. The orchestrator fetches those facts from the
directory/registry; the laws themselves read nothing and are fully replayable.
"""
from __future__ import annotations

from collections.abc import Sequence

from genios_engine.contracts.delivery import (
    DeliveryFormat,
    DeliveryPriority,
    priority_from_band,
)
from genios_engine.contracts.execution import AudienceClass, ChannelClass

#: The reserved agent transports. A human delivery may never ride these (law 1), and an agent may
#: ride ONLY these (law 2) — never a human dashboard with an agent recipient.
AGENT_TRANSPORTS: frozenset[str] = frozenset({"agent_push", "api"})

#: The durable pull surface every human recipient always has. It wakes nobody, so it is the safe
#: floor of every human ladder and the sole rung for non-intrusive priorities (law 4).
PULL_SURFACE = "in_app"

#: Channels that physically interrupt (a push). Preferred first for high/critical work (law 3).
PUSH_CHANNELS: frozenset[str] = frozenset({"slack", "teams"})


class NoRouteError(ValueError):
    """No lawful channel exists for this delivery — the caller must fail closed.

    Raised, not returned as an empty ladder, because a delivery with no route is not a quiet
    success: it is a materialisation failure that operations must see (law 7). The orchestrator
    catches this and writes a ``delivery_materialization_failures`` row.
    """


def _dedupe_preserving_order(channels: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for ch in channels:
        if ch and ch not in seen:
            seen.add(ch)
            out.append(ch)
    return tuple(out)


def build_route_ladder(*, audience: AudienceClass, band: str, interrupt: bool,
                       available_channels: Sequence[str], agent_route: str | None = None,
                       restricted: bool = False,
                       recipient_authorized: bool = True) -> tuple[str, ...]:
    """The primary→fallback ladder one logical delivery walks. Enforces the seven routing laws.

    - ``audience`` AGENT → only a signed agent push / API inbox (law 2); human audiences never
      touch an agent transport (law 1).
    - ``restricted`` (participants/private evidence) requires ``recipient_authorized``; otherwise
      there is no lawful route and we fail closed (law 7) rather than fall back to an admin.
    - High/critical prefer an available push channel, then the pull surface (law 3); medium/low/
      background land only on the durable pull surface (law 4).
    - ``available_channels`` is the recipient's configured/authenticated set; unknown channels are
      dropped rather than invented.
    """
    if audience is AudienceClass.AGENT:
        # Law 2: an agent gets an agent transport or nothing — never a human surface.
        if agent_route is None or agent_route not in AGENT_TRANSPORTS:
            raise NoRouteError("agent delivery requires a signed agent push or API inbox route")
        return (agent_route,)

    # Human audiences from here down. Law 1: strip any agent transport that leaked into the set.
    human_channels = [c for c in available_channels if c not in AGENT_TRANSPORTS]

    # Law 7: restricted evidence goes only to a visibility-authorised recipient, else fail closed.
    if restricted and not recipient_authorized:
        raise NoRouteError("restricted evidence has no visibility-authorised recipient")

    priority = priority_from_band(band, interrupt)
    intrusive = priority in (DeliveryPriority.CRITICAL, DeliveryPriority.HIGH)

    if intrusive:
        # Law 3: prefer a push channel the recipient actually has, then always the durable floor.
        pushes = [c for c in human_channels if c in PUSH_CHANNELS]
        ladder = _dedupe_preserving_order([*pushes, PULL_SURFACE, *human_channels])
    else:
        # Law 4: non-intrusive work is a pull-surface batch; no second "digest" duplicate (law 5).
        ladder = (PULL_SURFACE,)

    if not ladder:
        raise NoRouteError("no lawful channel available for this delivery")
    return ladder


def plan_format(channel: str, channel_class: ChannelClass) -> DeliveryFormat:
    """Pick the concrete render shape for a channel — deterministic table, never a model."""
    table = {
        "slack": DeliveryFormat.CHAT_MESSAGE,
        "teams": DeliveryFormat.CHAT_MESSAGE,
        "in_app": DeliveryFormat.CARD,
        "dashboard": DeliveryFormat.CARD,
        "webhook": DeliveryFormat.WEBHOOK_PAYLOAD,
        "api": DeliveryFormat.AGENT_ENVELOPE,
        "agent_push": DeliveryFormat.AGENT_ENVELOPE,
        "extension": DeliveryFormat.INLINE_SUGGESTION,
        "rest": DeliveryFormat.REST_RESOURCE,
    }
    if channel in table:
        return table[channel]
    # Fall back on the intent when the concrete name is unknown, still without inference.
    if channel_class is ChannelClass.CHAT:
        return DeliveryFormat.CHAT_MESSAGE
    if channel_class is ChannelClass.AGENT:
        return DeliveryFormat.AGENT_ENVELOPE
    return DeliveryFormat.CARD


def is_agent_transport(channel: str) -> bool:
    return channel in AGENT_TRANSPORTS


__all__ = ["AGENT_TRANSPORTS", "PULL_SURFACE", "PUSH_CHANNELS", "NoRouteError",
           "build_route_ladder", "is_agent_transport", "plan_format"]
