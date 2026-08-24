from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.internal_knowledge import normalize_kind
from genios_engine.capture.source_families import family_of
from genios_engine.capture.visibility_rules import derive_visibility
from genios_engine.contracts.source_event import (Actor, SourceEvent, SyncMode,
                                                  compute_dedup_key)
from genios_engine.platform.ids import new_id


def to_source_event(
    raw: RawObject,
    *,
    org_id: str,
    connection_id: str,
    sync_mode: SyncMode = SyncMode.incremental,
    payload_ref: str | None = None,
    mailbox_owner: str | None = None,
) -> SourceEvent:
    """Deterministic raw → immutable SourceEvent. dedup_key is stable per source
    object; only event_id/captured_at are non-deterministic (assigned at ingest)."""
    # A declared internal_kind PROMOTES the family to `internal`. Family answers "what
    # kind of reality is this", and a policy the company wrote is its own record no
    # matter which door it came through — classifying an uploaded pricing sheet as
    # `knowledge` would file it beside a customer's shared doc, which is the exact
    # conflation this step exists to end. The descriptor's family stays the DEFAULT.
    # An unrecognised tag normalises to None and changes nothing.
    kind = normalize_kind(raw.internal_kind)
    return SourceEvent(
        event_id=new_id("evt"),
        org_id=org_id,
        connection_id=connection_id,
        source=raw.source,
        source_family="internal" if kind else family_of(raw.source),
        internal_kind=kind,
        object_type=raw.object_type,
        source_object_id=raw.source_object_id,
        parent_object_id=raw.parent_object_id,
        dedup_key=compute_dedup_key(raw.source, raw.object_type, raw.source_object_id,
                                    raw.content_version),
        actor=Actor(type=raw.actor_type, email=raw.actor_email),
        # Carried through the seam instead of dying in the payload blob. One sender per event was
        # never enough to say who a conversation is WITH — it is the root of targeting an
        # introducer as though they were the counterparty.
        recipients=tuple(raw.recipients or ()),
        occurred_at=raw.occurred_at,
        captured_at=datetime.now(timezone.utc),
        sync_mode=sync_mode,
        payload_ref=payload_ref,
        # The source's own ACL, stamped once at the only seam that still knows it. By Layer 2
        # the email is a fact and the recipient list is gone.
        visibility=derive_visibility(
            source=raw.source, actor_email=raw.actor_email,
            recipients=raw.recipients, internal_kind=kind,
            mailbox_owner=mailbox_owner),
    )
