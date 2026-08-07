"""Layer 5.2 channel adapters.

Slack and Teams provide chat delivery, the generic webhook adapter provides a signed customer
endpoint, and named pull surfaces expose the already-durable outbox payload through the inbox
API. Delivery policy, timing, retry and failover remain in ``deliver/outbox.py``; an adapter
only sends to one concrete destination.
"""
from genios_engine.deliver.channels.base import ChannelResult, get_channel, supported_channels

__all__ = ["ChannelResult", "get_channel", "supported_channels"]
