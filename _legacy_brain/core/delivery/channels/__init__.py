"""Channel adapters for human-facing delivery (Slack / email / webhook).

Each channel implements the ChannelAdapter protocol — pluggable so a customer
can use Slack OR email OR a custom webhook without engine changes (same pattern
as g-i-1 MemoryAdapter).

Per MD g-i-7:
- urgent -> interrupt (Slack DM)
- non-urgent -> digest (email batch)
- per-user push budget (already enforced by g-i-4 deliver — channels are dumb pipes)
"""

from core.delivery.channels.base import ChannelAdapter, DeliveryAttempt, DeliveryError
from core.delivery.channels.email import EmailChannel
from core.delivery.channels.slack import SlackChannel
from core.delivery.channels.webhook_out import WebhookChannel

__all__ = [
    "ChannelAdapter",
    "DeliveryAttempt",
    "DeliveryError",
    "EmailChannel",
    "SlackChannel",
    "WebhookChannel",
]
