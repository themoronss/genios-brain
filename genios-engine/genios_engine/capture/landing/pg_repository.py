from __future__ import annotations

from sqlalchemy import text

from genios_engine.contracts.source_event import SourceEvent
from genios_engine.platform.db import get_engine

_INSERT = text(
    """
    insert into source_events
      (event_id, org_id, connection_id, source, object_type, source_object_id,
       parent_object_id, dedup_key, actor, occurred_at, captured_at, sync_mode,
       payload_ref, capture_confidence, schema_version, outcome)
    values
      (:event_id, :org_id, :connection_id, :source, :object_type, :source_object_id,
       :parent_object_id, :dedup_key, cast(:actor as jsonb), :occurred_at, :captured_at,
       :sync_mode, :payload_ref, :capture_confidence, :schema_version, :outcome)
    on conflict (org_id, dedup_key) do nothing
    """
)
_EXISTS = text("select 1 from source_events where org_id=:o and dedup_key=:d limit 1")


class PostgresSourceEventRepository:
    """Real Supabase/Postgres storage behind the SourceEventRepository interface.
    Dedup uniqueness is enforced by the DB index; insert is on-conflict-do-nothing."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def exists(self, org_id: str, dedup_key: str) -> bool:
        with self._engine.connect() as conn:
            return conn.execute(_EXISTS, {"o": org_id, "d": dedup_key}).first() is not None

    def add(self, event: SourceEvent, outcome: str | None = None) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT, {
                "event_id": event.event_id, "org_id": event.org_id,
                "connection_id": event.connection_id, "source": event.source,
                "object_type": event.object_type, "source_object_id": event.source_object_id,
                "parent_object_id": event.parent_object_id, "dedup_key": event.dedup_key,
                "actor": event.actor.model_dump_json(),
                "occurred_at": event.occurred_at, "captured_at": event.captured_at,
                "sync_mode": event.sync_mode.value, "payload_ref": event.payload_ref,
                "capture_confidence": event.capture_confidence,
                "schema_version": event.schema_version, "outcome": outcome,
            })
