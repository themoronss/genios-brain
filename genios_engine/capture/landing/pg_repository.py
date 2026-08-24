from __future__ import annotations

import json

from sqlalchemy import text

from genios_engine.contracts.source_event import SourceEvent
from genios_engine.platform.db import get_engine

_INSERT = text(
    """
    insert into source_events
      (event_id, org_id, connection_id, source, source_family, object_type,
       source_object_id, parent_object_id, dedup_key, actor, occurred_at, captured_at,
       sync_mode, payload_ref, capture_confidence, schema_version, outcome,
       route, triage_lane, domain_hints, linkage_hints, internal_kind, recipients,
       visibility_scope, visibility_principals, visibility_derived_from)
    values
      (:event_id, :org_id, :connection_id, :source, :source_family, :object_type,
       :source_object_id, :parent_object_id, :dedup_key, cast(:actor as jsonb),
       :occurred_at, :captured_at, :sync_mode, :payload_ref, :capture_confidence,
       :schema_version, :outcome,
       :route, :triage_lane, cast(:domain_hints as jsonb), cast(:linkage_hints as jsonb),
       :internal_kind, :recipients,
       :visibility_scope, :visibility_principals, :visibility_derived_from)
    on conflict (org_id, dedup_key) do nothing
    """
)
def _dump_list(items: list | None) -> str | None:
    """Serialize a hint list to JSON text for a jsonb column. Items may be pydantic
    models (DomainHint) or plain dicts — model_dump() first so the stored shape is a
    real object ({"domain": "sales", ...}), NOT its str() repr. Storing the repr was a
    silent correctness bug: L2's resolve_domain reads .domain off each item and a string
    has none, so every event fell back to the `general` domain and domain-scoped
    correlation never happened on Postgres (the in-memory path kept the objects, so no
    test caught it)."""
    if items is None:
        return None
    return json.dumps(
        [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]
    )


_EXISTS = text("select 1 from source_events where org_id=:o and dedup_key=:d limit 1")


class PostgresSourceEventRepository:
    """Real Supabase/Postgres storage behind the SourceEventRepository interface.
    Dedup uniqueness is enforced by the DB index; insert is on-conflict-do-nothing.
    Persists the full seam: envelope v3 (source_family, internal_kind) + the gate/triage
    decision (route, triage_lane, domain_hints, linkage_hints) that L2 reads instead of
    re-deriving. internal_kind carries AUTHORITY across the seam — without it persisted,
    company canon would arrive at L2 indistinguishable from a stranger's email."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def exists(self, org_id: str, dedup_key: str) -> bool:
        with self._engine.connect() as conn:
            return conn.execute(_EXISTS, {"o": org_id, "d": dedup_key}).first() is not None

    def add(self, event: SourceEvent, outcome: str | None = None, *,
            route: str | None = None, triage_lane: str | None = None,
            domain_hints: list | None = None, linkage_hints: list | None = None) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT, {
                "event_id": event.event_id, "org_id": event.org_id,
                "connection_id": event.connection_id, "source": event.source,
                "source_family": event.source_family,
                "object_type": event.object_type, "source_object_id": event.source_object_id,
                "parent_object_id": event.parent_object_id, "dedup_key": event.dedup_key,
                "actor": event.actor.model_dump_json(),
                "occurred_at": event.occurred_at, "captured_at": event.captured_at,
                "sync_mode": event.sync_mode.value, "payload_ref": event.payload_ref,
                "capture_confidence": event.capture_confidence,
                "schema_version": event.schema_version, "outcome": outcome,
                "route": route, "triage_lane": triage_lane,
                "domain_hints": _dump_list(domain_hints),
                "linkage_hints": _dump_list(linkage_hints),
                "internal_kind": event.internal_kind,
                # list, not tuple: psycopg maps a Python list onto text[]. Empty stays empty —
                # distinct from NULL, which means "captured before the column existed".
                "recipients": list(getattr(event, "recipients", ()) or ()),
                # The source's own ACL. NULL scope = no rule named the audience, and the gate
                # already parked such an event — a published row always carries a real scope.
                "visibility_scope": (event.visibility.scope if event.visibility else None),
                "visibility_principals": (list(event.visibility.principals)
                                          if event.visibility else None),
                "visibility_derived_from": (event.visibility.derived_from
                                            if event.visibility else None),
            })
