from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import RawObject, SourceBatch


class FakeGmailConnector:
    """Deterministic fake for dev/tests — no live Composio/Google needed.
    Same shape a real connector produces, so the spine is exercised end to end."""

    source = "gmail"

    def __init__(self, org_id: str = "org_demo", connection_id: str = "con_demo") -> None:
        self.org_id = org_id
        self.connection_id = connection_id

    def _sample(self) -> list[RawObject]:
        return [
            RawObject(
                source="gmail",
                object_type="email_message",
                source_object_id="msg_18c4a9e2f7",
                occurred_at=datetime(2026, 7, 28, 9, 14, 22, tzinfo=timezone.utc),
                actor_email="priya@acme.com",
                actor_type="external_contact",
                parent_object_id="thread_18c4a",
                raw={
                    "subject": "Revised contract",
                    "snippet": "Budget is approved. Can you send the revised contract by Friday?",
                },
            ),
        ]

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return SourceBatch(objects=self._sample(), next_cursor="cursor_end")

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        return SourceBatch(objects=self._sample(), next_cursor=cursor)

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return {"body": "Budget is approved. Can you send the revised contract by Friday?"}
