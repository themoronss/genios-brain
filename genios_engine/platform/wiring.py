from __future__ import annotations

import math
import os
from datetime import datetime, timezone

from genios_engine.capture.connectors.backfill import backfill_window_for
from genios_engine.capture.connectors.base import SourceConnector
from genios_engine.capture.source_registry import BUILDABLE_SOURCES
from genios_engine.capture.landing.repository import (InMemorySourceEventRepository,
                                                      SourceEventRepository)
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.platform.wiring")

# The switch between REAL and dev is here, driven entirely by .env — no code change.
#   DATABASE_URL set   → Postgres/Supabase repo   (else in-memory)
#   COMPOSIO keys set  → real Composio Gmail       (else fake connector)


def make_repo() -> SourceEventRepository:
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
        return PostgresSourceEventRepository(s.database_url)
    return InMemorySourceEventRepository()


# Source types make_connector_for can actually build. The integrations UI reads this
# so a "Connect" button never starts an OAuth flow that ends in a 502 — advertising a
# connector that raises ValueError was a customer-visible lie.
#
# Derived from the source registry (`buildable=True`) rather than hand-listed here: a
# second hand-maintained list of sources is exactly how this drifted out of step with
# the family taxonomy and the coverage capabilities. Adding a connector means flipping
# `buildable` on its descriptor AND wiring the branch in make_connector_for below —
# tests/test_source_registry.py asserts those two agree.
IMPLEMENTED_SOURCE_TYPES: frozenset[str] = BUILDABLE_SOURCES

# The dispatch table make_connector_for branches on, as DATA so it can be compared with
# the registry. In dev (no Composio key) the function falls back to a fake connector for
# every source_type, so a test cannot discover the real dispatch by calling it — these
# two names make the agreement checkable instead of hopeful.
DIRECT_SOURCE_TYPES: frozenset[str] = frozenset({"postgres", "database", "mysql"})
COMPOSIO_SOURCE_TYPES: frozenset[str] = frozenset({
    "gmail", "gcal", "calendar", "google_calendar", "notion",
    "gdrive", "drive", "google_drive", "hubspot",
})


def make_connector_for(connection, relevance=None) -> SourceConnector:
    """Build the right connector for ONE org's connection, dispatched by source_type.
    Composio API key is global (GeniOS's); per-org identity is composio_user_id. Every
    source sits behind the same SourceConnector interface — the pipeline is agnostic.

    `relevance` (optional): the SAME S2 classifier the pipeline uses. Passed to Gmail so it can
    gate on the list snippet and skip full-body fetches for confident drops (huge speedup)."""
    s = get_settings()
    st = connection.source_type
    # Client's own database — no Composio; read-only pull → structured route.
    if st in DIRECT_SOURCE_TYPES:
        from genios_engine.capture.connectors.database import ClientDatabaseConnector
        cfg = connection.config or {}
        return ClientDatabaseConnector(
            database_url=cfg["db_url"], table=cfg["table"],
            identity_field=cfg["identity_field"],
            watermark_col=cfg.get("watermark_col", "updated_at"), source=st)
    if not s.use_real_composio:
        # The fake is a GMAIL fixture. Returning it for every source_type meant a local run or
        # demo could "prove" Notion, Drive, HubSpot or Calendar coverage using Gmail data —
        # unfalsifiable in exactly the setting where it gets shown to someone. Refuse instead:
        # a missing fixture is a fact worth surfacing, not one worth papering over.
        if st not in ("gmail", "google_mail"):
            raise ValueError(
                f"no offline fixture for source_type={st!r}; set GENIOS_USE_REAL_COMPOSIO to "
                "exercise it, or add a fixture connector. The Gmail fake must not stand in for "
                "another source.")
        from genios_engine.capture.connectors.fake import FakeGmailConnector
        return FakeGmailConnector(org_id=connection.org_id,
                                  connection_id=connection.connection_id)
    key, uid = s.composio_api_key, connection.composio_user_id
    # L1.2.4-U1 — how far back a FIRST sync reaches is this connection's setting, not a constant
    # inside the connector. Resolved once, here, so both time-windowed sources (mail and calendar)
    # cover the same period for the same tenant.
    window = backfill_window_for(connection)
    if st == "gmail":
        from genios_engine.capture.connectors.composio import ComposioGmailConnector
        ocr = make_ocr(connection.org_id)       # per-tenant; None → native-text only
        return ComposioGmailConnector(api_key=key, user_id=uid,
                                      connected_account_id=s.composio_gmail_account or None, ocr=ocr,
                                      relevance=relevance, backfill_days=window.days)
    if st in ("gcal", "calendar", "google_calendar"):
        from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
        return ComposioCalendarConnector(api_key=key, user_id=uid, backfill_days=window.days)
    if st == "notion":
        from genios_engine.capture.connectors.notion import ComposioNotionConnector
        return ComposioNotionConnector(api_key=key, user_id=uid)
    if st in ("gdrive", "drive", "google_drive"):
        from genios_engine.capture.connectors.drive import ComposioDriveConnector
        ocr = make_ocr(connection.org_id)
        return ComposioDriveConnector(api_key=key, user_id=uid, ocr=ocr)
    if st == "hubspot":
        from genios_engine.capture.connectors.hubspot import ComposioHubspotConnector
        return ComposioHubspotConnector(api_key=key, user_id=uid)
    raise ValueError(f"no connector wired for source_type={st!r}")


