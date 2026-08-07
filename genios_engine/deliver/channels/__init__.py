"""L6 channels — how intelligence reaches a HUMAN.

Until this package existed, the only outbound transport was an unretried webhook to
machine agents: every grounded, scored card waited for someone to open a dashboard.
v1 ships exactly ONE human channel (Slack incoming webhook) plus the adapter seam —
the protocol is extracted from a working channel, not designed for ten imaginary ones.
Delivery itself is owned by deliver/outbox.py (queued → retried → audited); a channel
only knows how to FORMAT and SEND one message."""
from genios_engine.deliver.channels.base import ChannelResult, get_channel

__all__ = ["ChannelResult", "get_channel"]
