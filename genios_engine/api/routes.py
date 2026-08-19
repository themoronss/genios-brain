from __future__ import annotations

import threading

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.fake import FakeGmailConnector
from genios_engine.capture.coverage.model import capability_of, compute_coverage
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.contracts.connection import Connection
from genios_engine.contracts.events import (AGENT_ACTIONS, AGENT_API_SCOPES, HUMAN_API_SCOPES,
                                            AgentEvent, HumanEvent)
from genios_engine.platform.auth import (AuthCtx, get_auth_ctx, get_current_org,
                                          require_internal, require_owner, require_scope)
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import (make_agent_event_store,
                                           make_agent_registry_store, make_card_store,
                                           make_connection_store,
                                           make_connector_for, make_cursor_store,
                                           make_document_job_store, make_graph_store,
                                           make_human_event_store, make_llm_client,
                                           make_pack_registry, make_parked_store,
                                           make_payload_store, make_prepared_store,
                                           make_relevance_classifier, make_repo,
                                           make_trace_repo)

router = APIRouter()

# Real (DB-backed) stores when DATABASE_URL is set, else in-memory — decided in wiring.
# One engine is shared across them (get_engine is process-cached).
_repo = make_repo()
_trace_repo = make_trace_repo()
_payload_store = make_payload_store()
_prepared_store = make_prepared_store()
_connections = make_connection_store()
_parked = make_parked_store()
_cursors = make_cursor_store()
_documents = make_document_job_store()
_human_events = make_human_event_store()
_agent_events = make_agent_event_store()
_agent_registry = make_agent_registry_store()
_llm = make_llm_client()                              # L2 Anthropic client (None if no key)
_graph = make_graph_store()                           # L2 context graph (None without DB)
_registry = make_pack_registry()                      # L4 pack registry (None without DB)
_card_store = make_card_store()                       # L5 delivery cards (None without DB)
_demo_repo = InMemorySourceEventRepository()          # /dev/ingest-sample only (no persistence)


# ── health / config ──────────────────────────────────────────────────────────────
def _bind_gate_costs(gate, org_id: str) -> None:
    """Point a shared relevance gate's cost recording at the tenant currently being synced.
    Cross-org sweeps reuse one classifier; without this every gate call would be billed to the
    first org in the loop."""
    if gate is not None and _graph is not None and hasattr(gate, "bind_costs"):
        gate.bind_costs(_graph.record_cost, org_id)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "layer": "L1 capture"}


@router.get("/config")
def config() -> dict:
    s = get_settings()
    return {"env": s.env, "composio": "real" if s.use_real_composio else "fake",
            "database": "postgres" if s.use_real_db else "in-memory",
            "l1_relevance": s.enable_l1_relevance}


# ── connections (one per startup/org — NOT in .env) ──────────────────────────────
class AddConnection(BaseModel):
    composio_user_id: str = ""          # that org's label in Composio (blank for DB source)
    source_type: str = "gmail"
    config: dict = {}                   # source-specific (e.g. DB: db_url/table/watermark)


@router.post("/connections")
def add_connection(body: AddConnection, org_id: str = Depends(get_current_org)) -> dict:
    conn = Connection(org_id=org_id, composio_user_id=body.composio_user_id,
                      source_type=body.source_type, config=body.config)
    _connections.add(conn)
    return {"added": True, "connection": conn.model_dump(mode="json")}


@router.get("/connections")
def list_connections(org_id: str = Depends(get_current_org)) -> dict:
    return {"connections": [c.model_dump(mode="json")
                            for c in _connections.list_active() if c.org_id == org_id]}


# ── ingestion ────────────────────────────────────────────────────────────────────
_log = get_logger("genios.api")

# known-sender resolver: "is this email already a person in the org's graph?" feeds the
# gate's W-01 whitelist so mail from known contacts is never N-code dropped. The resolver
# param existed in run_sync since day one — it was simply never passed, so W-01 never
# fired in production. Cached per org (5 min) — one query per sync, not per email.
_SENDER_CACHE: dict[str, tuple[float, frozenset]] = {}
_SENDER_TTL_S = 300.0


def _sender_resolver_for(org_id: str):
    if _graph is None:
        return None

    def _known(raw) -> bool:
        email = (getattr(raw, "actor_email", None) or "").strip().lower()
        if not email:
            return False
        import time
        now = time.time()
        hit = _SENDER_CACHE.get(org_id)
        if hit is None or now - hit[0] > _SENDER_TTL_S:
            from sqlalchemy import text
            with _graph.engine.connect() as c:
                rows = c.execute(text(
                    "select canonical_key from graph_nodes where org_id=:o "
                    "and node_type='person' and valid_to is null"), {"o": org_id}).fetchall()
            hit = (now, frozenset(r.canonical_key for r in rows if r.canonical_key))
            _SENDER_CACHE[org_id] = hit
        return email in hit[1]
    return _known


def _run_ledger(*, org_id: str, connection_id: str, source: str, mode: str, summary=None,
                error: str | None = None) -> None:
    """l1_sync_runs writer — the per-run ingestion ledger run_sync used to log-and-drop.

    `summary` is None and `error` is set when the caller is reporting a TOTAL sync failure (the
    connector never returned a batch, so no SyncSummary exists) — previously this case produced no
    row at all, so a fully-broken connection was invisible anywhere but the server log. Never raises:
    a ledger hiccup must not break the caller, whether that's the sync loop or a failure handler."""
    if _graph is None:
        return
    from sqlalchemy import text

    from genios_engine.platform.ids import new_id
    try:
        with _graph.engine.begin() as c:
            c.execute(text(
                "insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, "
                "scanned, emitted, dropped, parked, duplicate, quarantined, error) "
                "values (:r,:o,:c,:s,:m,:sc,:em,:dr,:pa,:du,:qu,:err)"),
                {"r": new_id("run"), "o": org_id, "c": connection_id, "s": source, "m": mode,
                 "sc": getattr(summary, "scanned", 0), "em": getattr(summary, "emitted", 0),
                 "dr": getattr(summary, "dropped", 0), "pa": getattr(summary, "parked", 0),
                 "du": getattr(summary, "duplicate", 0), "qu": getattr(summary, "quarantined", 0),
                 "err": error})
    except Exception:      # noqa: BLE001 — a ledger hiccup must not break the caller
        _log.exception("l1_sync_runs write failed org=%s conn=%s", org_id, connection_id)


def _notify_sync_failure(*, org_id: str, source: str, error: str) -> None:
    from genios_engine.platform import ops_alert
    ops_alert.notify("sync_failed", org_id=org_id, source=source, error=error[:300])
    try:
        from genios_engine.platform import analytics
        analytics.capture(org_id, "sync_failed", {"source": source, "error": error[:200]})
    except Exception:      # noqa: BLE001
        pass


def _run_l2(org_id: str) -> None:
    """Background L2 + L3 + L5 pass for one org. In-process (no Celery/Upstash). Wrapped so a
    single org's failure is LOGGED (not a silent uvicorn traceback) and never touches another org."""
    if _graph is None:
        return
    try:
        from genios_engine.context.runner import process_pending
        process_pending(org_id=org_id, store=_graph, llm=_llm, crypto_key=get_settings().crypto_key)
        from genios_engine.reason.runner import run_all as run_l3    # L3 after the graph updates
        run_l3(org_id=org_id, store=_graph, registry=_registry)
        if _card_store is not None:                              # L5: new gated signals → cards
            from genios_engine.deliver.pipeline import build_cards_for_org
            build_cards_for_org(graph=_graph, card_store=_card_store, org_id=org_id,
                                llm=_llm, registry=_registry)
    except Exception:
        _log.exception("L2/L3/L5 background pass failed for org_id=%s", org_id)


def _sync_connection(connection, mode: str, limit: int) -> None:
    """ONE connection's full pass (L1 sync + L2) — background, per-org independent. A sync failure
    is LOGGED with org/connection context (was a bare `except: pass` — the exact 'stuck tenant' an
    on-call gets paged about, engineered to be invisible)."""
    try:
        run_sync(make_connector_for(connection), org_id=connection.org_id,
                 connection_id=connection.connection_id, repo=_repo, mode=mode, limit=limit,
                 parked_store=_parked, relevance=make_relevance_classifier(connection.org_id),
                 trace_repo=_trace_repo, payload_store=_payload_store,
                 prepared_store=_prepared_store,
                 sender_resolver=_sender_resolver_for(connection.org_id),
                 cursor_store=_cursors,
                 document_job_store=_documents, source=connection.source_type, max_pages=20,
                 run_ledger=_run_ledger)
    except Exception as e:
        _log.exception("L1 sync failed for org_id=%s connection_id=%s",
                       connection.org_id, connection.connection_id)
        # A total failure (bad auth, provider outage) never reaches run_ledger inside run_sync — write
        # the row here so it's visible in the admin console instead of only in the server log.
        _run_ledger(org_id=connection.org_id, connection_id=connection.connection_id,
                    source=connection.source_type, mode=mode, error=str(e)[:500])
        _notify_sync_failure(org_id=connection.org_id, source=connection.source_type, error=str(e))
    _run_l2(connection.org_id)


def run_sync_sweep(mode: str = "incremental", limit: int | None = None) -> dict:
    """Full auto-sync sweep across EVERY active connection (all orgs): L1 pull for all connections,
    THEN one L2/L3/L5 pass per org (not per-connection — an org with 3 sources shouldn't re-reason 3×).
    Synchronous, per-connection error-isolated, in-process (no Celery/Upstash). Reused by the background
    scheduler (platform/scheduler.py) — the same work /ingest/all does, callable without a request.
    Idempotent at the data layer (source_events dedup), so a re-run (or a second instance) never
    double-writes."""
    limit = get_settings().sync_batch_limit if limit is None else limit
    conns = _connections.list_active()
    rc = make_relevance_classifier()
    l1_ok = l1_err = 0
    for conn in conns:                            # L1: pull each connection (one bad source ≠ others)
        _bind_gate_costs(rc, conn.org_id)
        try:
            run_sync(make_connector_for(conn), org_id=conn.org_id, connection_id=conn.connection_id,
                     repo=_repo, mode=mode, limit=limit, parked_store=_parked, relevance=rc,
                     trace_repo=_trace_repo, payload_store=_payload_store,
                     prepared_store=_prepared_store,
                     sender_resolver=_sender_resolver_for(conn.org_id),
                     cursor_store=_cursors,
                     document_job_store=_documents, source=conn.source_type, max_pages=20,
                     run_ledger=_run_ledger)
            l1_ok += 1
        except Exception as e:
            l1_err += 1
            _log.exception("auto-sync L1 failed org=%s conn=%s", conn.org_id, conn.connection_id)
            _run_ledger(org_id=conn.org_id, connection_id=conn.connection_id,
                        source=conn.source_type, mode=mode, error=str(e)[:500])
            _notify_sync_failure(org_id=conn.org_id, source=conn.source_type, error=str(e))
    orgs = {c.org_id for c in conns}
    for org in orgs:                              # L2/L3/L5: once per org, after all its sources pulled
        _run_l2(org)
    _log.info("auto-sync sweep complete: %d/%d connection(s) pulled, %d org(s) reasoned",
              l1_ok, len(conns), len(orgs))
    return {"connections": len(conns), "l1_ok": l1_ok, "l1_err": l1_err, "orgs": len(orgs)}


# Retained as a compatibility diagnostic only. Calibration authority is the durable
# ``calibration_runs`` uniqueness key; process memory never decides whether tuning may repeat.
_last_calibration_at = None