# backward-compatible alias
make_gmail_connector_for = make_connector_for


def make_ocr(org_id: str | None = None):
    """The OCR engine for one org, or None with a logged reason. Shared by the Gmail/Drive
    attachment path AND dashboard uploads, so a scanned file reads the same way no matter which
    door it arrives through.

    Three inputs decide, not one (`capture/documents/enablement.py` holds the rule): the fleet
    default, this org's place on the allow/deny lists, and whether the Tesseract binary actually
    exists on this host. That last one is why `enable_ocr=true` is no longer enough — doc-03
    states the binary is absent from the deploy image, and wiring an engine that raises on its
    first call converts empty documents into failed syncs. Deliberately-off is a legitimate
    state; a silent None was not, so the reason is logged in the words that fix it.
    """
    s = get_settings()
    from genios_engine.capture.documents.enablement import (parse_org_allowlist,
                                                            resolve_ocr_availability)
    from genios_engine.capture.documents.tesseract import TesseractOcr, tesseract_available
    decision = resolve_ocr_availability(
        org_id=org_id,
        global_enabled=bool(getattr(s, "enable_ocr", False)),
        allowlist=parse_org_allowlist(getattr(s, "ocr_enabled_orgs", "")),
        denylist=parse_org_allowlist(getattr(s, "ocr_disabled_orgs", "")),
        engine_present=tesseract_available())
    if decision.enabled:
        return TesseractOcr()
    _log.info("OCR not wired (org=%s, %s): %s", org_id or "-", decision.availability,
              decision.detail)
    return None


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


def make_source_waitlist_store():
    """L1.1-U2's waitlist — the sources a tenant asked for and cannot connect yet.
    Postgres if DATABASE_URL is set, else in-memory. Nothing in the capture pipeline reads it:
    it is demand, recorded at the point of refusal, for the product to answer."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.source_waitlist import PostgresSourceWaitlist
        return PostgresSourceWaitlist(s.database_url)
    from genios_engine.capture.source_waitlist import InMemorySourceWaitlist
    return InMemorySourceWaitlist()


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


def make_relevance_classifier(org_id: str | None = None):
    """The L1 S2 relevance gate. Prefers the LLM junk-gate whenever an Anthropic key is present
    (production) — it is the one reliable filter that keeps noise OUT of the graph, replacing the
    over-aggressive regex drops. Falls back to the deterministic classifier only when explicitly
    opted in (dev), and to None (off) otherwise — so the hermetic test suite is unchanged.

    Pass `org_id` wherever the caller knows the tenant: the gate then writes its token usage to
    llm_costs like every other LLM call. Without it the gate still works, it just spends money
    invisibly — which is how reported spend drifted below the real Anthropic bill."""
    s = get_settings()
    if s.l1_llm_gate and s.use_real_llm:
        from genios_engine.capture.gate.relevance import LLMRelevanceClassifier
        from genios_engine.context.llm.client import LLMClient
        gate = LLMRelevanceClassifier(
            LLMClient(api_key=s.anthropic_api_key, model=s.anthropic_model))
        if org_id:
            store = make_graph_store()
            if store is not None:
                gate.bind_costs(store.record_cost, org_id)
        return gate
    if s.enable_l1_relevance:
        from genios_engine.capture.gate.relevance import DeterministicRelevanceClassifier
        return DeterministicRelevanceClassifier()
    return None


# ── coverage (L1.1-U1 / L1.7.5) ──────────────────────────────────────────────────
def make_conflict_store():
    """`signal_conflicts` (migration 0087) — L1.5.5's conflict record.

    Built on the same terms as `make_coverage_store` below: a real store when there is a real
    database, an in-memory one otherwise. A dev run keeps its conflicts for the life of the
    process, which is strictly more than the zero rows they had before the table existed.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.validate.conflict_store import PostgresConflictStore
        return PostgresConflictStore(s.database_url)
    from genios_engine.capture.validate.conflict_store import InMemoryConflictStore
    return InMemoryConflictStore()


