from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SyncMode(str, Enum):
    backfill = "backfill"
    incremental = "incremental"
    recovery = "recovery"


class Actor(BaseModel):
    type: str                       # internal_user | external_contact | agent | system | human
    email: str | None = None
    external_id: str | None = None


def compute_dedup_key(source: str, object_type: str, source_object_id: str,
                      content_version: str | None = None) -> str:
    """Stable per source object — same object+version yields the same key, so re-syncs and
    retries can't create duplicates. For a MUTABLE structured object the connector passes a
    content_version (updatedAt/etag/watermark); a genuine change then yields a NEW key so the
    edit lands and updates the graph, while an unchanged re-sync still dedups. Email/message
    pass no version → the immutable object never re-lands."""
    base = f"{source}:{object_type}:{source_object_id}"
    return f"{base}:{content_version}" if content_version else base


class SourceEvent(BaseModel):
    """The one immutable envelope every connector emits. Append-only; corrections
    are new events, never edits. occurred_at (world time) and captured_at (when we
    learned it) are never merged."""

    event_id: str
    org_id: str
    connection_id: str
    source: str
    object_type: str
    source_object_id: str
    parent_object_id: str | None = None
    dedup_key: str
    actor: Actor
    occurred_at: datetime
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sync_mode: SyncMode = SyncMode.incremental
    payload_ref: str | None = None          # -> raw_payloads (encrypted + TTL)
    capture_confidence: float = 1.0
    schema_version: int = 1