def run_maintenance_sweep(mode: str = "incremental", limit: int | None = None) -> dict:
    """The scheduler heartbeat (in-process, no Celery/Upstash): the data-sync sweep every tick, PLUS
    the two maintenance passes the queue otherwise never gets — the card LIFECYCLE sweep (expire +
    snooze-wake + abandoned-claim release) every tick, and the L6 CALIBRATION pass (precision →
    auto-mute → bounded nudges) weekly, per active pack per org. Without this, snoozed cards were a
    black hole, expired cards never cleared, and the self-tuning loop stayed inert (built, unscheduled)."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    sync = run_sync_sweep(mode=mode, limit=limit)
    try:
        lifecycle = _card_store.sweep_lifecycle()            # every tick: expire + snooze-wake + claim-release
    except Exception:                                        # noqa: BLE001 — never kill the heartbeat
        _log.exception("card lifecycle sweep failed")
        lifecycle = {"error": True}
    # retention clocks, ENFORCED: raw payloads (30d), prepared text (180d), and bounded Layer 4
    # context payloads. Hash/provenance rows remain after the L4 payload expires, but replay closes.
    retention = {}
    for name, store in (("raw_payloads", _payload_store), ("prepared_content", _prepared_store)):
        try:
            if hasattr(store, "purge_expired"):
                retention[name] = store.purge_expired()
        except Exception:                                    # noqa: BLE001 — never kill the heartbeat
            _log.exception("retention purge failed for %s", name)
            retention[name] = "error"
    if _graph is not None:
        try:
            from genios_engine.reason.store import ReasoningStore
            retention["reasoning_context_payloads"] = ReasoningStore(
                engine=_graph.engine).purge_expired_context_payloads(eval_time=now)
        except Exception:                                    # noqa: BLE001 — never kill the heartbeat
            _log.exception("retention purge failed for reasoning_context_payloads")
            retention["reasoning_context_payloads"] = "error"
    # L5 EXECUTIVE: turn authoritative decisions into tracked commitments, then advance every
    # commitment that has come due — validate, transition, remind, escalate, close.
    #
    # Runs BEFORE distribution on purpose: a reminder decided in this tick should leave in the
    # same tick rather than waiting a whole interval for the next one. Both passes are
    # idempotent and every write is guarded, so a double-run or a multi-instance deploy is safe.
    executive = None
    if _graph is not None:
        try:
            from genios_engine.executive.sweep import run_executive
            # Enumeration is inside the guard too: it is a database round trip like any other,
            # and a heartbeat that dies because one query failed stops card expiry, retention
            # and delivery along with it.
            orgs = _executive_orgs()
            planned = advanced = 0
            for org in orgs:
                try:
                    effective, _ = (_registry.effective(org) if _registry else (None, None))
                    result = run_executive(_graph.engine, org, eval_time=now,
                                           effective=effective)
                    planned += result["planned"].created
                    advanced += result["lifecycle"].examined
                except Exception:                            # noqa: BLE001 — one org ≠ the rest
                    _log.exception("executive sweep failed org=%s", org)
            executive = {"orgs": len(orgs), "commitments_created": planned,
                         "commitments_examined": advanced}
            if planned:
                _log.info("executive sweep: %d new commitment(s) across %d org(s)",
                          planned, len(orgs))
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("executive sweep pass failed")
            executive = {"error": True}
    # L6 distribution: enqueue new high/critical cards + the daily digest per org with an
    # active channel, then drain the outbox (retried, deduped, audited). Decoupled from
    # card creation on purpose — a slow Slack endpoint can never block the reasoning sweep.
    distribution = {}
    if _graph is not None:
        try:
            from genios_engine.deliver.outbox import run_distribution
            distribution = run_distribution(_graph.engine)
        except Exception:                                    # noqa: BLE001 — never kill the heartbeat
            _log.exception("distribution pass failed")
            distribution = {"error": True}
    calibration = None
    if _graph is not None:
        from genios_engine.feedback.calibrate import run_calibration
        orgs = {c.org_id for c in _connections.list_active()}
        runs = 0
        already_ran = 0
        for org in orgs:                                     # weekly: precision + auto-mute + nudges
            try:
                with _graph.engine.connect() as c:
                    packs = [r[0] for r in c.execute(text(
                        "select pack_id from tenant_packs where org_id=:o and state='active'"),
                        {"o": org})]
                for pid in (packs or ["sales"]):
                    result = run_calibration(_graph, org, registry=_registry, pack_id=pid,
                                             eval_time=now)
                    runs += int(bool(result.get("applied")))
                    already_ran += int(bool(result.get("already_ran")))
            except Exception:                                # noqa: BLE001 — one org's failure ≠ the rest
                _log.exception("calibration failed org=%s", org)
        calibration = {"orgs": len(orgs), "pack_runs": runs,
                       "already_ran": already_ran}
        _log.info("calibration pass complete: %d org(s), %d applied pack-run(s)", len(orgs), runs)
    # L6 LEARNING — the Atlas Learning & Evolution pass. Weekly per tenant, enforced by a
    # PostgreSQL tenant/week claim (not process memory), so it is safe to call every heartbeat:
    # a completed week is a no-op. Learns from OUTCOMES (execution_outcomes + delivery facts),
    # records immutable proposals, and publishes only validated + governed state. In-process (no
    # new Celery/Upstash task).
    learning = None
    if _graph is not None:
        try:
            from genios_engine.feedback.orchestrator import run_learning_sweep
            learning = run_learning_sweep(_graph.engine, now=now)
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("learning sweep failed")
            learning = {"error": True}
    # L2 GRAPH MAINTENANCE — entity lifecycle + a health measurement, per org.
    #
    # Here rather than in the L2 drain because both are O(graph), not O(event): running
    # them per event would make every email pay for a whole-tenant scan. Health is
    # recorded rather than just returned, because one number says little and the same
    # number falling over three weeks says a connector broke, a merge went wrong, or
    # correlation stopped reaching anything.
    graph_maintenance = None
    if _graph is not None:
        from genios_engine.context.health import (compute_health, purge_old_health,
                                                   refresh_node_lifecycle)
        orgs = {c.org_id for c in _connections.list_active()}
        checked = 0
        unhealthy = []
        for org in orgs:
            try:
                refresh_node_lifecycle(_graph, org, eval_time=now)
                health = compute_health(_graph, org, eval_time=now)
                purge_old_health(_graph, org)
                checked += 1
                if health.overall < 80:
                    unhealthy.append({"org_id": org, "overall": health.overall,
                                      "issues": [i["kind"] for i in health.issues]})
            except Exception:                                # noqa: BLE001 — one org's failure ≠ the rest
                _log.exception("graph maintenance failed org=%s", org)
        graph_maintenance = {"orgs_checked": checked, "unhealthy": unhealthy}
        if unhealthy:
            _log.warning("graph health below threshold for %d org(s): %s",
                         len(unhealthy), unhealthy)
    return {"sync": sync, "lifecycle": lifecycle, "retention": retention,
            "executive": executive, "distribution": distribution,
            "calibration": calibration, "learning": learning,
            "graph_maintenance": graph_maintenance}


def _executive_orgs() -> list[str]:
    """Tenants whose decisions can become commitments: those with an active pack.

    Deliberately not "orgs with an active connection" — the set the other passes use. A tenant
    can have a live connector and no applied pack, in which case Layer 4 produces nothing for
    Layer 5 to commit to, and sweeping them every tick is pure cost. An active pack is the
    narrowest set that can possibly yield a decision.
    """
    if _graph is None:
        return []
    with _graph.engine.connect() as c:
        return [row[0] for row in c.execute(text(
            "select distinct org_id from tenant_packs where state='active'"))]


@router.post("/ingest/all")
def ingest_all(background_tasks: BackgroundTasks, mode: str = "incremental",
               limit: int = 25, auto_l2: bool = True,
               _internal: None = Depends(require_internal)) -> dict:
    """Cross-org cron: sync EVERY connected startup through L1, then background L2. Internal-only
    (x-internal-token) — a tenant can't trigger a cross-org run or learn which orgs exist."""
    s = get_settings()
    rc = make_relevance_classifier()
    conns = _connections.list_active()          # every source type, every org
    totals = {"scanned": 0, "emitted": 0, "dropped": 0, "parked": 0, "duplicate": 0}
    per = []
    for conn in conns:
        _bind_gate_costs(rc, conn.org_id)
        try:
            summary = run_sync(make_connector_for(conn), org_id=conn.org_id,
                               connection_id=conn.connection_id, repo=_repo, mode=mode,
                               limit=limit, parked_store=_parked, relevance=rc,
                               trace_repo=_trace_repo, payload_store=_payload_store,
                               prepared_store=_prepared_store,
                               sender_resolver=_sender_resolver_for(conn.org_id),
                               cursor_store=_cursors, document_job_store=_documents,
                               source=conn.source_type, max_pages=20,
                               run_ledger=_run_ledger)
        except Exception as e:                   # one bad source never kills the rest
            per.append({"org_id": conn.org_id, "source": conn.source_type, "error": str(e)[:120]})
            continue
        for k in totals:
            totals[k] += getattr(summary, k)
        per.append({"org_id": conn.org_id, "source": conn.source_type,
                    "emitted": summary.emitted, "dropped": summary.dropped,
                    "parked": summary.parked})
    if auto_l2 and _graph is not None:              # L2 runs in the background per org
        for org in {c.org_id for c in conns}:
            background_tasks.add_task(_run_l2, org)
    return {"using": {"composio": s.use_real_composio, "db": s.use_real_db},
            "connections": len(conns), "totals": totals, "per_connection": per,
            "l2_background": auto_l2 and _graph is not None}


def _connected_capabilities(org_id: str) -> dict[str, str]:
    """Derive coverage from THIS org's DB connections — no in-memory state, survives restart."""
    out: dict[str, str] = {}
    for c in _connections.list_active():
        if c.org_id == org_id and (cap := capability_of(c.source_type)):
            out[cap] = "fresh"
    return out


@router.post("/sync/{connection_id}")
def sync_one(connection_id: str, background_tasks: BackgroundTasks,
             mode: str = "incremental", limit: int = 25,
             org_id: str = Depends(get_current_org)) -> dict:
    """PRODUCTION trigger: sync ONE of the authenticated tenant's connections (L1 + L2) in the
    BACKGROUND and return immediately. Per-org, independent — 4 startups sync concurrently."""
    conn = _connections.get(connection_id)
    if conn is None or conn.org_id != org_id:
        raise HTTPException(404, "connection not found")
    background_tasks.add_task(_sync_connection, conn, mode, limit)
    return {"scheduled": True, "connection_id": connection_id, "org_id": conn.org_id,
            "note": "L1 sync + L2 running in the background; this returned immediately"}


@router.post("/connections/{connection_id}/backfill")
def backfill_connection(connection_id: str, background_tasks: BackgroundTasks,
                        limit: int = 25, org_id: str = Depends(get_current_org)) -> dict:
    """Drain a connection's FULL history in the background — the older tail an incremental sync skips
    on a huge first connect (newest-first watermark + max_pages). OWNER-triggered, not automatic:
    it can pull thousands of items and each drives L2 extraction, so it is a deliberate cost choice."""
    conn = _connections.get(connection_id)
    if conn is None or conn.org_id != org_id:
        raise HTTPException(404, "connection not found")

    def _run() -> None:
        from genios_engine.capture.acquire.sync_runner import backfill_drain
        try:
            summary = backfill_drain(
                make_connector_for(conn), org_id=conn.org_id, connection_id=conn.connection_id,
                repo=_repo, source=conn.source_type, limit=limit,
                relevance=make_relevance_classifier(conn.org_id), parked_store=_parked,
                sender_resolver=_sender_resolver_for(conn.org_id), trace_repo=_trace_repo,
                payload_store=_payload_store, prepared_store=_prepared_store,
                document_job_store=_documents, run_ledger=_run_ledger)
            _log.info("backfill drain done org=%s conn=%s scanned=%s emitted=%s",
                      conn.org_id, connection_id, summary.scanned, summary.emitted)
            if _graph is not None:
                _run_l2(conn.org_id)                     # extract everything the backfill landed
        except Exception:                                # a drain failure must not crash the worker
            _log.exception("backfill drain failed org=%s conn=%s", conn.org_id, connection_id)

    background_tasks.add_task(_run)
    return {"started": True, "connection_id": connection_id,
            "note": "full-history backfill draining in the background (older tail incremental skips)"}


@router.post("/dev/ingest-sample", include_in_schema=False)
def ingest_sample(_internal: None = Depends(require_internal)) -> dict:
    """No-config demo: fake Gmail event through the FULL L1 pipeline, returns trace.

    Gated behind the internal token: it is a developer aid, and an unauthenticated POST that runs
    the capture pipeline has no business being reachable on a customer deployment."""
    conn = FakeGmailConnector()
    out = []
    for o in conn.incremental_changes().objects:
        res = capture_event(o, org_id=conn.org_id, connection_id=conn.connection_id,
                            repo=_demo_repo)
        out.append({"outcome": res.outcome,
                    "trace": [{"stage": r.stage, "action": r.action.value,
                               "reason": r.reason_code} for r in res.trace.records],
                    "gated_event": res.gated.model_dump(mode="json") if res.gated else None})
    return {"store_size": _demo_repo.count(), "results": out}


# ── parked / coverage ────────────────────────────────────────────────────────────
@router.get("/parked")
def list_parked(reason_code: str | None = None, org_id: str = Depends(get_current_org)) -> dict:
    return {"parked": [p.model_dump(mode="json") for p in _parked.list(org_id, reason_code)]}