def make_floor_store():
    """`org_qualification_floors` (migration 0088) — L1.6.8's per-tenant qualification floor.

    Built on `make_conflict_store`'s terms. The in-memory fallback is deliberately EMPTY rather
    than pre-seeded: a dev run with no configured floor gets `DEFAULT_FLOOR_BP`, which is the
    same answer production gives an untuned tenant, so the two do not disagree about a number
    that decides what a founder sees.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.esqe.qualification import PostgresFloorStore
        return PostgresFloorStore(s.database_url)
    from genios_engine.capture.esqe.qualification import InMemoryFloorStore
    return InMemoryFloorStore()


def make_drop_ledger():
    """`qualification_drops` (migration 0088) — the row a refused signal leaves behind.

    Without a real database this is a dict that lives for the process, which is strictly more
    than the zero rows a drop left before the table existed — and it keeps the seam exercised on
    every dev sweep instead of only under Postgres.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.esqe.qualification import PostgresDropLedger
        return PostgresDropLedger(s.database_url)
    from genios_engine.capture.esqe.qualification import InMemoryDropLedger
    return InMemoryDropLedger()


def make_rejection_ledger():
    """`publication_rejections` (migration 0092) — the row a signal the GATE refused leaves.

    Built on `make_drop_ledger`'s terms, and the pair matters: the floor's refusals and the
    publication gate's refusals answer one tenant question between them ("this email produced
    nothing; why?"), so a build where one of them falls back to a dict and the other does not
    would answer half of it on a dev run.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.esqe.publisher import PostgresRejectionLedger
        return PostgresRejectionLedger(s.database_url)
    from genios_engine.capture.esqe.publisher import InMemoryRejectionLedger
    return InMemoryRejectionLedger()


def make_lifecycle_store():
    """`signal_lifecycle` (migration 0093) — L1.6.9's ALG-19 state machine's rows.

    Built on `make_drop_ledger`'s terms. Without a real database this is a dict that lives for
    the process, which keeps the seam exercised on every dev sweep: a lifecycle that only runs
    under Postgres is a lifecycle nobody sees fail until production.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.esqe.lifecycle import PostgresLifecycleStore
        return PostgresLifecycleStore(s.database_url)
    from genios_engine.capture.esqe.lifecycle import InMemoryLifecycleStore
    return InMemoryLifecycleStore()


