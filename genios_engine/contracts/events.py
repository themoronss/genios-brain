from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

# Human and agent events re-enter through the same authenticated intake. They are
# first-class: human = strongest correction signal; agent = prevents recommending an
# action an agent already did + enables outcome tracking.

_HUMAN_TYPES = {
    "human.fact_edit", "human.card_wrong", "human.merge_confirm", "human.merge_undo",
    "human.scope_change", "human.park_recover", "human.classification_relabel",
    "human.manual_context",
}


class HumanEvent(BaseModel):
    type: str
    org_id: str
    actor_id: str
    target: dict[str, Any] = Field(default_factory=dict)
    detail: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_known_type(self) -> bool:
        return self.type in _HUMAN_TYPES


class AgentEvent(BaseModel):
    org_id: str
    agent_id: str
    client_event_id: str                       # idempotency key (agent_id + client_event_id)
    action_taken: str                          # controlled vocabulary
    target_hint: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def idempotency_key(self) -> str:
        return f"{self.agent_id}:{self.client_event_id}"


# Controlled agent action vocabulary — unknown actions are rejected, never guessed.
AGENT_ACTIONS = {
    "email_sent", "meeting_booked", "ticket_resolved", "crm_field_changed",
    "invoice_reminder_sent", "document_generated", "approval_requested",
}

# L5 Agent API grants (§5.16) — a SEPARATE scope family from the L1 outcome-event actions above.
# The $15/agent read-and-claim surface is authorized by these; the L1 event-write grant is distinct.
AGENT_API_SCOPES = {"signals.read", "artifacts.read", "signals.claim", "signals.result"}

# Human interaction grants are separate from both executor outcomes and agent polling. A key that
# can merely read signals must never be able to train org-wide calibration or request execution.
HUMAN_API_SCOPES = {
    "insights.read", "cards.read", "feedback.write", "cards.act", "actions.handoff",
}
