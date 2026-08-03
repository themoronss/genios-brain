from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from genios_engine.platform.ids import new_id


class Connection(BaseModel):
    """One connected source for ONE org (tenant). This is the per-startup identity —
    it lives in the DB, not in .env. 30 startups = 30 rows. The Composio API key is
    global (GeniOS's); composio_user_id is this org's label inside Composio (blank for
    non-Composio sources like a client DB). `config` holds source-specific settings
    (e.g. a client DB's db_url / table / watermark) — stored in the capture_scope jsonb."""

    connection_id: str = Field(default_factory=lambda: new_id("con"))
    org_id: str                                  # the startup / tenant (ours)
    provider: str = "google"
    source_type: str = "gmail"
    composio_user_id: str = ""                   # Composio label; blank for DB/other sources
    config: dict[str, Any] = Field(default_factory=dict)   # source-specific (e.g. DB pull)
    status: str = "connected"                    # connected | paused | disconnected
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
