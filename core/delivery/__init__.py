"""g-i-7 Delivery — agents + humans + envelope-always.

Per MD g-i-7 §0 (the law):
- Intelligence NEVER leaves the system "naked"
- Every delivery (agent or human) carries the Envelope:
    recommendation + confidence + derivation + uncertainty + route + asOf + decision_id
- Agent delivery > human delivery (effort priority — product = drive agents, not dashboards)
- Naked recommendations FORBIDDEN

Public API:
    from core.delivery import (
        Envelope, build_envelope, NakedOutputError,
        agent_router, agent_feed_router, dashboard_router,
        ChannelAdapter, SlackChannel, EmailChannel, WebhookChannel,
        FeedbackAction, capture_feedback, FeedbackToCorrection,
        MCPServer, MCPTool,
    )
"""

from core.delivery.channels.base import ChannelAdapter, DeliveryAttempt
from core.delivery.channels.email import EmailChannel
from core.delivery.channels.slack import SlackChannel
from core.delivery.channels.webhook_out import WebhookChannel
from core.delivery.envelope import Envelope, NakedOutputError, build_envelope
from core.delivery.feedback_capture import (
    FeedbackAction,
    FeedbackToCorrection,
    capture_feedback,
)
from core.delivery.mcp_server import MCPServer, MCPTool

__all__ = [
    "ChannelAdapter",
    "DeliveryAttempt",
    "EmailChannel",
    "Envelope",
    "FeedbackAction",
    "FeedbackToCorrection",
    "MCPServer",
    "MCPTool",
    "NakedOutputError",
    "SlackChannel",
    "WebhookChannel",
    "build_envelope",
    "capture_feedback",
]
