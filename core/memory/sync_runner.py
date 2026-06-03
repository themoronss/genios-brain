"""v2 sync runner — pulls records via a MemoryAdapter, normalizes, emits.

Replaces v1's per-source heavy ingestion (gmail_connector → email_parser →
classifier → entity_extractor → graph_builder + write to interactions/contacts/...).

Per g-i-1 contract:
- NO content storage on the v1 side
- Adapter pulls → normalize → MemoryItem (plaintext, in-flight)
- emit() publishes to multi-subscriber bus (g-i-3 builds facts, g-i-4 may trigger)
- Cursor updated; scope drops counted

Subscribers (registered once at app startup via emit.subscribe):
- "g-i-3 fact-extractor" — runs LLM extract → reconcile → graph persist
- (later) "g-i-4 proactive-trigger" — diff detect → maybe push

Usage from OAuth callback / scheduler:
    from core.memory.sync_runner import run_sync_for_connection
    run_sync_for_connection(session, connection_id="...", limit=50)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.memory.adapters import get_factory
from core.memory.emit import emit
from core.memory.interface import MemoryAdapter
from core.memory.normalize import normalize
from core.memory.scope import ScopeEnforcer
from core.memory.store import Connection, CursorRow, ScopeGrant
from core.memory.types import Cursor

log = get_logger(__name__)


@dataclass
class SyncResult:
    connection_id: str
    source_type: str
    items_emitted: int
    items_dropped_scope: int
    cursor_advanced: bool
    error: str | None = None


def run_sync_for_connection(
    session: Session,
    *,
    connection_id: str,
    limit: int = 100,
) -> SyncResult:
    """Pull one batch from the connection's source, emit each item.

    All work happens with the caller's session; we flush + commit between
    cursor updates so partial progress is preserved on crash.
    """
    conn = session.get(Connection, connection_id)
    if conn is None:
        return SyncResult(
            connection_id=connection_id,
            source_type="unknown",
            items_emitted=0,
            items_dropped_scope=0,
            cursor_advanced=False,
            error="connection not found",
        )

    adapter = _build_adapter(session, conn)
    if adapter is None:
        return SyncResult(
            connection_id=connection_id,
            source_type=conn.source_type,
            items_emitted=0,
            items_dropped_scope=0,
            cursor_advanced=False,
            error=f"no adapter factory registered for source_type={conn.source_type}",
        )

    # Cursor
    cursor_row = session.execute(
        select(CursorRow).where(CursorRow.connection_id == connection_id)
    ).scalar_one_or_none()
    cursor: Cursor | None = None
    if cursor_row and cursor_row.cursor_value:
        # CursorRow.strategy is a free-form str; Cursor.strategy is a Literal
        # subset. Trust the producer (only adapters write here).
        cursor = Cursor(
            strategy=cursor_row.strategy or "native",  # type: ignore[arg-type]
            value=cursor_row.cursor_value,
        )

    # Scope grants (post-fetch enforcement)
    grants = (
        session.execute(
            select(ScopeGrant).where(ScopeGrant.connection_id == connection_id)
        )
        .scalars()
        .all()
    )
    scopes = []
    for g in grants:
        try:
            scopes.append(g.to_read_scope())  # type: ignore[attr-defined]
        except Exception:  # noqa: S112 — scope_json may be raw; skip if shape unknown
            continue
    enforcer = ScopeEnforcer(scopes, connection_id=connection_id, org_id=conn.org_id)

    # Pull
    try:
        records, new_cursor, more = adapter.list_changed_since(cursor, limit)
    except Exception as e:
        log.exception("sync_pull_failed", connection_id=connection_id, error=str(e))
        return SyncResult(
            connection_id=connection_id,
            source_type=conn.source_type,
            items_emitted=0,
            items_dropped_scope=0,
            cursor_advanced=False,
            error=str(e),
        )

    mapping = adapter.get_mapping()
    emitted = 0
    dropped = 0
    for record in records:
        if not enforcer.is_allowed(record):
            dropped += 1
            continue
        try:
            item = normalize(record, mapping, source_id=conn.source_id)
            emit(item, org_id=conn.org_id)
            emitted += 1
        except Exception as e:
            log.warning(
                "normalize_or_emit_failed",
                connection_id=connection_id,
                native_id=record.native_id,
                error=str(e),
            )

    # Cursor advance
    cursor_advanced = False
    if new_cursor and new_cursor.value:
        if cursor_row is None:
            cursor_row = CursorRow(
                connection_id=connection_id,
                cursor_strategy=new_cursor.strategy,
                cursor_value=new_cursor.value,
                last_sync_at=datetime.now(UTC),
                items_pulled_count=emitted,
            )
            session.add(cursor_row)
        else:
            cursor_row.strategy = new_cursor.strategy
            cursor_row.cursor_value = new_cursor.value
            cursor_row.last_sync_at = datetime.now(UTC)
            cursor_row.items_pulled_count = (cursor_row.items_pulled_count or 0) + emitted
        cursor_advanced = True

    conn.last_health_check_at = datetime.now(UTC)
    conn.health_status = "green"
    session.flush()

    log.info(
        "sync_complete",
        connection_id=connection_id,
        source_type=conn.source_type,
        emitted=emitted,
        dropped_scope=dropped,
        cursor_advanced=cursor_advanced,
        more=more,
    )
    return SyncResult(
        connection_id=connection_id,
        source_type=conn.source_type,
        items_emitted=emitted,
        items_dropped_scope=dropped,
        cursor_advanced=cursor_advanced,
    )


def _build_adapter(session: Session, conn: Connection) -> MemoryAdapter | None:
    """Resolve the adapter factory for `source_type` and instantiate it."""
    try:
        factory = get_factory(conn.source_type)
    except KeyError:
        return None

    # Pull the access + refresh secret refs for this connection (typed `oauth_access`
    # and `oauth_refresh` per secrets.py convention). Adapter handles refresh.
    from core.memory.store import SecretRef

    access_ref = session.execute(
        select(SecretRef)
        .where(SecretRef.connection_id == conn.id)
        .where(SecretRef.secret_type == "oauth_access")  # noqa: S105 — enum label, not a credential
        .order_by(SecretRef.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    refresh_ref = session.execute(
        select(SecretRef)
        .where(SecretRef.connection_id == conn.id)
        .where(SecretRef.secret_type == "oauth_refresh")  # noqa: S105 — enum label, not a credential
        .order_by(SecretRef.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    kwargs: dict[str, Any] = {
        "session": session,
        "connection_id": conn.id,
        "org_id": conn.org_id,
        "access_secret_ref": access_ref.id if access_ref else None,
        "refresh_secret_ref": refresh_ref.id if refresh_ref else None,
        "account_email": conn.source_id,  # for Gmail, source_id IS the mailbox address
    }
    return factory(**kwargs)