def make_signal_store():
    """`qualified_signals` (migration 0089) — L1.7.4's store, the L1 -> L2 boundary made durable.

    Built on `make_drop_ledger`'s terms. The in-memory fallback matters more here than anywhere
    else in this family: without it a dev run with no database would exercise the publication
    gate and then throw its conclusion away, so the one seam that decides what Layer 2 ever sees
    would be the seam nobody ran outside Postgres.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.esqe.signal_store import PostgresSignalStore
        return PostgresSignalStore(s.database_url)
    from genios_engine.capture.esqe.signal_store import InMemorySignalStore
    return InMemorySignalStore()


def make_coverage_store():
    """`source_coverage` — the table migration 0002 created and nothing ever wrote."""
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.coverage.store import PostgresCoverageStore
        return PostgresCoverageStore(s.database_url)
    from genios_engine.capture.coverage.store import InMemoryCoverageStore
    return InMemoryCoverageStore()


#: "the caller did not say", which is NOT the same as "the caller said none". `engine=None` had
#: to mean the latter: a test that passes it is stating there is no database, and resolving that
#: to `make_graph_store()` would open a real connection from a hermetic test — the exact accident
#: `tests/conftest.py` exists to prevent.
_UNSET = object()


def make_coverage_fn(org_id: str, *, connections=None, store=_UNSET, engine=_UNSET,
                     now: datetime | None = None):
    """ONE coverage declaration for this org, as the `domain -> verdict` callable capture takes.

    This is the factory the four capture entries share, and sharing it is the point. `coverage_fn`
    used to be a parameter that only `capture/pipeline.py` mentioned: the sweep, the Composio
    webhook, the manual-intake door and `/dev/ingest-sample` all called `capture_event` without
    it, so every event any of them produced carried `coverage_ready=None` — and each of the four
    was a separate, silent omission. One factory means a fifth entry has one obvious thing to
    pass, and `tests/capture/coverage/test_coverage_wiring.py` fails by file and line if it
    forgets.

    Computed EAGERLY, once, here — not lazily per event. The inputs are one `connections` read
    and one `count(distinct source_object_id)`; paying them per message would put two queries on
    the ingestion path of every email, and paying them per sweep puts them where a fact about the
    tenant's SOURCES belongs. The returned callable is a dict lookup.

    Persisting is best-effort by construction (`PostgresCoverageStore.save` logs and returns 0 on
    a database error): a sweep must not die because a dashboard row could not be filed.
    """
    from genios_engine.capture.coverage.declaration import (company_knowledge_count,
                                                            declare_coverage)
    if connections is None:
        connections = make_connection_store().list_active()
    if engine is _UNSET:
        graph = make_graph_store()
        engine = getattr(graph, "engine", None)
    declaration = declare_coverage(
        org_id=org_id, connections=connections,
        company_knowledge_count=company_knowledge_count(engine, org_id),
        computed_at=now or datetime.now(timezone.utc))
    if store is _UNSET:
        store = make_coverage_store()
    if store is not None:
        try:
            store.save(declaration)
        except Exception:      # noqa: BLE001 — a coverage row is a hint; a sweep is the product
            _log.exception("could not persist coverage declaration for org=%s", org_id)
        _advance_coverage_epochs(declaration, engine=engine)
    return declaration.for_domain


def _advance_coverage_epochs(declaration, *, engine) -> None:
    """L-5 · open a new coverage EPOCH for any domain whose source set just changed.

    Here, and not inside `CoverageStore.save`, for two reasons. The store is a Protocol with an
    in-memory implementation whose whole purpose is to need no database, and an epoch is a
    windowed history that only Postgres can hold; and this factory is the ONE place all four
    capture doors share, so an epoch that advances here advances on the sweep, the Composio
    webhook, the manual door and the dev sample alike — which is precisely the four-way omission
    `coverage_ready=None on 100% of events` was, one field along.

    Best-effort by the same argument `save` makes: a sweep must not die because a history row
    could not be opened. It is idempotent on the fingerprint, so a sweep every ten minutes over an
    unchanged source set writes nothing at all.
    """
    if engine is None:
        return
    try:
        from genios_engine.capture.coverage.store import rows_for
        from genios_engine.context.quality.epoch import advance_epochs
        with engine.begin() as conn:
            advance_epochs(conn, declaration.org_id, rows_for(declaration),
                           at=declaration.computed_at)
    except Exception:      # noqa: BLE001 — coverage history is a hint; a sweep is the product
        _log.exception("could not advance coverage epochs for org=%s", declaration.org_id)


def make_esqe_stage(org_id: str, *, engine=_UNSET, now: datetime | None = None):
    """ONE ESQE bundle for this org's whole sweep — today, the org's L1.6.7 baseline.

    The sibling of `make_coverage_fn` above, and it exists for the same reason that one does.
    `EsqeStage.org_baseline` was a parameter only `capture/pipeline.py` mentioned: no capture
    entry ever supplied it, so `run_esqe_stage` fell through to `OrgBaseline.cold_start(...)` on
    every event of every sweep, `compute_org_baseline` had no production caller at all, and 50%
    of ALG-17's formula (the money term and the entity term) was pinned to two constants for
    every tenant. A factory rather than a keyword at seven call sites, because seven call sites
    is seven places to forget — which is the history `make_coverage_fn` already records.

    Computed EAGERLY, once, here. The read is one windowed scan of `l1_extraction_results`; a
    p50 over a year does not move inside one sweep, and paying for it per message would put a
    table scan on the ingestion path of every email.

    Never raises: `load_org_baseline` answers a broken or absent database with a cold start,
    which is exactly the state every tenant is in today, so wiring this in cannot make a sweep
    worse than not wiring it in.
    """
    from genios_engine.capture.esqe.baseline_reader import load_org_baseline
    from genios_engine.capture.pipeline import EsqeStage
    if engine is _UNSET:
        graph = make_graph_store()
        engine = getattr(graph, "engine", None)
    return EsqeStage(org_baseline=load_org_baseline(
        engine, org_id, eval_time=now or datetime.now(timezone.utc)))


# ── S2 semantic lane (L1.4), per-tenant ──────────────────────────────────────────
def make_extraction_cache():
    """L1.4.9's permanent, content-addressed extraction cache — `l1_extraction_results`.

    Permanent and hash-keyed is what makes heavy L1 extraction affordable: the model runs once per
    content version, ever, and a replay of a March decision reads the March row instead of asking
    a model that has since changed. In-memory without a database, which pays for every call and is
    slow rather than wrong.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.semantic.cache import PostgresExtractionCache
        return PostgresExtractionCache(s.database_url)
    from genios_engine.capture.semantic.cache import InMemoryExtractionCache
    return InMemoryExtractionCache()


