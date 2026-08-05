from __future__ import annotations

from genios_engine.capture.connectors.base import SourceConnector
from genios_engine.capture.landing.repository import (InMemorySourceEventRepository,
                                                      SourceEventRepository)
from genios_engine.platform.config import get_settings

# The switch between REAL and dev is here, driven entirely by .env — no code change.
#   DATABASE_URL set   → Postgres/Supabase repo   (else in-memory)
#   COMPOSIO keys set  → real Composio Gmail       (else fake connector)


def make_repo() -> SourceEventRepository:
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
        return PostgresSourceEventRepository(s.database_url)
    return InMemorySourceEventRepository()


def make_connector_for(connection) -> SourceConnector:
    """Build the right connector for ONE org's connection, dispatched by source_type.
    Composio API key is global (GeniOS's); per-org identity is composio_user_id. Every
    source sits behind the same SourceConnector interface — the pipeline is agnostic."""
    s = get_settings()
    st = connection.source_type
    # Client's own database — no Composio; read-only pull → structured route.
    if st in ("postgres", "database", "mysql"):
        from genios_engine.capture.connectors.database import ClientDatabaseConnector
        cfg = connection.config or {}
        return ClientDatabaseConnector(
            database_url=cfg["db_url"], table=cfg["table"],
            identity_field=cfg["identity_field"],
            watermark_col=cfg.get("watermark_col", "updated_at"), source=st)
    if not s.use_real_composio:
        from genios_engine.capture.connectors.fake import FakeGmailConnector
        return FakeGmailConnector(org_id=connection.org_id,
                                  connection_id=connection.connection_id)
    key, uid = s.composio_api_key, connection.composio_user_id
    if st == "gmail":
        from genios_engine.capture.connectors.composio import ComposioGmailConnector
        ocr = None                              # scanned-PDF attachments need OCR (native-only if off)
        if s.enable_ocr:
            from genios_engine.capture.documents.tesseract import TesseractOcr
            ocr = TesseractOcr()
        return ComposioGmailConnector(api_key=key, user_id=uid,
                                      connected_account_id=s.composio_gmail_account or None, ocr=ocr)
    if st in ("gcal", "calendar", "google_calendar"):
        from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
        return ComposioCalendarConnector(api_key=key, user_id=uid)
    if st == "notion":
        from genios_engine.capture.connectors.notion import ComposioNotionConnector
        return ComposioNotionConnector(api_key=key, user_id=uid)
    if st in ("gdrive", "drive", "google_drive"):
        from genios_engine.capture.connectors.drive import ComposioDriveConnector
        ocr = None
        if s.enable_ocr:
            from genios_engine.capture.documents.tesseract import TesseractOcr
            ocr = TesseractOcr()
        return ComposioDriveConnector(api_key=key, user_id=uid, ocr=ocr)
    raise ValueError(f"no connector wired for source_type={st!r}")


# backward-compatible alias
make_gmail_connector_for = make_connector_for


def make_agent_registry_store():
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.events_store import PostgresAgentRegistryStore
        return PostgresAgentRegistryStore(s.database_url)
    from genios_engine.capture.events_store import InMemoryAgentRegistryStore
    return InMemoryAgentRegistryStore()


def make_human_event_store():
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.events_store import PostgresHumanEventStore
        return PostgresHumanEventStore(s.database_url)
    from genios_engine.capture.events_store import InMemoryHumanEventStore
    return InMemoryHumanEventStore()


def make_agent_event_store():
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.events_store import PostgresAgentEventStore
        return PostgresAgentEventStore(s.database_url)
    from genios_engine.capture.events_store import InMemoryAgentEventStore
    return InMemoryAgentEventStore()


def make_cursor_store():
    """Sync watermark/cursor per connection (no-miss). Postgres if DATABASE_URL set."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.acquire.cursor_store import PostgresCursorStore
        return PostgresCursorStore(s.database_url)
    from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
    return InMemoryCursorStore()


def make_connection_store():
    """Per-org connections. Postgres if DATABASE_URL set (multi-tenant, survives
    restarts), else in-memory."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.connections.store import PostgresConnectionStore
        return PostgresConnectionStore(s.database_url)
    from genios_engine.capture.connections.store import InMemoryConnectionStore
    return InMemoryConnectionStore()


def make_parked_store():
    """Parked ('maybe') queue. Postgres if DATABASE_URL set, else in-memory."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.parked.store import PostgresParkedStore
        return PostgresParkedStore(s.database_url)
    from genios_engine.capture.parked.store import InMemoryParkedStore
    return InMemoryParkedStore()


def make_document_job_store():
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.documents.store import PostgresDocumentJobStore
        return PostgresDocumentJobStore(s.database_url)
    from genios_engine.capture.documents.store import InMemoryDocumentJobStore
    return InMemoryDocumentJobStore()


def make_payload_store():
    """Raw content store — encrypted + short TTL, KEPT-only. Postgres if DATABASE_URL
    set, else in-memory. This is where L2 reads the body of emitted events."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.payload_store import PostgresRawPayloadStore
        return PostgresRawPayloadStore(s.database_url, s.crypto_key)
    from genios_engine.capture.payload_store import InMemoryRawPayloadStore
    return InMemoryRawPayloadStore()


def make_prepared_store():
    """PreparedContent store — the persisted L1→L2 seam (PII-masked text + offset map).
    Retained longer than the raw payload: it is the replayable form."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.prepared_store import PostgresPreparedContentStore
        return PostgresPreparedContentStore(s.database_url)
    from genios_engine.capture.prepared_store import InMemoryPreparedContentStore
    return InMemoryPreparedContentStore()


def make_trace_repo():
    """Decision-trace persistence. Postgres/Supabase if DATABASE_URL is set, else
    in-memory. Every event's per-stage path lands in event_trace for debugging."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.trace_store import PostgresTraceRepository
        return PostgresTraceRepository(s.database_url)
    from genios_engine.capture.trace_store import InMemoryTraceRepository
    return InMemoryTraceRepository()


def make_llm_client():
    """L2's Anthropic client (the single combined call). None if no key configured."""
    s = get_settings()
    if not s.use_real_llm:
        return None
    from genios_engine.context.llm.client import LLMClient
    return LLMClient(api_key=s.anthropic_api_key, model=s.anthropic_model)


def make_graph_store():
    """L2 context-graph store (Postgres). None in pure in-memory dev (needs the DB)."""
    s = get_settings()
    if not s.use_real_db:
        return None
    from genios_engine.context.graph_store import GraphStore
    return GraphStore(s.database_url)


def make_card_store():
    """L5 delivery card store (Postgres). None in pure in-memory dev (needs the DB)."""
    s = get_settings()
    if not s.use_real_db:
        return None
    from genios_engine.deliver.store import CardStore
    return CardStore(s.database_url)


def make_pack_registry():
    """L4 pack registry (Postgres) with every built-in pack registered. None without DB."""
    s = get_settings()
    if not s.use_real_db:
        return None
    from genios_engine.packs.wiring import make_registry
    return make_registry(s.database_url)


def make_relevance_classifier():
    """Optional L1 S2 relevance gate. None (off) unless enabled. Deterministic today;
    swap for the LLM classifier at LLM-integration time (same interface)."""
    if not get_settings().enable_l1_relevance:
        return None
    from genios_engine.capture.gate.relevance import DeterministicRelevanceClassifier
    return DeterministicRelevanceClassifier()
