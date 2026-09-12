from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from genios_engine.platform.ids import new_id

#: Who a connection belongs to (migration 0138). `workspace` is the org's own connection — every
#: connection that existed before seats. `seat` is one member's own account (their mailbox).
WORKSPACE = "workspace"
SEAT = "seat"
OWNERSHIP_TYPES = (WORKSPACE, SEAT)


def composio_user_id_for(org_id: str, seat_id: str | None = None) -> str:
    """The Composio `user_id` a connection lives under.

    A workspace connection keeps the org id — what every existing connection already carries, so
    nothing already authorised moves. A seat connection gets its OWN Composio user, `{org}:{seat}`:
    Composio keys connected accounts by user id, so sharing the org's would make two members'
    Gmail accounts one account, and a webhook for one indistinguishable from the other.
    """
    return f"{org_id}:{seat_id}" if seat_id else org_id


class Connection(BaseModel):
    """One connected source for ONE org (tenant). This is the per-startup identity —
    it lives in the DB, not in .env. 30 startups = 30 rows. The Composio API key is
    global (GeniOS's); composio_user_id is this connection's label inside Composio (blank for
    non-Composio sources like a client DB). `config` holds source-specific settings
    (e.g. a client DB's db_url / table / watermark) — stored in the capture_scope jsonb.

    `seat_id` set = a SEAT connection (one member's own account; its messages' mailbox owner is
    that seat's address). `seat_id` None = a workspace connection, today's behaviour."""

    connection_id: str = Field(default_factory=lambda: new_id("con"))
    org_id: str                                  # the startup / tenant (ours)
    provider: str = "google"
    source_type: str = "gmail"
    composio_user_id: str = ""                   # Composio label; blank for DB/other sources
    config: dict[str, Any] = Field(default_factory=dict)   # source-specific (e.g. DB pull)
    status: str = "connected"                    # connected | paused | disconnected
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    seat_id: str | None = None                   # the owning seat; None = workspace
    ownership_type: str = WORKSPACE              # workspace | seat — always agrees with seat_id

    def model_post_init(self, _ctx: object) -> None:
        # The two fields say one thing; derive the second rather than trust callers to keep them
        # in step (the database constraint in 0138 would refuse a disagreement anyway).
        if self.seat_id:
            self.ownership_type = SEAT
        elif self.ownership_type != WORKSPACE:
            raise ValueError("a seat connection must name its seat_id")
