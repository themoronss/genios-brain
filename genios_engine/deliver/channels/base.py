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
    """Registry — two human channels (slack, email) and one agent transport. Unknown name →
    None (the outbox parks the row with a clear reason; never a crash).

    `email` is registered with NO transport (GeniOS-011 S37.U2): the provider is S37.U1, Rohit's
    decision, so `channels/email.TRANSPORTS` is empty and an email send is a failed result until
    one is wired. Registering the adapter is what lets `deliverable_channels` contain `email` for
    an org that has an active email row — no org has one until S37.U3."""
    if name == "slack":
        from genios_engine.deliver.channels.slack import SlackWebhookChannel
        return SlackWebhookChannel()
    if name == "email":
        from genios_engine.deliver.channels.email import EmailChannel
        return EmailChannel()
    if name == "agent_push":
        from genios_engine.deliver.channels.agent import AgentWebhookChannel
        return AgentWebhookChannel()
    return None