def make_open_lane_store():
    """L1.4.5's discovery lane — `unclassified_observations`.

    Every name the model used that the closed key vocabulary has no field for lands here, span-
    graded like any other claim, so the vocabulary grows from evidence ("this has been noticed 40
    times across 6 orgs, here are the sentences") instead of from a guess. No rule may read it:
    the rows are unreviewed labels the model chose its own words for, and the fence is asserted
    in `tests/capture/semantic/test_import_graph.py`.

    In-memory without a database, which loses the rows at process exit — that is a lost REPORT,
    never a lost extraction, because the sift that closes the lanes runs either way.
    """
    s = get_settings()
    if s.use_real_db:
        from genios_engine.capture.semantic.open_lane import PostgresOpenLaneStore
        return PostgresOpenLaneStore(s.database_url)
    from genios_engine.capture.semantic.open_lane import InMemoryOpenLaneStore
    return InMemoryOpenLaneStore()


#: A whole US dollar in minor units. The governor is integer cents end to end — a float budget
#: re-rounds differently on every worker, and `Budget` refuses one at construction.
_MINOR_PER_USD = 100

#: Basis-point ceiling above the daily budget at which the RUNAWAY breaker trips, distinct from
#: "today is spent". `batch.Budget` defaults to the same 1.5x the original `CostGuard` used; it
#: is named here because the wiring is where an operator would change it.
_BREAKER_BP = 15000


def _spent_today_minor(engine, org_id: str) -> int:
    """This org's LLM spend so far today, in cents, from the SAME ledger the deployed pre-flight
    breaker reads.

    `api/routes._llm_over_daily_cap` sums `llm_costs` since `date_trunc('day', now())` and
    compares it against `settings.daily_llm_usd_cap`. If the governor opened its day from
    anywhere else the two would disagree about how much has been spent, and which answer applied
    would depend on which door the work came through — the exact failure `batch.breaker`'s
    docstring refuses to introduce.

    Rounded UP, because a governor that under-counts the opening balance authorises a little
    more than the number a human approved, once per process, forever.

    Fails OPEN — an unreadable ledger returns 0 rather than pretending the day is spent. Blocking
    every tenant on a broken query is worse than one uncapped day, which is the judgement the
    deployed check already makes.
    """
    if engine is None:
        return 0
    try:
        from sqlalchemy import text

        from genios_engine.platform.metrics import cost_usd_sql
        with engine.connect() as c:
            # cost_usd_sql() already returns the sum(...) aggregate — never wrap it again.
            usd = c.execute(text(
                f"select coalesce({cost_usd_sql()}, 0) from llm_costs where org_id=:o "
                "and created_at >= date_trunc('day', now())"), {"o": org_id}).scalar()
        return math.ceil(float(usd or 0.0) * _MINOR_PER_USD)
    except Exception:      # noqa: BLE001 — a broken cost read must never block extraction
        _log.exception("daily spend read failed for org=%s — opening the governor at zero", org_id)
        return 0