@router.post("/parked/{event_id}/recover")
def recover_parked(event_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """Human promotes a grey-zone parked event → re-inject it: flip the source event to 'emitted'
    so the next L2 pass processes it (its encrypted payload was kept). No longer a no-op."""
    ev = _parked.get(event_id)
    if ev is None or getattr(ev, "org_id", None) != org_id:
        raise HTTPException(404, "parked event not found")
    reinjected = False
    s = get_settings()
    if s.use_real_db:
        from sqlalchemy import text
        from genios_engine.platform.db import get_engine
        with get_engine(s.database_url).begin() as c:
            has_payload = c.execute(text("select 1 from raw_payloads where org_id=:o and event_id=:e"),
                                    {"o": org_id, "e": event_id}).first() is not None
            if has_payload:
                reinjected = c.execute(text(
                    "update source_events set outcome='emitted' where org_id=:o and event_id=:e "
                    "and outcome='parked'"), {"o": org_id, "e": event_id}).rowcount > 0
    _parked.set_status(event_id, "recovered")
    return {"event_id": event_id, "status": "recovered", "reinjected": reinjected}


def _company_knowledge_count(org_id: str) -> int:
    """Distinct company-knowledge assertions this org has WRITTEN (non-app evidence: policies,
    pricing, SOPs — source='internal'). Surfaced in coverage so written canon is visible evidence,
    not an ignored 'not connected'. Returns 0 (never an error) when there is no graph/DB."""
    if _graph is None:
        return 0
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        return int(c.execute(text(
            "select count(distinct source_object_id) from source_events "
            "where org_id=:o and source='internal'"), {"o": org_id}).scalar() or 0)


@router.get("/coverage")
def coverage(domain: str = "sales", org_id: str = Depends(get_current_org)) -> dict:
    return compute_coverage(domain, _connected_capabilities(org_id),
                            company_knowledge_count=_company_knowledge_count(org_id))


# ── connection lifecycle ─────────────────────────────────────────────────────────
@router.post("/connections/{connection_id}/{action}")
def connection_lifecycle(connection_id: str, action: str,
                         org_id: str = Depends(get_current_org)) -> dict:
    status = {"pause": "paused", "resume": "connected", "disconnect": "disconnected"}.get(action)
    if status is None:
        raise HTTPException(422, "action must be pause | resume | disconnect")
    conn = _connections.get(connection_id)
    if conn is None or conn.org_id != org_id:
        raise HTTPException(404, "connection not found")
    _connections.set_status(connection_id, status)
    return {"connection_id": connection_id, "status": status}


@router.post("/workspace/{action}")
def workspace_kill(action: str, ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    """Per-org kill (spec Level C) — the tenant's 'stop everything' switch. pause → every request
    for this org 503s (checked in get_current_org, cache-invalidated for immediate effect); resume
    lifts it. Uses get_auth_ctx (NOT get_current_org) so a paused owner can still call resume.
    Complements per-source pause (/connections/{id}/pause) and the global kill."""
    if ctx.scopes is not None:
        raise HTTPException(403, "owner credential required")
    org_id = ctx.org_id
    enabled = {"pause": False, "resume": True}.get(action)
    if enabled is None:
        raise HTTPException(422, "action must be pause | resume")
    with _graph.engine.begin() as c:
        c.execute(text("insert into feature_flags (key, enabled) values (:k, :e) "
                       "on conflict (key) do update set enabled=:e"),
                  {"k": f"kill_switch:{org_id}", "e": enabled})
    try:
        from genios_engine.platform.cache import get_cache
        get_cache().delete(f"ff:kill:{org_id}")            # immediate effect, don't wait for TTL
    except Exception:      # noqa: BLE001
        pass
    return {"org_id": org_id, "paused": not enabled}


# ── self-serve connect (frontend initiates Composio OAuth) ───────────────────────
class InitiateConnect(BaseModel):
    source_type: str
    auth_config_id: str                 # from Composio, per toolkit
    user_id: str                        # the org's Composio entity/label
    callback_url: str | None = None


@router.post("/connect/initiate")
def connect_initiate(body: InitiateConnect, org_id: str = Depends(get_current_org)) -> dict:
    """Authenticated tenant starts OAuth for a tool → Composio redirect URL. After authorizing,
    add a /connections row with the same user_id."""
    from genios_engine.platform.wiring import IMPLEMENTED_SOURCE_TYPES
    if body.source_type not in IMPLEMENTED_SOURCE_TYPES:
        raise HTTPException(400, f"'{body.source_type}' is not available yet — no connector is "
                                 "implemented for it. Connecting would authorize data GeniOS "
                                 "cannot ingest.")
    s = get_settings()
    if not s.use_real_composio:
        raise HTTPException(400, "Composio not configured")
    from composio import Composio
    c = Composio(api_key=s.composio_api_key)
    req = c.connected_accounts.initiate(body.user_id, body.auth_config_id,
                                        callback_url=body.callback_url)
    redirect = (getattr(req, "redirect_url", None) or getattr(req, "redirect_uri", None)
                or getattr(req, "redirectUrl", None))
    return {"redirect_url": redirect, "request_id": getattr(req, "id", None),
            "source_type": body.source_type}


# frontend tool name → Composio toolkit slug (Composio slugs are lowercase)
_TOOLKIT_SLUGS = {
    "gmail": "gmail", "notion": "notion", "slack": "slack", "hubspot": "hubspot", "jira": "jira",
    "gcal": "googlecalendar", "calendar": "googlecalendar", "google_calendar": "googlecalendar",
    "gdrive": "googledrive", "drive": "googledrive", "google_drive": "googledrive",
    # the dashboard uses ids gsheets/gdocs — accept those (and the short aliases) → real Composio slugs
    "gsheets": "googlesheets", "sheets": "googlesheets", "gdocs": "googledocs", "docs": "googledocs",
}


def _find_auth_config(comp, slug: str) -> str | None:
    """The org's Composio auth config id for a toolkit slug (created once in the Composio dashboard)."""
    acs = comp.auth_configs.list()
    items = getattr(acs, "items", None) or getattr(acs, "data", None) or []
    for a in items:
        tk = getattr(a, "toolkit", None)
        tk_slug = (getattr(tk, "slug", None) if tk else None) or getattr(a, "toolkit_slug", None)
        if tk_slug and str(tk_slug).lower() == slug:
            return getattr(a, "id", None)
    return None


@router.get("/auth/{tool}/connect")
def tool_connect_redirect(tool: str, org_id: str, callback: str | None = None):
    """Full-page OAuth start for a tool (the integrations 'Connect' button navigates here). It's a
    top-level browser navigation so the JWT can't be sent — org_id comes as a query param and only
    STARTS an OAuth flow (no tenant data exposed). Finds the toolkit's Composio auth config, mints a
    Connect Link (connected_accounts.link), mirrors a connection row so /sync works after auth, and
    302-redirects the browser to the provider's consent page."""
    from fastapi.responses import RedirectResponse
    s = get_settings()
    if not s.use_real_composio:
        raise HTTPException(400, "Composio not configured — set GENIOS_COMPOSIO_API_KEY in the engine .env")
    # Stop the 502 lie: never START an OAuth flow for a source make_connector_for can't
    # build — the user would grant real data access and every later sync would crash.
    from genios_engine.platform.wiring import IMPLEMENTED_SOURCE_TYPES
    if tool.lower() not in IMPLEMENTED_SOURCE_TYPES:
        raise HTTPException(400, f"'{tool}' is not available yet — its connector is not "
                                 "implemented. Coming soon; nothing was authorized.")
    slug = _TOOLKIT_SLUGS.get(tool.lower(), tool.lower())
    from composio import Composio
    comp = Composio(api_key=s.composio_api_key)
    try:
        auth_config_id = _find_auth_config(comp, slug)
    except Exception as e:      # noqa: BLE001
        raise HTTPException(502, f"Composio auth_configs.list failed: {str(e)[:200]}")
    if not auth_config_id:
        raise HTTPException(400, f"No Composio auth config for '{slug}'. Create one for this toolkit in "
                            f"the Composio dashboard (one-time), then retry Connect.")
    try:
        # callback_url → after the user authorizes, Composio sends them BACK to the dashboard
        # (instead of leaving them on the 'you can close this window' page).
        req = (comp.connected_accounts.link(org_id, auth_config_id, callback_url=callback)
               if callback else comp.connected_accounts.link(org_id, auth_config_id))
    except Exception as e:      # noqa: BLE001 — surface a readable message, not a 500
        raise HTTPException(502, f"Composio link failed for {slug}: {str(e)[:250]}")
    redirect = (getattr(req, "redirect_url", None) or getattr(req, "redirect_uri", None)
                or getattr(req, "redirectUrl", None))
    if not redirect:
        raise HTTPException(502, f"Composio returned no redirect URL for {slug}")
    # NOTE: we do NOT mirror a local connection row here — a click ≠ a completed OAuth. The tool
    # is "connected" only once Composio reports an ACTIVE account (see _composio_connected below),
    # which is the single source of truth for status + sync.
    from genios_engine.platform.audit import record
    record(org_id, "source_connect_started", actor_type="user", target_type="source",
           target_id=_norm_source(tool), metadata={"audit_category": "update", "tool": tool})
    return RedirectResponse(redirect, status_code=302)


# Composio toolkit slug → our source_type (reverse of _TOOLKIT_SLUGS). Keys must match the ids the
# dashboard uses (gsheets/gdocs, not sheets/docs) so status/sync/disconnect resolve to the same tool.
_SLUG_TO_SOURCE = {"googlecalendar": "gcal", "gmail": "gmail", "notion": "notion",
                   "googledrive": "gdrive", "googlesheets": "gsheets", "googledocs": "gdocs",
                   "slack": "slack", "hubspot": "hubspot", "jira": "jira"}


def _norm_source(tool: str) -> str:
    """Normalize any tool name (gcal / calendar / google_calendar / GOOGLECALENDAR) to our
    canonical source_type (gcal), so connect/sync/disconnect all agree regardless of the label."""
    slug = _TOOLKIT_SLUGS.get(tool.lower(), tool.lower())
    return _SLUG_TO_SOURCE.get(slug, tool.lower())


def _composio_connected(org_id: str) -> list[dict]:
    """The org's Composio accounts (the source of truth for what's connected). ACTIVE = usable."""
    from composio import Composio
    acs = Composio(api_key=get_settings().composio_api_key).connected_accounts.list(user_ids=[org_id])
    items = getattr(acs, "items", None) or getattr(acs, "data", None) or []
    out = []
    for a in items:
        tk = getattr(a, "toolkit", None)
        slug = (getattr(tk, "slug", None) if tk else None) or getattr(a, "toolkit_slug", None)
        if not slug:
            continue
        out.append({"slug": slug, "source_type": _SLUG_TO_SOURCE.get(slug, slug),
                    "status": str(getattr(a, "status", "")).upper(), "id": getattr(a, "id", None)})
    return out


def _org_tool_connection(org_id: str, tool: str):
    return next((c for c in _connections.list_active()
                 if c.org_id == org_id and c.source_type == tool), None)


@router.post("/integrations/{tool}/disconnect")
def integration_disconnect(tool: str, wipe_data: bool = False,
                           org_id: str = Depends(get_current_org)) -> dict:
    """Disconnect a tool for the authed tenant — deletes the Composio account(s) for that toolkit.
    wipe_data=false → keep the captured graph data; wipe_data=true → also delete source_events +
    raw payloads for that source."""
    removed = 0
    if get_settings().use_real_composio:
        from composio import Composio
        comp = Composio(api_key=get_settings().composio_api_key)
        for a in _composio_connected(org_id):
            if a["source_type"] == _norm_source(tool) and a.get("id"):
                try:
                    comp.connected_accounts.delete(a["id"]); removed += 1
                except Exception:      # noqa: BLE001
                    _log.warning("composio delete failed for %s/%s", tool, a.get("id"))
    wiped = 0
    if wipe_data and get_settings().use_real_db:
        from sqlalchemy import text
        from genios_engine.platform.db import get_engine
        eng = get_engine(get_settings().database_url)
        with eng.begin() as c:
            wiped = c.execute(text("delete from raw_payloads where org_id=:o and event_id in "
                                   "(select event_id from source_events where org_id=:o and source=:s)"),
                              {"o": org_id, "s": _norm_source(tool)}).rowcount
            c.execute(text("delete from source_events where org_id=:o and source=:s"),
                      {"o": org_id, "s": _norm_source(tool)})
    from genios_engine.platform.audit import record
    record(org_id, "source_disconnected", actor_type="user", target_type="source",
           target_id=_norm_source(tool),
           metadata={"audit_category": "update", "tool": tool, "wipe_data": wipe_data,
                     "accounts_removed": removed, "events_wiped": wiped})
    return {"disconnected": True, "tool": tool, "accounts_removed": removed,
            "data_wiped": bool(wipe_data), "payloads_wiped": wiped}


@router.get("/integrations/status")
def integrations_status(org_id: str = Depends(get_current_org)) -> dict:
    """Per-tool connection status from Composio's ACTUAL accounts (source of truth). ACTIVE = usable;
    EXPIRED/INITIATED = needs (re)connect. This is what the integrations page reads."""
    if not get_settings().use_real_composio:
        return {}
    try:
        accounts = _composio_connected(org_id)
    except Exception as e:      # noqa: BLE001
        _log.warning("composio status failed for %s: %s", org_id, e)
        return {}
    # A sync now runs as a DURABLE JOB (not the old in-memory BackgroundTask flag), so "running" must
    # come from the job/progress state — otherwise the Sync button never shows "Syncing…" while a job
    # is actually running. Read it ONCE for the org (all its tools sync together).
    job_running = _sync_active(org_id)
    out: dict = {}
    for a in accounts:
        active = a["status"] == "ACTIVE"
        cur = out.get(a["source_type"])
        if cur is None or active:      # prefer an ACTIVE account if the tool has several
            out[a["source_type"]] = {"connected": active,
                                     "syncStatus": ("running"
                                                    if (job_running
                                                        or _sync_is_running(org_id, a["source_type"]))
                                                    else "idle"),
                                     "freshness": "error" if not active else "stale",
                                     "syncIntervalHours": 6,   # trial cadence; drives the card copy
                                     "lastSyncAt": None,
                                     "metadata": {"recordsPulled": 0, "entitiesExtracted": 0,
                                                  "factsExtracted": 0}}
    # per-source counts — what each connection has actually pulled into the graph (so the dashboard
    # "Connected sources" row shows real pulled/entities/facts, not zeros). Best-effort: a failure
    # here never breaks the base connection status.
    if out and _graph is not None:
        try:
            from sqlalchemy import text
            with _graph.engine.connect() as c:
                ev = {r.source: r for r in c.execute(text(
                    "select source, count(*) pulled, max(captured_at) last from source_events "
                    "where org_id=:o group by source"), {"o": org_id})}
                ent = {r.source: r.n for r in c.execute(text(
                    "select se.source, count(*) n from graph_nodes gn "
                    "join source_events se on se.event_id=gn.created_by_event_id and se.org_id=gn.org_id "
                    "where gn.org_id=:o and gn.valid_to is null group by se.source"), {"o": org_id})}
                fac = {r.source: r.n for r in c.execute(text(
                    "select se.source, count(*) n from graph_facts gf "
                    "join source_events se on se.event_id=gf.created_by_event_id and se.org_id=gf.org_id "
                    "where gf.org_id=:o and gf.valid_to is null and gf.status='active' group by se.source"),
                    {"o": org_id})}
                llm = {r.source: r.n for r in c.execute(text(
                    "select se.source, count(*) n from llm_costs lc "
                    "join source_events se on se.event_id=lc.event_id and se.org_id=lc.org_id "
                    "where lc.org_id=:o group by se.source"), {"o": org_id})}
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            for st, entry in out.items():
                e = ev.get(st)
                entry["metadata"] = {"recordsPulled": int(e.pulled) if e else 0,
                                     "entitiesExtracted": int(ent.get(st, 0)),
                                     "factsExtracted": int(fac.get(st, 0)),
                                     "llmCalls": int(llm.get(st, 0))}
                last = e.last if (e and e.last) else None
                entry["lastSyncAt"] = last.isoformat() if last else None
                # real freshness from age of the last pull vs the sync cadence (6h trial):
                if entry["connected"] and last is not None:
                    age_h = (now - last).total_seconds() / 3600.0
                    entry["freshness"] = ("healthy" if age_h <= 6 else
                                          "aging" if age_h <= 24 else "stale")
        except Exception as e:      # noqa: BLE001 — counts are a nicety, never break status
            _log.warning("status counts failed for %s: %s", org_id, e)
    return out


def _sync_source(org_id: str, source_type: str, limit: int):
    from genios_engine.contracts.connection import Connection
    conn = Connection(org_id=org_id, composio_user_id=org_id, source_type=source_type, config={})
    rel = make_relevance_classifier(org_id)    # ONE classifier: connector gates on snippet + fetches
    return run_sync(make_connector_for(conn, relevance=rel),   # only keepers; pipeline reuses its cache
                    org_id=org_id, connection_id=conn.connection_id,
                    repo=_repo, mode="incremental", limit=limit, parked_store=_parked,
                    relevance=rel, trace_repo=_trace_repo,
                    payload_store=_payload_store, prepared_store=_prepared_store,
                    sender_resolver=_sender_resolver_for(org_id), cursor_store=_cursors,
                    document_job_store=_documents, source=source_type, max_pages=3,
                    run_ledger=_run_ledger)


# Onboarding backfill is WINDOW-bounded (60d email / 120d calendar), not count-bounded — the user
# gets "2 months of everything". These are SAFETY ceilings only, high enough that a normal inbox is
# fully covered but a pathological 20k-inbox can't run away on time/LLM. Hit → logged, never silent.
_BACKFILL_MAX_ROUNDS = 200      # 200 × 25 = ~5000 messages ceiling per source (was 24 ≈ 600)
_BACKFILL_L2_EVERY = 6          # drain L2 every N rounds so facts appear DURING the backfill
_SOURCE_EVENT_CAP: dict[str, int] = {"gcal": 2000}     # calendar safety ceiling (was 150)

# Which (org, source) syncs are ACTIVE right now. Lives on the SERVER for the whole L1+backfill+L2
# lifetime, so /integrations/status can report "running" and the Sync button stays "Syncing…" from
# ANY page load — a client's local button state resets on navigation, this does not. Cleared when
# the whole background chain finishes (or on failure). In-memory = per-process (fine for the single
# app instance; a restart clears it, and a restart also kills the sync, so the two agree).
_running_syncs: set[tuple[str, str]] = set()
_running_lock = threading.Lock()


def _set_sync_running(org_id: str, source: str, running: bool) -> None:
    with _running_lock:
        (_running_syncs.add if running else _running_syncs.discard)((org_id, source))


def _sync_is_running(org_id: str, source: str) -> bool:
    with _running_lock:
        return (org_id, source) in _running_syncs


def _backfill_full(org_id: str, source_type: str, limit: int = 25,
                   max_rounds: int = _BACKFILL_MAX_ROUNDS) -> None:
    """First-connect history backfill, run once in the background — BOUNDED and progressive.

    The incremental 'Sync' only pulls the newest page and advances a watermark, so on a large first
    connect the older tail is skipped permanently. This pages BACKWARD through the window (dedup-safe,
    cursor_store=None so it never touches the incremental watermark) through the SAME S2 junk-gate,
    and drains L2 every few rounds so facts surface progressively instead of only at the very end.

    Why bounded: a high-volume inbox can hold thousands of messages in the window, and fetching +
    gating every one costs real time/LLM. We cap at `max_rounds` (~600 messages) — plenty to reach a
    normal 2-month business history and this inbox's recent real mail — and LOG (never silently) if
    more history remains, which an owner can pull with the manual /connections/{id}/backfill."""
    from genios_engine.contracts.connection import Connection
    conn = Connection(org_id=org_id, composio_user_id=org_id, source_type=source_type, config={})
    connector = make_connector_for(conn)
    event_cap = _SOURCE_EVENT_CAP.get(source_type)     # e.g. calendar → 150 events max
    cursor: str | None = None
    scanned = emitted = 0
    try:
        for rnd in range(max_rounds):
            summary = run_sync(
                connector, org_id=org_id, connection_id=conn.connection_id, repo=_repo,
                mode="backfill", cursor=cursor, limit=limit, source=source_type,
                cursor_store=None, max_pages=1, relevance=make_relevance_classifier(org_id),
                parked_store=_parked, sender_resolver=_sender_resolver_for(org_id),
                trace_repo=_trace_repo, payload_store=_payload_store,
                prepared_store=_prepared_store, document_job_store=_documents,
                run_ledger=_run_ledger)
            scanned += summary.scanned
            emitted += summary.emitted
            cursor = summary.next_cursor
            # Per-source hard event cap (e.g. calendar 150): stop once the org holds that many for
            # this source, so a busy calendar never floods in more than the user asked for.
            if event_cap is not None and _graph is not None:
                with _graph.engine.connect() as _c:
                    have = _c.execute(text("select count(*) from source_events "
                                           "where org_id=:o and source=:s"),
                                      {"o": org_id, "s": source_type}).scalar() or 0
                if have >= event_cap:
                    break
            if _graph is not None and (rnd + 1) % _BACKFILL_L2_EVERY == 0:
                try:
                    _run_l2(org_id)               # progressive: facts appear mid-backfill
                except Exception:      # noqa: BLE001
                    _log.exception("backfill mid-L2 failed org=%s", org_id)
            if not cursor:
                break                             # window exhausted
        if _graph is not None:
            _run_l2(org_id)                       # final drain of whatever remains
        capped = cursor is not None
        _log.info("first-connect backfill %s org=%s source=%s scanned=%s emitted=%s%s",
                  "CAPPED" if capped else "done", org_id, source_type, scanned, emitted,
                  " — more history remains; run manual /backfill to continue" if capped else "")
        from genios_engine.platform.audit import record
        record(org_id, "data_backfilled", actor_type="system", target_type="source",
               target_id=source_type,
               metadata={"audit_category": "meeting" if source_type == "gcal" else "data_extraction",
                         "source": source_type, "scanned": scanned, "emitted": emitted,
                         "capped": capped})
    except Exception:      # noqa: BLE001 — a backfill failure must never crash the worker
        _log.exception("first-connect backfill failed org=%s source=%s (scanned=%s)",
                       org_id, source_type, scanned)


def _source_count(org_id: str, source: str) -> int:
    if _graph is None:
        return 0
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        return int(c.execute(text("select count(*) from source_events where org_id=:o and source=:s"),
                             {"o": org_id, "s": source}).scalar() or 0)


def _pending_count(org_id: str) -> int:
    """How many captured events still await L2 — mirrors runner._pull's filter, for a progress total."""
    if _graph is None:
        return 0
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        return int(c.execute(text(
            "select count(*) from source_events se where se.org_id=:o and se.outcome='emitted' "
            "and se.event_id not in (select event_id from l2_extraction_results where org_id=:o) "
            "and se.event_id not in (select event_id from l2_processing_runs "
            "                        where org_id=:o and status in ('done','parked'))"),
            {"o": org_id}).scalar() or 0)


def _backfill_one_source(org_id: str, source_type: str, limit: int = 25,
                         max_rounds: int = _BACKFILL_MAX_ROUNDS, on_round=None) -> tuple[int, int, bool]:
    """Window-bounded backfill of ONE source (no interleaved L2 — L2 runs as its own phase after).
    Pages backward through the 2-month window; `on_round(count)` fires each round so the progress
    bar can move live. Returns (scanned, emitted, capped-at-ceiling)."""
    from genios_engine.contracts.connection import Connection
    conn = Connection(org_id=org_id, composio_user_id=org_id, source_type=source_type, config={})
    rel = make_relevance_classifier(org_id)    # ONE classifier for the whole backfill: the connector
    connector = make_connector_for(conn, relevance=rel)   # gates on snippet + fetches only keepers;
    event_cap = _SOURCE_EVENT_CAP.get(source_type)        # the pipeline reuses its primed verdicts.
    cursor: str | None = None
    scanned = emitted = 0
    for _rnd in range(max_rounds):
        summary = run_sync(
            connector, org_id=org_id, connection_id=conn.connection_id, repo=_repo,
            mode="backfill", cursor=cursor, limit=limit, source=source_type,
            cursor_store=None, max_pages=1, relevance=rel,
            parked_store=_parked, sender_resolver=_sender_resolver_for(org_id),
            trace_repo=_trace_repo, payload_store=_payload_store,
            prepared_store=_prepared_store, document_job_store=_documents, run_ledger=_run_ledger)
        scanned += summary.scanned
        emitted += summary.emitted
        cursor = summary.next_cursor
        if on_round is not None:
            try:
                on_round(_source_count(org_id, source_type))
            except Exception:      # noqa: BLE001 — progress is best-effort
                pass
        if event_cap is not None and _source_count(org_id, source_type) >= event_cap:
            break
        if not cursor:
            break                             # window exhausted
    capped = cursor is not None
    _log.info("onboarding backfill %s org=%s src=%s scanned=%s emitted=%s%s",
              "CAPPED" if capped else "done", org_id, source_type, scanned, emitted,
              " — safety ceiling hit, older tail remains (manual /backfill)" if capped else "")
    return scanned, emitted, capped


def _process_and_reason_tracked(org_id: str, heartbeat=None) -> None:
    """L2 (chunked, so progress moves) → graph → L3/L5, each surfaced as a plain-language phase.
    L3 runs ONCE at the very end (not mid-backfill) so the graph is stable when signals emit."""
    from genios_engine.context.runner import process_pending
    from genios_engine.platform import progress as P
    hb = heartbeat if callable(heartbeat) else (lambda *a, **k: None)
    eng = _graph.engine
    total = _pending_count(org_id)
    P.set_phase(eng, org_id, "processing", state="running", total=total, done=0,
                detail="Reading your messages…")
    processed = 0
    while True:                                # drain in chunks → live progress, still bounded/idempotent
        out = process_pending(org_id=org_id, store=_graph, llm=_llm,
                              crypto_key=get_settings().crypto_key, max_total=500)
        n = int(out.get("processed", 0))
        processed += n
        P.set_phase(eng, org_id, "processing",
                    done=min(processed, total or processed), detail=f"{processed} processed")
        hb()                                   # liveness beat per L2 chunk
        if n == 0:
            break
    P.set_phase(eng, org_id, "processing", state="done",
                total=total or processed, done=total or processed)

    P.set_phase(eng, org_id, "graph", state="running", detail="Linking people & companies…")
    P.set_phase(eng, org_id, "graph", state="done")     # read models are built during L2 above

    P.set_phase(eng, org_id, "intelligence", state="running", detail="Analyzing your relationships…")
    try:
        from genios_engine.reason.runner import run_all as run_l3
        run_l3(org_id=org_id, store=_graph, registry=_registry)
        if _card_store is not None:
            from genios_engine.deliver.pipeline import build_cards_for_org
            build_cards_for_org(graph=_graph, card_store=_card_store, org_id=org_id,
                                llm=_llm, registry=_registry)
        P.set_phase(eng, org_id, "intelligence", state="done", detail="Ready")
    except Exception:      # noqa: BLE001
        _log.exception("intelligence phase failed org=%s", org_id)
        P.set_phase(eng, org_id, "intelligence", state="error")


import os as _os

# Bill circuit-breaker: a per-org DAILY LLM-call ceiling. Cost is already bounded by idempotency +
# dedup + the ~5000 backfill ceiling, so this only ever trips on a genuine runaway (a bug/abuse
# re-processing many times over). Default is set FAR above a normal full sync (~a few hundred to a
# few thousand calls) so a real user never hits it. Fail-safe: it only refuses to START a new sync —
# it NEVER interrupts a run in progress.
_LLM_DAILY_CAP = int(_os.environ.get("GENIOS_LLM_DAILY_CAP", "20000"))


def _llm_over_daily_cap(org_id: str) -> bool:
    if _graph is None or _LLM_DAILY_CAP <= 0:
        return False
    try:
        from sqlalchemy import text
        with _graph.engine.connect() as c:
            n = c.execute(text("select count(*) from llm_costs where org_id=:o "
                               "and created_at >= date_trunc('day', now())"), {"o": org_id}).scalar()
        return int(n or 0) >= _LLM_DAILY_CAP
    except Exception:      # noqa: BLE001 — a broken cost check must never block a sync
        return False


def _sync_active(org_id: str) -> bool:
    """Is a sync run currently in progress for this org? Reads the DB progress state so a duplicate
    Sync click (or a second endpoint) doesn't reset the bar / spawn a competing run."""
    if _graph is None:
        return False
    try:
        from genios_engine.platform import progress as P
        return P.read(_graph.engine, org_id).get("state") == "running"
    except Exception:      # noqa: BLE001 — never let the guard block a sync
        return False


def _onboarding_sync_bg(org_id: str, sources: list[str], limit: int = 25, heartbeat=None) -> None:
    """THE single Sync action: for every connected tool, pull the full 2-month window, then process
    → graph → intelligence. Runs inside the durable worker; `heartbeat(checkpoint=None)` is called
    as it works so a crash leaves a stale beat and the job is re-claimed + resumed (idempotent —
    dedup + l2_processing_runs make a re-run safe). Re-raises on an unrecoverable failure so the
    worker can mark the job for retry."""
    from genios_engine.platform import progress as P
    eng = _graph.engine if _graph is not None else None
    hb = heartbeat if callable(heartbeat) else (lambda *a, **k: None)
    # Bill circuit-breaker (pre-flight only): refuse to START a new sync if this org has already made
    # a runaway number of LLM calls today. Never interrupts a run already in progress.
    if _llm_over_daily_cap(org_id):
        _log.warning("sync skipped: org=%s hit the daily LLM cap (%s) — cost circuit breaker",
                     org_id, _LLM_DAILY_CAP)
        if eng is not None:
            try:
                P.start(eng, org_id, sources)
                P.finish(eng, org_id, error=True,
                         detail="Paused for today — daily processing limit reached. Resumes tomorrow.")
            except Exception:      # noqa: BLE001
                pass
        return
    # gmail first, then calendar, then anything else — a sensible phase order for the UI.
    order = ([s for s in ("gmail", "gcal") if s in sources]
             + [s for s in sources if s not in ("gmail", "gcal")])
    try:
        if eng is not None:
            P.start(eng, org_id, order)
            P.set_phase(eng, org_id, "connecting", state="done")     # OAuth already completed
        for st in order:
            phase = "emails" if st == "gmail" else "calendar" if st == "gcal" else "processing"
            tracked = phase in ("emails", "calendar")
            if eng is not None and tracked:
                P.set_phase(eng, org_id, phase, state="running", detail="Fetching…")

            def _round(cnt, p=phase, _tracked=tracked):
                if eng is not None and _tracked:
                    P.set_phase(eng, org_id, p, done=cnt, detail=f"{cnt} synced")
                hb()                                    # liveness beat every backfill round
            try:
                _backfill_one_source(org_id, st, limit, on_round=_round)
            except Exception:      # noqa: BLE001 — one source failing never stops the rest
                _log.exception("onboarding backfill failed org=%s src=%s", org_id, st)
                if eng is not None and tracked:
                    P.set_phase(eng, org_id, phase, state="error")
            else:
                if eng is not None and tracked:
                    cnt = _source_count(org_id, st)
                    P.set_phase(eng, org_id, phase, state="done", done=cnt, total=cnt,
                                detail=f"{cnt} synced")
        if _graph is not None:
            _process_and_reason_tracked(org_id, heartbeat=hb)
        if eng is not None:
            P.finish(eng, org_id)
    except Exception as e:      # noqa: BLE001
        _log.exception("onboarding sync failed org=%s", org_id)
        if eng is not None:
            P.finish(eng, org_id, error=True, detail=f"{type(e).__name__}: {str(e)[:160]}")
        raise                                           # let the worker retry (resume) this job
    finally:
        for st in sources:
            _set_sync_running(org_id, st, False)


def run_one_sync_job(worker_id: str) -> bool:
    """Worker entry: claim ONE sync job and run it to completion. Returns True if a job ran (so the
    worker loops immediately to drain the queue), False if the queue was empty. A heartbeat ticker
    beats every 30s for the WHOLE run so a long step (e.g. L3) never looks stale; on failure the job
    goes back to 'queued' and a worker resumes it from the durable state."""
    if _graph is None:
        return False
    from genios_engine.platform import sync_jobs as J
    eng = _graph.engine
    job = J.claim_next(eng, worker_id)
    if job is None:
        return False
    jid, org, sources = job["id"], job["org_id"], job["sources"]
    stop_beat = threading.Event()

    def _beat() -> None:
        while not stop_beat.wait(30):
            try:
                J.heartbeat(eng, jid)
            except Exception:      # noqa: BLE001 — a missed beat is not fatal
                pass
    ticker = threading.Thread(target=_beat, daemon=True, name=f"job-beat-{jid}")
    ticker.start()
    try:
        _onboarding_sync_bg(org, sources, heartbeat=lambda *a, **k: J.heartbeat(eng, jid))
        J.complete(eng, jid)
    except Exception:      # noqa: BLE001 — orchestrator re-raises on failure → mark for resume/retry
        _log.exception("sync job failed org=%s job=%s", org, jid)
        try:
            J.fail(eng, jid, "run failed")
        except Exception:      # noqa: BLE001
            pass
    finally:
        stop_beat.set()
    return True


@router.post("/integrations/{tool}/sync")
def integration_sync(tool: str, background_tasks: BackgroundTasks, limit: int = 25,
                     org_id: str = Depends(get_current_org)) -> dict:
    """ENQUEUE a durable sync job for one tool, then return immediately. A server-side worker claims
    and runs it (L1 backfill → L2 → graph → intelligence), heart-beating + checkpointing, so it
    survives a process restart and the user closing the tab. The client only reads progress."""
    norm = _norm_source(tool)
    active = {a["source_type"] for a in _composio_connected(org_id) if a["status"] == "ACTIVE"}
    if norm not in active:
        raise HTTPException(404, f"{tool} is not connected (or the OAuth wasn't completed). "
                            f"Click Connect and finish the authorization first.")
    from genios_engine.platform import sync_jobs as J
    from genios_engine.platform.audit import record
    queued = J.enqueue(_graph.engine, org_id, [norm]) if _graph is not None else False
    record(org_id, "data_synced", actor_type="user", target_type="source", target_id=norm,
           metadata={"audit_category": "meeting" if norm == "gcal" else "data_extraction",
                     "tool": tool, "mode": "onboarding_backfill"})
    return {"started": True, "tool": tool, "queued": queued, "already_running": not queued}


def _sync_all_bg(org_id: str, sources: list[str], limit: int) -> None:
    """Pull every connected source, then drain L2 — all IN-PROCESS (FastAPI BackgroundTask, no
    Celery/Upstash). Runs AFTER the response is sent so the 'Sync now' button never blocks on the
    (slow) Composio round-trips. One source failing never stops the rest."""
    for st in sources:
        try:
            _sync_source(org_id, st, limit)
        except Exception:      # noqa: BLE001
            _log.exception("sync-all bg: %s failed", st)
    if _graph is not None:
        try:
            _run_l2(org_id)
        except Exception:      # noqa: BLE001
            _log.exception("sync-all bg: L2 drain failed for %s", org_id)


@router.post("/integrations/sync-all")
def integrations_sync_all(background_tasks: BackgroundTasks, limit: int = 25,
                          org_id: str = Depends(get_current_org)) -> dict:
    """Sync EVERY ACTIVE Composio tool for the authed tenant (the 'Sync now' action). Returns
    IMMEDIATELY and runs the whole L1→L2 pull in the background — a calendar/Gmail Composio pull can
    take tens of seconds, so blocking the HTTP response left the button spinning on 'Syncing…'.
    Fresh counts land on the dashboard's next status poll."""
    active = [a for a in _composio_connected(org_id) if a["status"] == "ACTIVE"]
    if not active:
        return {"started": False, "reason": "no connected tools", "tools": []}
    sources = [a["source_type"] for a in active]
    # ENQUEUE a durable job (full 2-month backfill → process → graph → intelligence for every
    # connected tool). A server-side worker runs it and resumes on any restart; the client just
    # reads progress. The unique partial index means a duplicate click doesn't spawn a second job.
    from genios_engine.platform import sync_jobs as J
    queued = J.enqueue(_graph.engine, org_id, sources) if _graph is not None else False
    return {"started": True, "queued": queued, "already_running": not queued, "tools": sources}


# ── real-time webhook (Composio trigger push → L1, no poll) ───────────────────────
@router.post("/webhooks/composio")
async def composio_webhook(request: Request,
                           x_composio_signature: str | None = Header(None),
                           webhook_signature: str | None = Header(None)) -> dict:
    """A Composio trigger delivers a new object → run it through L1 in real time. HMAC-verified:
    an unsigned/forged payload can no longer inject fabricated 'emails' into a tenant's graph."""
    import json as _json
    from genios_engine.platform.auth import verify_webhook_hmac
    raw = await request.body()
    secret = get_settings().composio_webhook_secret
    if secret:
        sig = x_composio_signature or webhook_signature
        if not verify_webhook_hmac(raw, sig, secret):
            raise HTTPException(401, "invalid webhook signature")
    elif get_settings().env != "dev":
        raise HTTPException(403, "webhook secret not configured")   # fail-closed outside dev
    try:
        payload = _json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(422, "invalid JSON body")
    if not isinstance(payload, dict):
        raise HTTPException(422, "webhook body must be a JSON object")
    data = payload.get("data") or payload.get("payload") or payload
    user_id = (payload.get("user_id") or (data.get("user_id") if isinstance(data, dict) else None)
               or payload.get("connected_account_id"))
    conn = next((c for c in _connections.list_active() if c.composio_user_id == user_id), None)
    if conn is None:
        raise HTTPException(404, "no active connection for this user_id")
    from genios_engine.capture.connectors.dispatch import webhook_to_raw
    try:
        raw_obj = webhook_to_raw(conn.source_type, data,
                                 connector_factory=lambda: make_connector_for(conn))
    except Exception:                                    # a foreign/bad payload must never 500 the webhook
        _log.exception("webhook parse failed org=%s source=%s", conn.org_id, conn.source_type)
        raw_obj = None
    if raw_obj is None:
        return {"ingested": False, "reason": "unmapped payload", "source": conn.source_type}
    res = capture_event(raw_obj, org_id=conn.org_id, connection_id=conn.connection_id,
                        repo=_repo, trace_repo=_trace_repo, payload_store=_payload_store,
                        document_job_store=_documents)
    return {"ingested": True, "outcome": res.outcome, "event_id": res.event.event_id}


# ── L2 context graph ─────────────────────────────────────────────────────────────
@router.post("/context/process")
def context_process(limit: int = 50, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """L1→L2 handoff for the authed tenant (org from credential — an unauthenticated caller can
    no longer trigger Haiku spend). limit clamped so it can't be driven unbounded."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured (needs DATABASE_URL)")
    org_id = ctx.org_id
    limit = max(1, min(int(limit), 200))
    from genios_engine.context.runner import process_pending
    # NOTE: process_pending's cap arg is max_total (there is no `limit=` param — passing one raised
    # TypeError and 500'd this endpoint). Clamp the manual drain to `limit`.
    return process_pending(org_id=org_id, store=_graph, llm=_llm,
                           crypto_key=get_settings().crypto_key, max_total=limit)


@router.post("/context/reason")
def context_reason(ctx: AuthCtx = Depends(require_owner)) -> dict:
    """L3: evaluate deterministic rules over the authed tenant's graph → scored signals (no LLM)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    org_id = ctx.org_id
    from genios_engine.reason.runner import run_all as run_l3
    return run_l3(org_id=org_id, store=_graph, registry=_registry)


@router.post("/context/sweep")
def context_sweep(_internal: None = Depends(require_internal)) -> dict:
    """Daily cron: re-evaluate L3 over EVERY org's graph so time-based crossings fire with no new
    event. Internal-only (x-internal-token). Idempotent (cooldown blocks duplicates)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    from genios_engine.reason.runner import run_all as run_l3
    with _graph.engine.connect() as c:
        orgs = [r[0] for r in c.execute(text("select org_id from graph_versions"))]
    return {"orgs": len(orgs),
            "results": {o: run_l3(org_id=o, store=_graph, registry=_registry)["outcomes"]
                        for o in orgs}}


@router.get("/context/signals")
def context_signals(status: str = "open", org_id: str = Depends(get_current_org)) -> dict:
    """The L3 output — ranked signals. org_id is derived from the credential (tenant isolation)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        if status == "open":
            from genios_engine.reason.authority import (
                AUTHORITATIVE_REASON_CODE_SQL,
                AUTHORITATIVE_SCORE_INPUTS_SQL,
                AUTHORITATIVE_SCORE_SQL,
                AUTHORITATIVE_SIGNAL_JOINS,
                AUTHORITATIVE_SIGNAL_PREDICATE,
                authority_time,
            )
            rows = c.execute(text(
                "select s.signal_id, regexp_replace(rr.capability_id, '^.*\\.', '') "
                "as rule_id, s.subject_node_id, " + AUTHORITATIVE_SCORE_SQL + " as score, "
                + AUTHORITATIVE_REASON_CODE_SQL + " as reason_code, "
                "selected_rc.play_id as play, " + AUTHORITATIVE_SCORE_INPUTS_SQL +
                " as score_inputs, selected_rc.evidence_refs as evidence "
                "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
                " where s.org_id=:o and s.status='open' and " +
                AUTHORITATIVE_SIGNAL_PREDICATE +
                " order by selected_rc.final_utility_bp desc, s.signal_id"),
                {"o": org_id, "authority_time": authority_time()}).fetchall()
        else:
            rows = c.execute(text(
                "select signal_id, rule_id, subject_node_id, score, reason_code, play, "
                "score_inputs, evidence from signals where org_id=:o and status=:s "
                "order by score desc"), {"o": org_id, "s": status}).fetchall()
    return {"signals": [dict(r._mapping) for r in rows]}


@router.get("/context/read-models/{model_type}/{entity_id}")
def context_read_model(model_type: str, entity_id: str,
                       org_id: str = Depends(get_current_org)) -> dict:
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        r = c.execute(text("select payload, graph_version from context_read_models "
                           "where org_id=:o and model_type=:mt and entity_id=:e"),
                      {"o": org_id, "mt": model_type, "e": entity_id}).first()
    if r is None:
        raise HTTPException(404, "read model not found")
    return {"model_type": model_type, "entity_id": entity_id,
            "graph_version": r.graph_version, "payload": r.payload}


# ── L2 graph views (for the dashboard graph/context pages) ─────────────────────────
def _days_since_iso(v, now) -> int:
    from datetime import datetime as _dt
    try:
        t = _dt.fromisoformat(str(v).strip('"').replace("Z", "+00:00"))
        return max(0, int((now - t).total_seconds() // 86400))
    except (ValueError, TypeError):
        return 999


@router.get("/graph")
def graph_data(org_id: str = Depends(get_current_org)) -> dict:
    """The tenant's context graph — nodes (people/companies/deals/meetings) + edges + type counts.
    What the dashboard graph view renders; a node click drills into its facts via read-models."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from collections import Counter
    from datetime import datetime, timezone
    from sqlalchemy import text
    now = datetime.now(timezone.utc)
    with _graph.engine.connect() as c:
        nodes = c.execute(text("select node_id, node_type, display_name, canonical_key "
                               "from graph_nodes where org_id=:o and valid_to is null"),
                          {"o": org_id}).fetchall()
        edges = c.execute(text("select from_node_id, to_node_id, edge_type, confidence "
                               "from graph_edges where org_id=:o"), {"o": org_id}).fetchall()
        last_in = {r.subject_node_id: r.value for r in c.execute(text(
            "select subject_node_id, value from graph_facts where org_id=:o "
            "and field='thread.last_inbound' and valid_to is null and status='active'"),
            {"o": org_id})}
    node_list = [{"id": n.node_id, "name": n.display_name, "type": n.node_type,
                  "email": n.canonical_key if n.node_type == "person" else None,
                  "last_interaction_days": _days_since_iso(last_in.get(n.node_id), now)}
                 for n in nodes]
    links = [{"source": e.from_node_id, "target": e.to_node_id, "type": e.edge_type,
              "weight": float(e.confidence)} for e in edges]
    tools = sorted({c.source_type for c in _connections.list_active() if c.org_id == org_id})
    return {"nodes": node_list, "links": links,
            "entity_type_counts": dict(Counter(n["type"] for n in node_list)),
            "communities": [], "connected_tools": tools}


@router.get("/graph/node/{node_id}")
def graph_node_detail(node_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """One node's full detail for the graph side-panel: its facts + who/what it is connected to
    (a meeting's attendees, the meetings a person attended, a deal's champion…). Computed LIVE from
    the graph so it works for every node — not only ones that happen to have a pre-built read model."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text

    def _clean(v):
        return v.strip('"') if isinstance(v, str) else v

    with _graph.engine.connect() as c:
        node = c.execute(text(
            "select node_id, node_type, display_name, canonical_key, identity_strength "
            "from graph_nodes where org_id=:o and node_id=:n and valid_to is null limit 1"),
            {"o": org_id, "n": node_id}).first()
        if node is None:
            raise HTTPException(404, "node not found")
        facts = c.execute(text(
            "select field, value, confidence, authority_rank, occurred_at from graph_facts "
            "where org_id=:o and subject_node_id=:n and valid_to is null and status='active' "
            "order by occurred_at desc nulls last"), {"o": org_id, "n": node_id}).fetchall()
        out_edges = c.execute(text(
            "select e.edge_type, e.confidence, e.to_node_id as other_id, "
            "  o.display_name as other_name, o.node_type as other_type "
            "from graph_edges e join graph_nodes o on o.node_id=e.to_node_id and o.org_id=e.org_id "
            "where e.org_id=:o and e.valid_to is null and e.from_node_id=:n"),
            {"o": org_id, "n": node_id}).fetchall()
        in_edges = c.execute(text(
            "select e.edge_type, e.confidence, e.from_node_id as other_id, "
            "  o.display_name as other_name, o.node_type as other_type "
            "from graph_edges e join graph_nodes o on o.node_id=e.from_node_id and o.org_id=e.org_id "
            "where e.org_id=:o and e.valid_to is null and e.to_node_id=:n"),
            {"o": org_id, "n": node_id}).fetchall()
        obs = c.execute(text(
            "select kind, occurred_at from graph_observations where org_id=:o "
            "and subject_node_id=:n and status='active' order by occurred_at desc limit 20"),
            {"o": org_id, "n": node_id}).fetchall()

    rels = ([{"edge_type": r.edge_type, "direction": "out", "other_id": r.other_id,
              "other_name": r.other_name, "other_type": r.other_type, "confidence": float(r.confidence)}
             for r in out_edges] +
            [{"edge_type": r.edge_type, "direction": "in", "other_id": r.other_id,
              "other_name": r.other_name, "other_type": r.other_type, "confidence": float(r.confidence)}
             for r in in_edges])
    return {
        "id": node.node_id, "name": node.display_name, "type": node.node_type,
        "email": node.canonical_key if node.node_type == "person" else None,
        "identity_strength": node.identity_strength,
        "facts": [{"field": f.field, "value": _clean(f.value), "confidence": float(f.confidence),
                   "authority": f.authority_rank,
                   "occurred_at": f.occurred_at.isoformat() if f.occurred_at else None}
                  for f in facts],
        "relationships": rels,
        "observations": [{"kind": o.kind, "at": o.occurred_at.isoformat() if o.occurred_at else None}
                         for o in obs],
    }


@router.get("/graph/stats")
def graph_stats(org_id: str = Depends(get_current_org)) -> dict:
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        n = c.execute(text("select count(*) from graph_nodes where org_id=:o and valid_to is null"),
                      {"o": org_id}).scalar()
        e = c.execute(text("select count(*) from graph_edges where org_id=:o"), {"o": org_id}).scalar()
    return {"ready": bool(n), "total_nodes": int(n or 0), "total_edges": int(e or 0),
            "last_sync": "", "quality_score": 0}


@router.get("/contacts")
def contacts(limit: int = 100, offset: int = 0, org_id: str = Depends(get_current_org)) -> dict:
    """People + companies in the graph (the dashboard contacts list)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    limit = max(1, min(int(limit), 500))
    with _graph.engine.connect() as c:
        rows = c.execute(text("select node_id, node_type, display_name, canonical_key "
                              "from graph_nodes where org_id=:o and valid_to is null "
                              "and node_type in ('person','company') order by display_name "
                              "limit :l offset :off"),
                         {"o": org_id, "l": limit, "off": offset}).fetchall()
        total = c.execute(text("select count(*) from graph_nodes where org_id=:o and valid_to is null "
                               "and node_type in ('person','company')"), {"o": org_id}).scalar()
    return {"contacts": [{"id": r.node_id, "name": r.display_name, "email": r.canonical_key,
                          "company": None, "entity_type": r.node_type} for r in rows],
            "total": int(total or 0)}


@router.get("/dashboard/metrics")
def dashboard_metrics(org_id: str = Depends(get_current_org)) -> dict:
    """Headline counts for the dashboard 'What your brain knows' card — real graph state:
    entities (nodes), facts, and relationships (edges). org from the JWT."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        entities = int(c.execute(text("select count(*) from graph_nodes where org_id=:o "
                                      "and valid_to is null"), {"o": org_id}).scalar() or 0)
        facts = int(c.execute(text("select count(*) from graph_facts where org_id=:o "
                                   "and valid_to is null and status='active'"), {"o": org_id}).scalar() or 0)
        rels = int(c.execute(text("select count(*) from graph_edges where org_id=:o "
                                  "and valid_to is null"), {"o": org_id}).scalar() or 0)
        signals = int(c.execute(text("select count(*) from signals where org_id=:o "
                                     "and status='open'"), {"o": org_id}).scalar() or 0)
        # inputs for a REAL graph-health score (not a hardcoded 0):
        connected = int(c.execute(text(
            "select count(distinct nid) from ("
            "  select from_node_id nid from graph_edges where org_id=:o and valid_to is null "
            "  union select to_node_id from graph_edges where org_id=:o and valid_to is null) x"),
            {"o": org_id}).scalar() or 0)
        nodes_with_fact = int(c.execute(text("select count(distinct subject_node_id) from graph_facts "
                                             "where org_id=:o and valid_to is null and status='active'"),
                                        {"o": org_id}).scalar() or 0)
        avg_conf = float(c.execute(text("select coalesce(avg(confidence),0) from graph_facts where "
                                        "org_id=:o and valid_to is null and status='active'"),
                                   {"o": org_id}).scalar() or 0)
        plan = c.execute(text("select plan_status from orgs where id=:o"), {"o": org_id}).scalar()
    # Graph health 0-1: 40% how connected the graph is, 25% how many entities carry facts,
    # 35% average fact confidence. A well-linked, fact-rich, confident graph → high "Brain" score.
    if entities > 0:
        connectivity = min(1.0, connected / entities)
        coverage = min(1.0, nodes_with_fact / entities)
        quality = round(0.40 * connectivity + 0.25 * coverage + 0.35 * avg_conf, 3)
    else:
        quality = 0.0
    return {"contacts_count": entities, "interactions_count": facts,
            "active_relationships_count": rels, "signals_count": signals,
            "graph_quality_score": quality, "aer": 0, "time_saved_hours": 0,
            "context_calls_today": 0, "context_calls_limit": 3000, "plan": plan or "trial",
            "aer_trend": [], "brain_trend": [], "time_trend": [], "calls_trend": []}


@router.get("/activity")
def activity_feed(limit: int = 20, org_id: str = Depends(get_current_org)) -> dict:
    """Recent brain activity for the dashboard home widget — merges new decisions (cards) and new/
    updated entities (graph nodes), newest first. Honest by construction: an empty graph returns an
    empty feed (no fabricated events). org from the JWT (the ?org_id query param is ignored)."""
    if _graph is None:
        return {"events": []}
    from sqlalchemy import text
    limit = max(1, min(int(limit), 100))
    events: list[dict] = []
    with _graph.engine.connect() as c:
        for r in c.execute(text(
                "select headline, situation, urgency_band, created_at from cards "
                "where org_id=:o order by created_at desc limit :l"), {"o": org_id, "l": limit}):
            events.append({
                "event_type": "insight_generated",
                "event_data": {"title": r.headline, "detail": r.situation, "badge_label": r.urgency_band},
                "created_at": r.created_at.isoformat() if r.created_at else "",
            })
        for r in c.execute(text(
                "select display_name, node_type, version, valid_from from graph_nodes "
                "where org_id=:o and valid_to is null and node_type in ('person','company') "
                "and display_name is not null order by valid_from desc limit :l"),
                {"o": org_id, "l": limit}):
            created = (r.version or 1) == 1
            events.append({
                "event_type": "contact_created" if created else "contact_updated",
                "event_data": {"contact_name": r.display_name,
                               "detail": f"{'New' if created else 'Updated'} {r.node_type} in your graph"},
                "created_at": r.valid_from.isoformat() if r.valid_from else "",
            })
    events.sort(key=lambda e: e["created_at"], reverse=True)   # ISO strings sort chronologically
    return {"events": events[:limit]}


# Pricing lives in platform.metrics so the tenant-facing usage endpoints below and the cross-org
# admin console quote the SAME dollar figure for the same tokens (ANALYTICS_V3_PLAN §1).
from genios_engine.platform.metrics import llm_price as _llm_price          # noqa: E402


@router.get("/v1/usage/llm/summary")
def llm_usage_summary(org_id: str = Depends(get_current_org)) -> dict:
    """Token + USD spend over 24h / 7d / 30d, computed from the llm_costs ledger. Cost is derived
    from tokens × model list price (the ledger stores tokens, not dollars)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text
    now = datetime.now(timezone.utc)

    def _window(c, since) -> dict:
        rows = c.execute(text("select model, sum(input_tokens) it, sum(output_tokens) ot, count(*) n "
                              "from llm_costs where org_id=:o and created_at >= :s group by model"),
                         {"o": org_id, "s": since}).fetchall()
        calls = toks = 0
        cost = 0.0
        for r in rows:
            pi, po = _llm_price(r.model)
            it, ot = int(r.it or 0), int(r.ot or 0)
            calls += int(r.n); toks += it + ot; cost += it * pi + ot * po
        return {"calls": calls, "tokens": toks, "cost_usd": round(cost, 6), "credits_billed": 0}

    with _graph.engine.connect() as c:
        return {"window_24h": _window(c, now - timedelta(hours=24)),
                "window_7d": _window(c, now - timedelta(days=7)),
                "window_30d": _window(c, now - timedelta(days=30))}


@router.get("/v1/usage/llm/breakdown")
def llm_usage_breakdown(days: int = 7, org_id: str = Depends(get_current_org)) -> dict:
    """Per-purpose × per-model spend over the last `days` — 'did extraction or reasoning eat the budget?'"""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text
    days = max(1, min(int(days), 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select purpose, model, sum(input_tokens) it, sum(output_tokens) ot, count(*) n "
            "from llm_costs where org_id=:o and created_at >= :s group by purpose, model "
            "order by n desc"), {"o": org_id, "s": since}).fetchall()
    out = []
    for r in rows:
        pi, po = _llm_price(r.model)
        it, ot = int(r.it or 0), int(r.ot or 0)
        out.append({"purpose": r.purpose, "model": r.model, "calls": int(r.n),
                    "input_tokens": it, "output_tokens": ot,
                    "cost_usd": round(it * pi + ot * po, 6), "credits_billed": 0})
    return {"window_days": days, "rows": out}


@router.get("/v1/metrics/intervention_rate/summary")
def intervention_rate_summary(on_date: str | None = None,
                              org_id: str = Depends(get_current_org)) -> dict:
    """Per-module intervention rate. Empty until decisions are emitted + corrections recorded
    (an L6 rollup) — the dashboard shows a 'no rollups yet' state, not an error."""
    return {}


@router.get("/v1/metrics/headline")
def metrics_headline(org_id: str = Depends(get_current_org)) -> dict:
    """Headline engine metrics. Empty maps until the intelligence query loop starts producing
    decisions — returned as a valid (zero) shape so the dashboard degrades gracefully."""
    return {"date": "", "intervention_rate_by_module": {}, "latest_roi_by_module": {},
            "latest_symbolic_resolution_rate_by_module": {}}


@router.get("/context/overview")
def context_overview(org_id: str = Depends(get_current_org)) -> dict:
    """Context page health cards — fact totals + avg confidence + recent graph changes.
    conflictsDetected is the REAL open-discrepancy count (was hardcoded 0 while the
    conflict detector ran and wrote rows nobody read)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        row = c.execute(text("select count(*) n, coalesce(avg(confidence),0) a from graph_facts "
                             "where org_id=:o and valid_to is null and status='active'"),
                        {"o": org_id}).first()
        conflicts = c.execute(text(
            "select count(*) from discrepancies where org_id=:o and status='open'"),
            {"o": org_id}).scalar()
        recent = c.execute(text("select field, subject_node_id, created_at from graph_facts "
                                "where org_id=:o and valid_to is null order by created_at desc "
                                "limit 10"), {"o": org_id}).fetchall()
    return {"healthCards": {"totalFacts": int(row.n), "avgConfidence": round(float(row.a), 3),
                            "factsDecaying": 0, "conflictsDetected": int(conflicts or 0)},
            "recentEvents": [{"eventType": r.field, "eventData": {"node": r.subject_node_id},
                              "createdAt": r.created_at.isoformat() if r.created_at else ""}
                             for r in recent]}


@router.get("/context/discrepancies")
def context_discrepancies(limit: int = 50, org_id: str = Depends(get_current_org)) -> dict:
    """Open conflicts: a lower-authority source disagreed with the held value (e.g. an
    email says unpaid, Stripe says paid). The detector always wrote these; this is the
    first surface that reads them. The flag is product — 'which one is true?' is a card."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    limit = max(1, min(int(limit), 200))
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select d.id, d.subject_node_id, d.field, d.held, d.challenger, d.created_at, "
            "n.display_name from discrepancies d "
            "left join graph_nodes n on n.node_id=d.subject_node_id and n.org_id=d.org_id "
            "and n.valid_to is null "
            "where d.org_id=:o and d.status='open' order by d.created_at desc limit :l"),
            {"o": org_id, "l": limit}).fetchall()
    import json as _json

    def _j(v):
        return v if isinstance(v, dict) else (_json.loads(v) if v else {})
    return {"discrepancies": [
        {"id": r.id, "entity": r.display_name, "entity_id": r.subject_node_id,
         "field": r.field, "held": _j(r.held), "challenger": _j(r.challenger),
         "detected_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows]}


def _stage_from_age(last_at, now) -> str:
    """Deterministic relationship stage from the last real activity. Honest bands:
    <14d active · 14–45d cooling · >45d dormant · never → new."""
    if last_at is None:
        return "new"
    if last_at.tzinfo is None:
        from datetime import timezone as _tz
        last_at = last_at.replace(tzinfo=_tz.utc)
    age_d = (now - last_at).total_seconds() / 86400.0
    return "active" if age_d < 14 else ("cooling" if age_d <= 45 else "dormant")


@router.get("/context/facts")
def context_facts(limit: int = 100, offset: int = 0,
                  org_id: str = Depends(get_current_org)) -> dict:
    """Per-entity fact summary (the Context 'Facts' tab). Every number is REAL or null —
    this endpoint used to ship invented constants (stage 'active' for everyone,
    freshness 1.0, consistency 1.0, sentiment 0), which is a trust liability on the one
    page that exists to show what the twin knows. Ordered by attention when present."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from datetime import datetime, timezone

    from sqlalchemy import text
    limit = max(1, min(int(limit), 500))
    now = datetime.now(timezone.utc)
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select n.node_id, n.node_type, n.display_name, n.canonical_key, "
            "count(f.fact_version_id) fc, coalesce(avg(f.confidence),0) conf, "
            "coalesce(max(f.authority_rank),1) auth, max(f.occurred_at) last_at, "
            "a.score as attention_score, a.band as attention_band "
            "from graph_nodes n "
            "left join graph_facts f on f.subject_node_id=n.node_id "
            "and f.org_id=n.org_id and f.valid_to is null and f.status='active' "
            "left join context_attention a on a.node_id=n.node_id and a.org_id=n.org_id "
            "where n.org_id=:o and n.valid_to is null "
            "group by n.node_id, n.node_type, n.display_name, n.canonical_key, a.score, a.band "
            "order by a.score desc nulls last, last_at desc nulls last, fc desc "
            "limit :l offset :off"),
            {"o": org_id, "l": limit, "off": offset}).fetchall()
        total = c.execute(text("select count(*) from graph_nodes where org_id=:o and valid_to is null"),
                          {"o": org_id}).scalar()
    facts = [{"id": r.node_id, "entity": r.display_name,
              "email": r.canonical_key if r.node_type == "person" else None, "company": None,
              "entity_type": r.node_type,
              "relationship_stage": _stage_from_age(r.last_at, now),
              "freshness": None,                       # honest: not computed yet
              "confidence": round(float(r.conf), 3),
              "consistency": None,                     # honest: not computed yet
              "authority": int(r.auth),
              "context": round(float(r.conf), 3),
              "attention": int(r.attention_score) if r.attention_score is not None else None,
              "attention_band": r.attention_band,
              "last_confirmed": r.last_at.isoformat() if r.last_at else None,
              "interaction_count": int(r.fc), "sentiment_avg": None, "topics": []}
             for r in rows]
    return {"facts": facts, "total": int(total or 0)}


