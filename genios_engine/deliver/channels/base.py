"""Channel adapter seam. A channel does exactly two things: format a payload and send
it. It never decides WHO gets a message, WHETHER one should exist, or WHEN — those are
the outbox's and the pipeline's jobs. Send failures are RESULTS, not exceptions: the
outbox owns retry policy, so a channel that throws would be smuggling policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChannelResult:
    ok: bool
    detail: str = ""                 # error text on failure; never includes the config
    retryable: bool = False
    unknown: bool = False             # provider may have accepted but acknowledgement was lost
    http_status: int | None = None
    retry_after_seconds: int | None = None
    provider_message_id: str | None = None


class Channel(Protocol):
    name: str

    def send(self, payload: dict, config: dict) -> ChannelResult: ...


def get_channel(name: str):
    """The concrete adapter registry. Unknown name is a typed terminal failure, not a crash."""
    if name == "slack":
        from genios_engine.deliver.channels.slack import SlackWebhookChannel
        return SlackWebhookChannel()
    if name == "teams":
        from genios_engine.deliver.channels.teams import TeamsWebhookChannel
        return TeamsWebhookChannel()
    if name == "webhook":
        from genios_engine.deliver.channels.webhook import SignedWebhookChannel
        return SignedWebhookChannel()
    if name == "agent":
        from genios_engine.deliver.channels.agent import AgentWebhookChannel
        return AgentWebhookChannel()
    from genios_engine.deliver.channels.surface import SURFACE_CHANNELS, SurfaceChannel
    if name in SURFACE_CHANNELS:
        return SurfaceChannel(name)
    return None


def supported_channels() -> tuple[str, ...]:
    from genios_engine.deliver.channels.surface import SURFACE_CHANNELS
    return tuple(sorted({"slack", "teams", "webhook", "agent", *SURFACE_CHANNELS}))


__all__ = ["Channel", "ChannelResult", "get_channel", "supported_channels"]
