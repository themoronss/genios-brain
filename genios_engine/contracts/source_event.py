from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from genios_engine.contracts.visibility import Visibility


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
    source_family: str = "unclassified"     # one of capture.source_families.FAMILIES
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
    # Company canon: the org deliberately asserting something about itself. One of
    # capture.internal_knowledge.INTERNAL_KINDS, else None. Carries the event's AUTHORITY
    # to L2 — provenance is L1's to know, so L2 honours this instead of guessing from the
    # source name. See capture.internal_knowledge for why canon sits above rank 3.
    internal_kind: str | None = None
    # WHO ELSE was on this message. First-class because the alternative is a deadline: To/Cc
    # survived only inside the encrypted `raw_payloads` blob, which carries a 30-day TTL, so the
    # design partner's backfilled correspondence loses its recipient data on 2026-09-16 and even
    # best-effort reconstruction stops being possible. It is also the only way to tell a message
    # sent TO one person from one that copied nine — which is the difference between a
    # conversation and a broadcast, and neither L2 nor any rule could previously see it.
    recipients: tuple[str, ...] = ()
    # WHO could see the original — the source's own ACL, derived per source family at the
    # normalize seam (capture/visibility_rules.py). None means "no derivation rule covered this
    # source", and the gate PARKS such an event as `visibility_unknown` rather than publishing:
    # an audience we cannot name is not an audience we may assume. The contract existed, fully
    # tested, and nothing on the capture path called it — every event landed org-scoped, so a
    # two-person private thread and a company-wide page were indistinguishable to every layer
    # above.
    visibility: Visibility | None = None
    schema_version: int = 5                 # v5: + visibility · v4: + recipients (additive)
