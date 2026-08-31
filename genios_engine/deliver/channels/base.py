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


class Channel(Protocol):
    name: str

    def send(self, payload: dict, config: dict) -> ChannelResult: ...


def get_channel(name: str):
    """Registry — v1 has exactly one human channel. Unknown name → None (the outbox
    marks the row failed_terminal with a clear reason; never a crash)."""
    if name == "slack":
        from genios_engine.deliver.channels.slack import SlackWebhookChannel
        return SlackWebhookChannel()
    if name == "agent_push":
        from genios_engine.deliver.channels.agent import AgentWebhookChannel
        return AgentWebhookChannel()
    return None
