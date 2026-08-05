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
       route, triage_lane, domain_hints, linkage_hints)
    values
      (:event_id, :org_id, :connection_id, :source, :source_family, :object_type,
       :source_object_id, :parent_object_id, :dedup_key, cast(:actor as jsonb),
       :occurred_at, :captured_at, :sync_mode, :payload_ref, :capture_confidence,
       :schema_version, :outcome,
       :route, :triage_lane, cast(:domain_hints as jsonb), cast(:linkage_hints as jsonb))
    on conflict (org_id, dedup_key) do nothing
    """
)
_EXISTS = text("select 1 from source_events where org_id=:o and dedup_key=:d limit 1")


class PostgresSourceEventRepository:
    """Real Supabase/Postgres storage behind the SourceEventRepository interface.
    Dedup uniqueness is enforced by the DB index; insert is on-conflict-do-nothing.
    Persists the full seam: envelope v2 (source_family) + the gate/triage decision
    (route, triage_lane, domain_hints, linkage_hints) that L2 reads instead of
    re-deriving."""

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
                "domain_hints": json.dumps(domain_hints, default=str) if domain_hints is not None else None,
                "linkage_hints": json.dumps(linkage_hints, default=str) if linkage_hints is not None else None,
            })
