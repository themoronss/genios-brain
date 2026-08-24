from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class RawObject:
    """A raw object returned by a source (via Composio or native), pre-normalization.
    Connectors differ only in how they produce this; downstream is source-agnostic."""

    source: str
    object_type: str
    source_object_id: str
    occurred_at: datetime
    actor_email: str | None = None
    actor_type: str = "external_contact"
    parent_object_id: str | None = None
    # For MUTABLE structured objects (CRM deal, calendar event, DB row) a connector sets a
    # content version (updatedAt / etag / watermark). It folds into dedup_key so a CHANGED
    # object re-lands and updates the graph. Email/message leave it None → stable dedup (an
    # email never edits). Without this, deal.stage froze at its first-seen value forever.
    content_version: str | None = None
    # Set ONLY when the company is deliberately asserting something about itself (a
    # written policy, an upload tagged `pricing`). One of internal_knowledge.INTERNAL_KINDS.
    # It promotes the event's family to `internal` and its facts to authority rank 4 —
    # so company canon outranks a third-party system of record. None for observed traffic.
    internal_kind: str | None = None
    # The clock the incremental cursor advances on. For a message `occurred_at` (when it was
    # sent) IS the right watermark. For a calendar event it is catastrophically wrong:
    # `occurred_at` is when the MEETING STARTS, so one event booked for next month pushes the
    # cursor into the future and every subsequent sync asks the provider for changes "since"
    # a date that has not happened — the connector goes permanently silent while still
    # reporting success. Mutable sources must set this to their own last-modified stamp.
    synced_at: datetime | None = None
    #: Everyone else the message was addressed to (To + Cc), lowercased. Connectors already parse
    #: these — the Gmail path extracts them and drops them into an untyped dict — so this is a
    #: contract, not new work: it makes the participant set survive past the payload TTL.
    recipients: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def watermark_at(self) -> datetime:
        """The timestamp the cursor may advance to for this object."""
        return self.synced_at or self.occurred_at


@dataclass
class SourceBatch:
    objects: list[RawObject]
    next_cursor: str | None = None


@runtime_checkable
class SourceConnector(Protocol):
    """One interface, every source implements. Composio sits BEHIND this (auth +
    data delivery only); a native adapter can replace any one connector without
    changing landing/gate/graph. Our contract stays ours."""

    source: str

    def validate_connection(self) -> bool: ...
    def initial_snapshot(self, cursor: str | None, limit: int) -> SourceBatch: ...
    def incremental_changes(self, cursor: str | None, limit: int,
                            since: Optional[datetime] = None) -> SourceBatch: ...
    def fetch_content(self, object_ref: str) -> dict[str, Any]: ...