@router.get("/context/commitments")
def context_commitments(org_id: str = Depends(get_current_org)) -> dict:
    """Open commitments (commitment.due_at facts) with the entity they belong to."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select f.subject_node_id, f.value, f.occurred_at, n.display_name from graph_facts f "
            "join graph_nodes n on n.node_id=f.subject_node_id and n.org_id=f.org_id "
            "and n.valid_to is null where f.org_id=:o and f.field='commitment.due_at' "
            "and f.valid_to is null and f.status='active' order by f.occurred_at desc limit 100"),
            {"o": org_id}).fetchall()
    return {"commitments": [{"id": r.subject_node_id, "entity": r.display_name,
                             "due_at": str(r.value).strip('"'),
                             "created_at": r.occurred_at.isoformat() if r.occurred_at else None}
                            for r in rows]}


@router.get("/context/lifecycle")
def context_lifecycle(limit: int = 50, org_id: str = Depends(get_current_org)) -> dict:
    """Recent fact-version transitions — the graph's activity feed. Each row is a HUMAN-READABLE
    event: what was learned/updated, about which entity, and when (latest first)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from sqlalchemy import text
    limit = max(1, min(int(limit), 200))
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select f.field, f.status, f.created_at, f.occurred_at, n.display_name, n.node_type "
            "from graph_facts f join graph_nodes n on n.node_id=f.subject_node_id and n.org_id=f.org_id "
            "and n.valid_to is null where f.org_id=:o order by f.created_at desc nulls last limit :l"),
            {"o": org_id, "l": limit}).fetchall()
    events = []
    for r in rows:
        verb = "learned" if r.status == "active" else ("updated" if r.status == "superseded" else r.status)
        field_label = (r.field or "fact").split(".")[-1].replace("_", " ")
        when = r.created_at or r.occurred_at
        events.append({
            "event_type": verb,                                   # learned | updated
            "entity": r.display_name, "entity_type": r.node_type,
            "field": field_label,
            "description": f"{field_label.capitalize()} {verb} · {r.display_name}",
            "at": when.isoformat() if when else "",
        })
    return {"events": events}


