from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ParkedEvent(BaseModel):
    """Parked ≠ deleted. An uncertain/unsupported event, reviewable with its reason,
    stage, and trace. Recover re-injects it; retention is L7 policy, not hidden delete."""

    event_id: str
    org_id: str
    source: str
    reason_code: str
    stage: str
    trace: list[dict] = Field(default_factory=list)
    status: str = "pending"                    # pending | recovered | relabeled | dropped
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