def _org_tier(engine, org_id: str) -> str | None:
    """The org's plan tier, or None when it cannot be read. None falls to the trial row in
    `plan_of`, which is the least generous ceiling — an unreadable plan must not buy a bigger
    budget than a known one."""
    try:
        eng = engine if engine is not None else getattr(make_graph_store(), "engine", None)
        if eng is None:
            return None
        from sqlalchemy import text as _text
        with eng.connect() as c:
            return c.execute(_text("select subscription_tier from orgs where id=:o"),
                             {"o": org_id}).scalar()
    except Exception:                      # noqa: BLE001 — never block ingestion on a DB blip
        _log.warning("plan tier read failed for org=%s — using the trial ceiling", org_id)
        return None


def make_cost_governor(org_id: str, *, engine=None):
    """L1.4.8's cost governor for ONE org, or `None` when no ceiling is configured.

    The three numbers all come from controls that already exist, so this adds an enforcement
    POINT and not a second budget:

    * `daily_minor` — `settings.daily_llm_usd_cap`, in cents. The same ceiling
      `_llm_over_daily_cap` refuses to start a sync at. Zero means "disabled" there, so zero
      means "no governor" here; anything else would turn a documented off-switch into a total
      block;
    * `daily_call_cap` — `GENIOS_LLM_DAILY_CAP`, the call ceiling from commit `7e17a6d`, read
      through the same env var and with the same "0 = no ceiling" meaning;
    * `t3_daily_minor` — `settings.daily_t3_llm_usd_cap` when set. Unset it equals the daily
      ceiling, which makes the T3 sub-budget non-binding rather than guessed: `llm_costs` does
      not record a tier, so this process cannot know what today has already spent at T3, and a
      sub-ceiling opened at an invented balance would demote frontier work for a reason nobody
      could check.

    The opening ledger is READ HERE, once per lane, and advanced in-process from then on. That
    is what makes the ceiling bind within a sweep instead of only between sweeps.
    """
    s = get_settings()
    cap_usd = float(getattr(s, "daily_llm_usd_cap", 0) or 0)
    if cap_usd <= 0:
        return None                       # documented global off-switch; a plan must not re-arm it
    # THE PLAN ALSO BINDS. Ingestion spend is never charged to the customer in credits (the
    # working rule puts user-facing credits on the intelligence surface only), so the ONLY thing
    # standing between a trial account with a 200,000-message mailbox and an unbounded bill was
    # this one global number — set at $25/day for a paying tenant and applied identically to a
    # free 15-day trial, i.e. up to ~$375 of model spend to give the product away. The plan's own
    # ceiling is taken as a MINIMUM with the global one, so tightening either tightens the org.
    from genios_engine.platform.billing import plan_ingest_usd_cap
    cap_usd = min(cap_usd, plan_ingest_usd_cap(_org_tier(engine, org_id)))
    from genios_engine.capture.semantic.batch import Budget, CostGovernor, Ledger
    daily_minor = int(cap_usd * _MINOR_PER_USD)
    t3_usd = float(getattr(s, "daily_t3_llm_usd_cap", 0) or 0)
    t3_minor = min(int(t3_usd * _MINOR_PER_USD), daily_minor) if t3_usd > 0 else daily_minor
    call_cap = int(os.environ.get("GENIOS_LLM_DAILY_CAP", "20000") or 0)
    spent = _spent_today_minor(engine, org_id)
    return CostGovernor(
        Budget(daily_minor=daily_minor, t3_daily_minor=t3_minor,
               daily_call_cap=max(0, call_cap), breaker_bp=_BREAKER_BP),
        Ledger(spent_minor=spent, t3_spent_minor=0, calls=0))