# ── human / agent events ─────────────────────────────────────────────────────────
@router.post("/human-events")
def human_event(ev: HumanEvent, ctx: AuthCtx = Depends(require_owner)) -> dict:
    if not ev.is_known_type():
        raise HTTPException(422, f"unknown human event type: {ev.type}")
    org_id = ctx.org_id
    ev.org_id = org_id                  # bind tenant + actor to the owner credential
    ev.actor_id = ctx.actor_id or "org_owner"
    _human_events.add(ev)               # the correction ledger (kept — audit/undo reads it)
    # ONE DOOR: the event also enters the graph's world as a SourceEvent, so L2 actually
    # learns what the human said (before: side table only, the twin never saw it).
    from genios_engine.capture.intake import ingest_human_event
    res = ingest_human_event(ev, repo=_repo, payload_store=_payload_store,
                             prepared_store=_prepared_store, trace_repo=_trace_repo)
    return {"accepted": True, "type": ev.type, "event_id": res.event.event_id,
            "outcome": res.outcome}


class RegisterAgent(BaseModel):
    agent_id: str
    key: str                            # raw key; only its hash is stored
    allowed_actions: list[str]


@router.post("/agents/register")
def register_agent(body: RegisterAgent, ctx: AuthCtx = Depends(require_owner)) -> dict:
    # Only an authenticated tenant (owner session) may mint an agent for ITS OWN org. A grant may
    # be an L1 outcome action OR an L5 Agent-API scope (§5.16) — a key can carry either.
    org_id = ctx.org_id
    allowed = AGENT_ACTIONS | AGENT_API_SCOPES | HUMAN_API_SCOPES
    bad = [a for a in body.allowed_actions if a not in allowed]
    if bad:
        raise HTTPException(422, f"unknown actions/scopes: {bad}")
    _agent_registry.register(org_id, body.agent_id, body.key, body.allowed_actions)
    return {"registered": True, "agent_id": body.agent_id, "allowed_actions": body.allowed_actions}


@router.post("/agent-events")
def agent_event(ev: AgentEvent, x_agent_key: str = Header(...)) -> dict:
    if ev.action_taken not in AGENT_ACTIONS:
        raise HTTPException(422, f"unknown action_taken: {ev.action_taken}")
    if not _agent_registry.verify(ev.org_id, ev.agent_id, x_agent_key, ev.action_taken):
        raise HTTPException(401, "agent key invalid or action not allowed for this agent")
    is_new = _agent_events.add(ev)      # the outcome ledger (kept — idempotency reads it)
    # ONE DOOR: the agent's completed action becomes a SourceEvent too, so GeniOS never
    # recommends what an agent already did. Dedup rides the agent's idempotency key.
    from genios_engine.capture.intake import ingest_agent_event
    res = ingest_agent_event(ev, repo=_repo, payload_store=_payload_store,
                             prepared_store=_prepared_store, trace_repo=_trace_repo)
    return {"accepted": True, "duplicate": not is_new, "action": ev.action_taken,
            "event_id": res.event.event_id, "outcome": res.outcome}


# ── L5 delivery · cards ───────────────────────────────────────────────────────────
def _require_l5():
    if _card_store is None or _graph is None:
        raise HTTPException(400, "delivery store not configured (needs DATABASE_URL)")