def make_structured_lane(org_id: str, *, engine=_UNSET):
    """L1.3.9-U5's bundle for ONE org — the typed-record route's zone and discovery store.

    UNCONDITIONAL, unlike `make_semantic_lane` below, and that is the whole point: the structured
    bypass calls no model, so there is nothing to key off a model being configured and nothing an
    activation row could sensibly gate. A HubSpot deal that lands for an unactivated tenant is
    still a typed record with a close date, and it is resolved in the ORG's zone rather than in
    UTC because that is what decides which calendar day it falls on.
    """
    from genios_engine.capture.pipeline import StructuredLane
    if engine is _UNSET:
        graph = make_graph_store()
        engine = getattr(graph, "engine", None)
    return StructuredLane(timezone=_org_timezone(engine, org_id),
                          open_lane=make_open_lane_store())


def make_semantic_lane(org_id: str, *, now: datetime | None = None, engine=_UNSET, llm=_UNSET,
                       activated: frozenset[str] | None = None):
    """The S2 lane for ONE org, or `None` when it must not run — the strangler fig's gate.

    THREE conditions, all required, and the order is cheapest-first:

    1. a real model is configured. Without an Anthropic key there is nothing to call, and a lane
       around a `None` client would fail every event of every sweep;
    2. this TENANT is activated (`platform/activation.py`). Not a config flag — doc 04 forbids one
       here by name, because a global boolean is either never exercised or switched on for
       everybody at once;
    3. the tenant is reachable in a database that can answer 2. No database answers "not
       activated", which is the state every tenant is in today.

    `None` is the ordinary answer and it costs nothing: `capture_event` with `semantic=None`
    behaves exactly as it did before the lane existed.

    `activated` lets a cross-org sweep read the activation set ONCE and hand it to every
    connection, instead of one query per tenant per tick.
    """
    s = get_settings()
    # The key check gates the CONSTRUCTION of a client, not the use of one that was handed in.
    # In production `llm` is always `_UNSET`, so this is the same cheapest-first order the
    # docstring describes; with a client injected the question "is a model configured" is already
    # answered, and refusing anyway made this factory the one seam a caller holding its own
    # transport could not go through — so every such caller built the bundle by hand instead,
    # which is how a lane in a test ends up without the cache and the discovery store the
    # production bundle carries.
    if llm is _UNSET and not s.use_real_llm:
        return None
    if engine is _UNSET:
        graph = make_graph_store()
        engine = getattr(graph, "engine", None)
    if activated is None:
        from genios_engine.platform.activation import is_semantic_activated
        if not is_semantic_activated(engine, org_id):
            return None
    elif org_id not in activated:
        return None
    if llm is _UNSET:
        llm = make_llm_client()
    if llm is None:
        return None
    from genios_engine.capture.esqe.relevance import RelevancePage
    from genios_engine.capture.pipeline import SemanticLane
    # ONE governor object, shared by S2's extractor and S4's relevance page. Two would be two
    # ledgers for one day's money — the exact "second budget nobody reconciles" this factory's
    # own comment below warns about.
    governor = make_cost_governor(org_id, engine=engine)
    return SemanticLane(llm=llm, eval_time=now or datetime.now(timezone.utc),
                        cache=make_extraction_cache(),
                        # D6a: without this the guard runs with no store and the discovery lane
                        # never receives a row — a failure that raises nothing and shows up only
                        # as a report that stays empty.
                        open_lane=make_open_lane_store(),
                        # W9 defect #9: the cost governor was built, tested and never consulted,
                        # so a budget could not stop or demote a single call. This is the seam.
                        governor=governor,
                        # D6: L1.6.5's page seam. One batcher per lane, so the ambiguous
                        # remainder of a connector page is bought in whole prompts and read per
                        # event instead of being bought per event. It shares the governor above,
                        # and it is the reason "the model sees under 5%" is a rate this process
                        # can actually report (`RelevancePage.stats.llm_share_bp`).
                        relevance_page=RelevancePage(llm=llm, governor=governor),
                        timezone=_org_timezone(engine, org_id))


def _org_timezone(engine, org_id: str) -> str:
    """The org's IANA zone, or UTC. ALG-09 resolves "Friday" in it and stores UTC, so a wrong zone
    moves a deadline by hours — but a MISSING one is not a reason to fail a capture, and UTC is the
    same answer the rest of the engine already falls back to."""
    if engine is None:
        return "UTC"
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return str(conn.execute(text("select timezone from orgs where id=:o"),
                                    {"o": org_id}).scalar() or "UTC")
    except Exception:      # noqa: BLE001 — a missing zone is UTC, never a failed sweep
        return "UTC"