def _owns_card(card_id: str, org_id: str) -> dict:
    """Fetch a card and assert it belongs to the authenticated org (no cross-tenant access)."""
    card = _card_store.get_card(card_id)
    if card is None or card["org_id"] != org_id:
        raise HTTPException(404, "card not found")
    return card


# Relationship signals worth surfacing on a card (skip bookkeeping/noise kinds like mention:*,
# email_relevance, email_noise:*). Maps the raw obs kind → a human label.
_CONTEXT_OBS: dict[str, str] = {
    "meeting_request": "Meeting proposed",
    "next_step_agreed": "Next step agreed",
    "question": "Open question",
    "introduction": "Intro thread",
    "proposal_sent": "Proposal sent",
    "demo_requested": "Demo requested",
    "objection": "Objection raised",
    "contract_requested": "Contract requested",
    "pricing_discussed": "Pricing discussed",
    "positive_reply": "Positive reply",
    "timeline_slip": "Timeline slipping",
    "closed_lost_mention": "At-risk mention",
    "budget_approved": "Budget approved",
    "verbal_yes": "Verbal yes",
    "champion_change": "Champion changed",
}
# Facts already shown in the card's subject line / why rows, or redundant/noisy for a card —
# don't repeat them under Context (the date is in the subject line; title repeats the headline).
_CONTEXT_FACT_SKIP = frozenset({"thread.ball_in_court", "thread.last_inbound", "thread.last_outbound",
                                "thread.last_seen", "meeting.status", "meeting.start_at",
                                "meeting.end_at", "end_at", "meeting.title", "title"})


# Observation kinds that ground WHAT the counterparty is asking for — the "expectation" half of the
# clarity gate. If none of these are on record for an unanswered thread, we know they wrote but not
# what response they need, so the card must fail closed.
_ASK_SIGNALS = frozenset({"question", "meeting_request", "proposal_sent", "demo_requested",
                          "contract_requested", "objection", "next_step_agreed"})


def _actionability(reason_code: str | None, obs_kinds: set, fact_fields: set) -> dict:
    """Update 1 — the universal zero-clarity gate. A card may carry a confident action imperative
    ('reply now', 'deliver the commitment') ONLY when the decisive context for its type is grounded.
    When the action-critical fact is missing, fail closed: switch to a context-recovery outcome so
    the card says 'review the source' instead of inventing confidence. Deterministic, no LLM."""
    if reason_code == "unanswered_email":
        if obs_kinds & _ASK_SIGNALS:
            return {"state": "actionable"}
        return {"state": "context_incomplete", "missing": ["what response they need"],
                "message": "We verified they wrote and the ball is on you — but not what response they need.",
                "recommended": "Open the email to see what they're actually asking before replying."}
    if reason_code == "commitment_overdue":
        if "commitment.action" in fact_fields:
            return {"state": "actionable"}
        return {"state": "context_incomplete", "missing": ["the promised outcome"],
                "message": "We found a due date, but not what was actually promised.",
                "recommended": "Open the source thread to verify what you committed to before acting."}
    if reason_code == "meeting_no_followup":
        if "meeting.description" in fact_fields:
            return {"state": "actionable"}
        return {"state": "context_incomplete", "missing": ["what to recap"],
                "message": "A meeting ended with no follow-up, but we don't have its agenda on record.",
                "recommended": "Open the calendar event to see what was discussed before sending a recap."}
    return {"state": "actionable"}


# Per-ask-signal step text — the concrete next move the recommendation should propose.
_ASK_STEP: dict[str, str] = {
    "question": "Answer their open question",
    "meeting_request": "Confirm or decline the proposed meeting",
    "proposal_sent": "Respond to their proposal",
    "demo_requested": "Book the demo they asked for",
    "contract_requested": "Send the contract they requested",
    "objection": "Address the objection they raised",
    "next_step_agreed": "Deliver the agreed next step",
}
# Every CTA carries ONE documented server-side effect (Update 1 §9.5). Opening/handling never
# completes the loop; completion is an explicit, evidence-backed transition.
_ACTION_EFFECT: dict[str, str] = {
    "run_play": "draft_only",       # opens grounded steps / a draft; does not send or execute
    "do_it_myself": "claim_only",   # claims ownership; does NOT mark the work complete
    "snooze": "defer_surface",      # defers delivery to a chosen time; decision unchanged
    "wrong": "feedback",            # records structured feedback, suppresses per policy
    "open_source": "none",          # read-only navigation
}


def _annotate_effects(actions):
    """Attach the documented server-side effect to each CTA so the surface can label transitions
    honestly ('I'll handle this' = claim only, never complete)."""
    out = []
    for a in actions or []:
        a = dict(a)
        a["effect"] = _ACTION_EFFECT.get(a.get("type"), "none")
        out.append(a)
    return out


def _confidence_block(facts: dict, score_block: dict, actionable: bool) -> dict:
    """Separate confidence meanings (Update 1): evidence vs identity vs situation vs recommendation.
    These are DIFFERENT quantities and must never collapse into one number."""
    evidence = int((score_block or {}).get("C") or 0)
    identity = 85 if ("company" in facts or "role" in facts) else 30
    situation = 80 if (facts.get("thread.last_inbound") or facts.get("commitment.due_at")
                       or facts.get("meeting.description")) else 50
    return {"evidence": evidence, "identity": identity, "situation": situation,
            "recommendation": evidence if actionable else 10}


def _decision_projection(reason_code, card, facts, obs_kinds, actionability) -> dict:
    """card.v2 decision projection — the typed, grounding-aware read model. Deterministic, no LLM,
    no new reasoning: it only shapes what Layers 1-5 already produced. Fields we cannot ground
    (request text, promised outcome, cost-of-inaction, completion criteria) stay `missing` rather
    than being invented — that gap closes when source bodies are captured (Level 2)."""
    actionable = actionability.get("state") == "actionable"
    if not actionable:
        rec = {"verdict": "review_source",
               "objective": "Verify what's actually needed before acting",
               "steps": [actionability.get("recommended") or "Open the source and review the request"],
               "avoid": "Don't reply, deliver, or mark done until the request is verified"}
    elif reason_code == "unanswered_email":
        steps = [_ASK_STEP[k] for k in _ASK_STEP if k in obs_kinds][:3]
        rec = {"verdict": "reply", "objective": "Reply to what they actually asked",
               "steps": steps or ["Reply in the thread"],
               "avoid": "Don't send a generic acknowledgement"}
    elif reason_code == "commitment_overdue":
        act = facts.get("commitment.action")
        rec = {"verdict": "deliver",
               "objective": f"Close this loop — “{act}”" if act else "Deliver the commitment",
               "steps": ["Reply in the thread to resolve it"] if act else ["Confirm completion in the thread"],
               "avoid": "Don't mark done until it's actually resolved"}
    elif reason_code == "meeting_no_followup":
        rec = {"verdict": "follow_up", "objective": "Send a recap of the meeting",
               "steps": ["Recap the key points discussed", "State the next step and who owns it"],
               "avoid": "Don't recap to yourself or a group with no external counterparty"}
    else:
        rec = {"verdict": reason_code or "review", "objective": (card.get("situation") or "").strip(),
               "steps": [], "avoid": None}

    def gs(cond):
        return "grounded" if cond else "missing"

    grounding = {
        "situation": "grounded",
        "request": gs(reason_code == "unanswered_email" and bool(obs_kinds & _ASK_SIGNALS)),
        "obligation": gs(reason_code == "commitment_overdue" and "commitment.action" in facts),
        "stakes": "missing",       # cost-of-inaction / business consequence not captured yet
        "completion": "missing",   # observable completion criteria not captured yet
    }
    return {"card_version": "card.v2", "recommendation": rec,
            "confidence": _confidence_block(facts, card.get("score_block") or {}, actionable),
            "grounding": grounding}


# Known networking-connector bots — the transport sender is never the business subject (Update 4).
_BOT_DOMAINS = frozenset({"boardy.ai"})


def _is_connector(canonical_key: str | None, obs_counts: dict) -> bool:
    """Update 4 — detect an introduction connector / bot that many separate threads collapse onto, so
    the card never treats the intermediary as the person to reply to. Two signals: a known bot domain,
    or an automated sender that has accumulated many introductions/meeting-requests across threads
    (§20's 'connector node with many intro/meeting observations but no person-specific loop' detector)."""
    key = (canonical_key or "").lower()
    domain = key.rsplit("@", 1)[-1] if "@" in key else ""
    if domain in _BOT_DOMAINS:
        return True
    if obs_counts.get("email_noise:automated", 0) >= 1 and (
            obs_counts.get("introduction", 0) >= 3 or obs_counts.get("meeting_request", 0) >= 5):
        return True
    return False


def _connector_gate(canonical_key: str | None) -> dict:
    """Fail-closed actionability for a connector subject: point the user at the real contacts instead
    of confidently telling them to reply to the bot."""
    who = canonical_key or "This sender"
    return {"state": "context_incomplete", "connector": True,
            "missing": ["the actual person to reply to"],
            "message": f"{who} is an introduction connector — many separate intros are collapsed "
                       "here, so this is not one person to reply to.",
            "recommended": "Open Gmail and reply to each introduced contact in their own thread; "
                           "don't reply to the connector."}


def _meeting_lifecycle(status, start_raw, now) -> tuple[str, str]:
    """Reconcile a meeting's honest lifecycle state (Update 3 §4/§9.6). A past scheduled event proves
    it was SCHEDULED, not HELD — 'held' needs attendance/transcript/follow-up evidence we don't have,
    so we say 'occurrence unverified' rather than inventing that it happened."""
    from datetime import datetime, timezone
    if status == "cancelled":
        return "cancelled", "Cancelled"
    start = None
    if isinstance(start_raw, str):
        try:
            start = datetime.fromisoformat(start_raw)
        except ValueError:
            start = None
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start is None or start > now:
        return "scheduled", "Scheduled"
    return "past_scheduled", "Past scheduled · occurrence unverified"


def _commitment_neighbors(c, org_id: str, node_id: str) -> list[dict]:
    """One-hop traversal to the person's connected commitment nodes. The promised text is extracted
    and stored on the commitment node (e.g. 'Let's speak coming Monday 11am-1pm?'), but the card was
    node-local and only saw the person's due-date — so it said 'context incomplete'. Reading the
    commitment node recovers the actual promise, no re-capture needed."""
    from sqlalchemy import text
    rows = c.execute(text(
        "select distinct m.node_id from graph_edges e "
        "join graph_nodes m on m.org_id=e.org_id and m.node_id = "
        "  case when e.from_node_id=:n then e.to_node_id else e.from_node_id end "
        "where e.org_id=:o and (e.from_node_id=:n or e.to_node_id=:n) "
        "and m.node_type='commitment' and e.valid_to is null"), {"o": org_id, "n": node_id}).all()
    out = []
    for r in rows:
        cf = {x.field: x.value for x in c.execute(text(
            "select field, value from graph_facts where org_id=:o and subject_node_id=:m "
            "and status='active' and field like 'commitment.%'"), {"o": org_id, "m": r.node_id})}
        txt = cf.get("commitment.text")
        if txt:
            out.append({"text": txt, "due_at": cf.get("commitment.due_at"),
                        "status": cf.get("commitment.status")})
    out.sort(key=lambda m: m.get("due_at") or "", reverse=True)
    return out[:3]


def _meeting_neighbors(c, org_id: str, node_id: str) -> list[dict]:
    """One-hop traversal to the person's connected Calendar meetings — the cross-tool bridge the card
    used to ignore (Update 3 §6.9). Node-local projection hid these; now a person's card can show the
    meeting that a Gmail thread led to, with its reconciled lifecycle state."""
    from datetime import datetime, timezone
    from sqlalchemy import text
    rows = c.execute(text(
        "select distinct m.node_id, m.display_name from graph_edges e "
        "join graph_nodes m on m.org_id=e.org_id and m.node_id = "
        "  case when e.from_node_id=:n then e.to_node_id else e.from_node_id end "
        "where e.org_id=:o and (e.from_node_id=:n or e.to_node_id=:n) "
        "and m.node_type='meeting' and e.valid_to is null"), {"o": org_id, "n": node_id}).all()
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        mf = {x.field: x.value for x in c.execute(text(
            "select field, value from graph_facts where org_id=:o and subject_node_id=:m "
            "and status='active' and field like 'meeting.%'"), {"o": org_id, "m": r.node_id})}
        start = mf.get("meeting.start_at")
        state, label = _meeting_lifecycle(mf.get("meeting.status"), start, now)
        out.append({"title": r.display_name or mf.get("meeting.title"),
                    "start_at": start, "status": mf.get("meeting.status"),
                    "state": state, "state_label": label, "source": "gcal"})
    out.sort(key=lambda m: m.get("start_at") or "", reverse=True)
    return out[:4]


def _card_intelligence(org_id: str, card: dict) -> tuple[dict, dict, dict]:
    """Return (context, actionability, decision) for a card — the subject's captured profile facts +
    relationship signals, the Update-1 clarity gate, and the card.v2 decision projection. One DB read,
    deterministic, no LLM. The subject node + reason_code live on the signal (the cards table has
    neither column), so resolve them via signal_id first."""
    signal_id = card.get("signal_id")
    if _graph is None or not signal_id:
        return {}, {"state": "actionable"}, {}
    from sqlalchemy import text
    with _graph.engine.connect() as c:
        row = c.execute(text(
            "select s.subject_node_id, s.reason_code, n.canonical_key "
            "from signals s join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=s.org_id "
            "where s.signal_id=:s and s.org_id=:o"),
            {"s": signal_id, "o": org_id}).first()
        if not row or not row.subject_node_id:
            return {}, {"state": "actionable"}, {}
        node_id, reason_code, canonical_key = row.subject_node_id, row.reason_code, row.canonical_key
        fact_rows = c.execute(text(
            "select field, value, created_at from graph_facts where org_id=:o and subject_node_id=:n "
            "and valid_to is null and status='active'"), {"o": org_id, "n": node_id}).all()
        facts = {r.field: r.value for r in fact_rows}
        obs = c.execute(text(
            "select kind, count(*) n from graph_observations where org_id=:o "
            "and subject_node_id=:n group by kind"), {"o": org_id, "n": node_id}).all()
        interactions = _meeting_neighbors(c, org_id, node_id)
        commitments = _commitment_neighbors(c, org_id, node_id)
    obs_kinds = {r.kind for r in obs}
    obs_counts = {r.kind: int(r.n) for r in obs}
    profile = [{"field": k, "value": v} for k, v in facts.items()
               if k not in _CONTEXT_FACT_SKIP and not k.startswith("thread.")]
    signals = [{"kind": r.kind, "label": _CONTEXT_OBS[r.kind], "count": int(r.n)}
               for r in obs if r.kind in _CONTEXT_OBS]
    # The promised/said text lives on the connected commitment node (already extracted). Use it to
    # GROUND the commitment gate — so the card recovers the real thread topic instead of saying
    # 'context incomplete' — but keep it as neutral 'what was said' context, not a mis-attributed
    # 'you promised', since extraction can capture the counterparty's reschedule ask (Update 4 nuance).
    said = facts.get("commitment.action") or (commitments[0]["text"] if commitments else None)
    gate_facts = set(facts) | ({"commitment.action"} if said else set())
    dec_facts = {**facts, "commitment.action": said} if said else facts
    # A connector/bot subject fails closed to 'reply to the real contacts', never to the intermediary.
    if _is_connector(canonical_key, obs_counts):
        actionability = _connector_gate(canonical_key)
    else:
        actionability = _actionability(reason_code, obs_kinds, gate_facts)
    decision = _decision_projection(reason_code, card, dec_facts, obs_kinds, actionability)
    context = {"profile": profile, "signals": signals, "interactions": interactions,
               "commitments": commitments, "freshness": _freshness(fact_rows)}
    return context, actionability, decision


def _freshness(fact_rows) -> dict | None:
    """Update 2 §10/§16 — the card must be honest that it reads a synced Context Graph, never
    'real-time'. Report when the newest fact was captured, and label the freshness against the trial
    sync cadence (~6h). Deterministic."""
    from datetime import datetime, timezone
    times = [r.created_at for r in fact_rows if getattr(r, "created_at", None)]
    if not times:
        return None
    newest = max(times)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    # Only genuinely old context (>7d) is worth flagging — 1–7 day-old business context is normal and
    # should not carry an alarming 'not live' note on every card.
    label = "fresh" if age_h <= 48 else "aging" if age_h <= 24 * 7 else "stale"
    ago = "just now" if age_h < 1 else f"~{round(age_h)}h ago" if age_h < 48 else f"~{round(age_h / 24)}d ago"
    return {"as_of": newest.isoformat(), "age_hours": round(age_h, 1), "label": label,
            "note": f"Latest info here is {ago} — open the source for anything newer"}


def _owns_authoritative_card(card_id: str, org_id: str) -> dict:
    """Assert tenant ownership and that the originating Layer 4 authority is still live."""
    card = _card_store.get_authoritative_card(card_id, org_id)
    if card is None:
        raise HTTPException(404, "card not found or no longer actionable")
    return card


@router.post("/deliver/build")
def deliver_build(org_id: str = Depends(get_current_org)) -> dict:
    """E0→E1→E3→persist: turn THIS tenant's open, un-carded gated signals into cards (idempotent)."""
    _require_l5()
    from genios_engine.deliver.pipeline import build_cards_for_org
    return build_cards_for_org(graph=_graph, card_store=_card_store, org_id=org_id,
                               llm=_llm, registry=_registry)


@router.post("/cards/sweep")
def cards_sweep(_internal: None = Depends(require_internal)) -> dict:
    """Cron: expire overdue cards + wake snoozed ones (in-process, no Celery). Internal-only."""
    _require_l5()
    return _card_store.sweep_lifecycle()


@router.post("/feedback/calibrate")
def feedback_calibrate(pack_id: str = "sales",
                       org_id: str = Depends(get_current_org)) -> dict:
    """Tenant-safe calibration preview. Mutation is scheduler/internal-only and durably claimed."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from genios_engine.feedback.calibrate import precision_28d
    return {"org_id": org_id, "pack_id": pack_id, "applied": False,
            "preview": precision_28d(_graph, org_id, pack_id=pack_id)}


@router.get("/feedback/precision")
def feedback_precision(pack_id: str = "sales",
                       org_id: str = Depends(get_current_org)) -> dict:
    """The per-rule 28-day precision counters L6 reads (transparency — the moat is a table)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from genios_engine.feedback.calibrate import precision_28d
    return {"pack_id": pack_id, "rules": precision_28d(_graph, org_id, pack_id=pack_id)}


@router.post("/retention/purge")
def retention_purge(_internal: None = Depends(require_internal)) -> dict:
    """Cron: enforce the raw-content TTL — delete encrypted raw_payloads past expires_at across
    all tenants (DB Law 2 / deletion promise). Internal-only. Returns the deletion count."""
    purged = _payload_store.purge_expired() if hasattr(_payload_store, "purge_expired") else 0
    return {"raw_payloads_purged": purged}


@router.get("/cards")
def list_cards(assignee: str | None = None,
               ctx: AuthCtx = Depends(require_scope("cards.read"))) -> dict:
    """Dashboard queue read. org from credential; admin (all queues) only for an owner session
    (JWT / full-scope key), never a caller-supplied flag."""
    _require_l5()
    admin = ctx.scopes is None                       # owner/dashboard session sees all queues
    effective_assignee = assignee if admin else (ctx.actor_id or ctx.agent_id)
    return {"cards": _card_store.queue(
        ctx.org_id, assignee=effective_assignee, admin=admin)}


@router.get("/cards/{card_id}")
def get_card(card_id: str, ctx: AuthCtx = Depends(require_scope("cards.read"))) -> dict:
    """Full card.v1 — only if it belongs to the authenticated tenant."""
    _require_l5()
    card = _owns_authoritative_card(card_id, ctx.org_id)
    actor_id = ctx.actor_id or ctx.agent_id
    if (ctx.scopes is not None and card.get("assignee") is not None
            and card.get("assignee") not in {actor_id, ctx.agent_id}):
        raise HTTPException(403, "card is assigned to a different seat")
    # Enrich the detail with the Update-1 decision context: captured profile + relationship signals,
    # the clarity gate (actionable vs context_incomplete), and the card.v2 decision projection
    # (recommendation verdict/steps, separate confidences, per-section grounding). Plus a documented
    # server-side effect on each CTA. All deterministic, no extra LLM.
    card["context"], card["actionability"], card["decision"] = _card_intelligence(ctx.org_id, card)
    card["actions"] = _annotate_effects(card.get("actions"))
    return card


class CardAction(BaseModel):
    actor: str | None = None                # legacy input; authenticated identity always wins
    action: str                             # run_play | do_it_myself | snooze | wrong | requeue
    reason: str | None = None               # optional, for 'wrong'
    snooze_option: str | None = None        # 4h | tomorrow_09 | 3d | custom
    custom_until: str | None = None


@router.post("/cards/{card_id}/action")
def card_action(card_id: str, body: CardAction,
                ctx: AuthCtx = Depends(require_scope("cards.act"))) -> dict:
    """E8 · the round trip. Card must belong to the authed tenant. Every button + requeue lands
    as an L1 human event, a card_event and a lifecycle transition."""
    _require_l5()
    org_id = ctx.org_id
    actor_id = ctx.actor_id or ctx.agent_id or "authenticated_principal"
    from genios_engine.deliver.actions import ingest_action
    out = ingest_action(card_store=_card_store, graph=_graph, org_id=org_id,
                        card_id=card_id, actor=actor_id, action=body.action,
                        reason=body.reason, snooze_option=body.snooze_option,
                        custom_until=body.custom_until,
                        allow_any_assignee=ctx.scopes is None)
    if not out.get("ok"):
        status = 403 if out.get("error") == "assigned_to_different_seat" else 422
        raise HTTPException(status, out)
    return out


class ContextMatch(BaseModel):
    card_id: str
    matched_tag: str                        # the ONLY upstream bytes — no URL, no page content


@router.post("/context/match")
def context_match(body: ContextMatch,
                  ctx: AuthCtx = Depends(require_scope("cards.act"))) -> dict:
    """E7 round trip (§5.14). On-device matcher sends exactly {card_id, matched_tag}; card must
    belong to the authed tenant. Law 5: the server never learns what the user looked at."""
    _require_l5()
    actor_id = ctx.actor_id or ctx.agent_id or "authenticated_principal"
    result = _card_store.surface_context_match(
        ctx.org_id, body.card_id, body.matched_tag, actor_id=actor_id,
        allow_any_assignee=ctx.scopes is None)
    if not result.get("ok"):
        status = 403 if result.get("error") == "assigned_to_different_seat" else 422
        raise HTTPException(status, result)
    return {**result, "cause": "context_match"}


@router.get("/digest")
def digest(assignee: str | None = None,
           ctx: AuthCtx = Depends(require_scope("cards.read"))) -> dict:
    """The 08:30 morning summary (§5.15), scoped to the authenticated tenant."""
    _require_l5()
    from genios_engine.deliver.digest import build_digest
    admin = ctx.scopes is None
    effective_assignee = assignee if admin else (ctx.actor_id or ctx.agent_id)
    return build_digest(
        _card_store, ctx.org_id, assignee=effective_assignee, admin=admin)


class Seat(BaseModel):
    seat_id: str
    email: str | None = None
    role: str = "member"                    # admin | member


@router.post("/seats")
def upsert_seat(body: Seat, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Seed a seat for the authenticated tenant (org from credential, never from the body)."""
    _require_l5()
    org_id = ctx.org_id
    if body.role not in {"admin", "member"}:
        raise HTTPException(422, "role must be admin or member")
    seat_id = body.seat_id.strip()
    if not seat_id or len(seat_id) > 128:
        raise HTTPException(422, "seat_id must be between 1 and 128 characters")
    from sqlalchemy import text
    with _card_store.engine.begin() as c:
        tier = str(c.execute(text(
            "select subscription_tier from orgs where id=:o for share"),
            {"o": org_id}).scalar() or "trial").lower()
        seat_limit = {"trial": 2, "startup": 5, "growth": 15, "scale": 50}.get(tier, 2)
        exists = c.execute(text(
            "select 1 from org_seats where org_id=:o and seat_id=:s"),
            {"o": org_id, "s": seat_id}).first() is not None
        active = int(c.execute(text(
            "select count(*) from org_seats where org_id=:o and active"),
            {"o": org_id}).scalar() or 0)
        if not exists and active >= seat_limit:
            raise HTTPException(409, f"seat limit reached for the {tier} plan ({seat_limit})")
        c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) "
                       "values (:o,:s,:e,:r,true) on conflict (org_id, seat_id) do update set "
                       "email=excluded.email, role=excluded.role, active=true"),
                  {"o": org_id, "s": seat_id, "e": body.email, "r": body.role})
    return {"upserted": True, "seat_id": seat_id, "role": body.role}


# ── L5 · Agent API (§5.16) · metered read-and-claim; execution stays client-side ────
def _agent_scope(org_id: str, agent_id: str, key: str, scope: str) -> None:
    if scope not in AGENT_API_SCOPES:
        raise HTTPException(422, f"unknown scope: {scope}")
    if not _agent_registry.verify(org_id, agent_id, key, scope):
        raise HTTPException(401, "agent key invalid or scope not granted")


@router.get("/v1/signals")
def agent_poll(org_id: str, agent_id: str, since: str | None = None,
               x_agent_key: str = Header(...)) -> dict:
    """Poll delivered cards' signals + presentation (machine-readable). Metered per read."""
    _require_l5()
    _agent_scope(org_id, agent_id, x_agent_key, "signals.read")
    from genios_engine.deliver import agent_api
    return {"signals": agent_api.poll_signals(_card_store, org_id, agent_id, since=since)}


@router.get("/v1/signals/{signal_id}/artifact")
def agent_artifact(signal_id: str, org_id: str, agent_id: str,
                   x_agent_key: str = Header(...)) -> dict:
    _require_l5()
    _agent_scope(org_id, agent_id, x_agent_key, "artifacts.read")
    from genios_engine.deliver import agent_api
    art = agent_api.get_artifact(_card_store, org_id, signal_id, agent_id)
    if art is None:
        raise HTTPException(404, "no card/artifact for this signal")
    return art


class AgentClaim(BaseModel):
    org_id: str
    agent_id: str


@router.post("/v1/signals/{signal_id}/claim")
def agent_claim(signal_id: str, body: AgentClaim, x_agent_key: str = Header(...)) -> dict:
    """Lock the card 15 min. Double claim → 409 with holder + expiry (first writer wins)."""
    _require_l5()
    _agent_scope(body.org_id, body.agent_id, x_agent_key, "signals.claim")
    from genios_engine.deliver import agent_api
    out = agent_api.claim(_card_store, body.org_id, signal_id, body.agent_id)
    if not out.get("ok"):
        raise HTTPException(out.get("status", 400), out)
    return out


class AgentResult(BaseModel):
    org_id: str
    agent_id: str
    status: str                             # done | failed
    detail: dict | None = None


@router.post("/v1/signals/{signal_id}/result")
def agent_result(signal_id: str, body: AgentResult, x_agent_key: str = Header(...)) -> dict:
    """done resolves; failed re-surfaces to the human with the failure detail (honest failures)."""
    _require_l5()
    _agent_scope(body.org_id, body.agent_id, x_agent_key, "signals.result")
    if body.status not in ("done", "failed"):
        raise HTTPException(422, "status must be done | failed")
    from genios_engine.deliver import agent_api
    return agent_api.result(_card_store, body.org_id, signal_id, body.agent_id,
                            body.status, detail=body.detail)
