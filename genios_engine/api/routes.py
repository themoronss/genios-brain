from __future__ import annotations

import threading

from fastapi import (APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException,
                     Request)
from pydantic import BaseModel

from genios_engine.capture.acquire.scheduler import (ConnectionSchedule, schedules_for,
                                                    select_due)
from genios_engine.capture.acquire.sync_runner import (run_sync, sweep_cadence_policy,
                                                      sweep_tick_seconds)
from genios_engine.capture.connectors.fake import FakeGmailConnector
from genios_engine.capture.connectors.push_ingest import (PushIngestWiring,
                                                         ingest_pushed_objects)
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.contracts.connection import Connection
from genios_engine.contracts.events import (AGENT_ACTIONS, AGENT_API_SCOPES, HUMAN_API_SCOPES,
                                            AgentEvent, HumanEvent)
from genios_engine.platform.auth import (AuthCtx, get_auth_ctx, get_current_org,
                                          require_internal, require_owner, require_scope)
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.capture.esqe.lifecycle import outcome_digest, sweep_lifecycle
from genios_engine.capture.esqe.publisher import publish_sweep
from genios_engine.capture.esqe.qualification import qualify_sweep
from genios_engine.capture.validate.conflict_store import persist_sweep_conflicts
from genios_engine.platform.wiring import (make_agent_event_store,
                                           make_agent_registry_store, make_card_store,
                                           make_conflict_store,
                                           make_drop_ledger, make_floor_store,
                                           make_rejection_ledger,
                                           make_signal_store,
                                           make_lifecycle_store,
                                           make_connection_store, make_coverage_fn,
                                           make_esqe_stage,
                                           make_coverage_store,
                                           make_semantic_lane,
                                           make_structured_lane,
                                           make_connector_for, make_cursor_store,
                                           make_document_job_store, make_graph_store,
                                           make_human_event_store, make_llm_client,
                                           make_open_lane_store, make_pack_registry,
                                           make_parked_store,
                                           make_payload_store, make_prepared_store,
                                           make_relevance_classifier, make_repo,
                                           make_trace_repo)

# ONE top-level import, deliberately: this module had none and used per-function local imports,
# and FOUR call sites (mailbox-owner lookup, heartbeat timezone block, kill switch, backfill
# event cap) used `text` with no local import — each a NameError waiting for its first runtime
# execution, invisible to every import check and to any test that did not walk that exact line.
from sqlalchemy import text

from genios_engine.reason import actionability as _decisive

router = APIRouter()

# Real (DB-backed) stores when DATABASE_URL is set, else in-memory — decided in wiring.
# One engine is shared across them (get_engine is process-cached).
_repo = make_repo()
_trace_repo = make_trace_repo()
_payload_store = make_payload_store()
_prepared_store = make_prepared_store()
_open_lane_store = make_open_lane_store()
_connections = make_connection_store()
_parked = make_parked_store()
_cursors = make_cursor_store()
_documents = make_document_job_store()
_human_events = make_human_event_store()
_agent_events = make_agent_event_store()
_agent_registry = make_agent_registry_store()
_coverage_store = make_coverage_store()               # `source_coverage` — filed each sweep
# `signal_conflicts` — L1.5.5's conflict record. ALG-12 has been detecting conflicts on every
# sweep and returning them on a summary that every caller dropped; this is the store that keeps
# them (see `_run_ledger` for where a sweep's conflicts are actually filed).
_conflict_store = make_conflict_store()
# L1.6.8 (ALG-18) — the qualification floor and the ledger a refusal leaves behind. The floor is
# a PER-TENANT row, so it is read here rather than compiled in: `org_qualification_floors` with
# no row for this org means DEFAULT_FLOOR_BP, never a shared constant somebody edits in a deploy.
_floor_store = make_floor_store()
_drop_ledger = make_drop_ledger()
# L1.6.10 / L1.7.4 — `qualified_signals`, the L1 -> L2 boundary made durable. Resolved here beside
# the floor and its ledger because the three are one decision seen from three sides: what crossed,
# what did not, and against which threshold.
_signal_store = make_signal_store()
# L1.6.10 — `publication_rejections`, the row the OTHER five blocking rules never left. V-1 parks
# and the floor drops; V-2, V-3, V-4, V-6 and V-7 refused a signal and wrote nothing anywhere, so
# "why did I never see X?" had an answer for two of the seven rules. Resolved here beside the
# store for the same reason the drop ledger sits beside the floor: what crossed and what was
# refused are one decision seen from two sides, and reading them from two different builds of the
# same wiring is how the two sides stop agreeing.
_rejection_ledger = make_rejection_ledger()
# L1.6.9 (ALG-19) — the lifecycle rows a sweep ages and supersedes. A per-tenant table for the
# same reason the floor is: what already stands for a subject is this org's own history, and a
# signal that stood live for ever is the ghost L2 correlates.
_lifecycle_store = make_lifecycle_store()
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
def health(request: Request) -> dict:
    """Liveness — and, when the process is alive but the database will not take writes, that too.

    This used to answer a flat "ok" whichever way the database was pointing, which is how a
    four-hour write outage passed every check that was watching. The process really was up; the
    product was not. A degraded boot is reported here because it is the only signal that reaches
    an uptime monitor, and a silent partial outage is the failure mode that costs the most.
    """
    degraded = getattr(request.app.state, "degraded_read_only", None)
    if degraded:
        return {"status": "degraded", "layer": "L1 capture", "writes": "unavailable",
                "reason": degraded}
    return {"status": "ok", "layer": "L1 capture"}


@router.get("/health/readiness")
def health_readiness(org_id: str = Depends(get_current_org)) -> dict:
    """Semantic readiness, not liveness — is THIS tenant in the state the code implies?

    `/health` answers "is the process up"; these receipts answer the question health metrics
    never asked: an empty sweep looked healthy, a skip read as a pass, and "Present / Wired /
    Tested" was communicated as active intelligence. One read-only SELECT per structural claim
    (platform/receipts.py — the same list the release-gate CLI runs, so the operator surface and
    the release gate cannot drift apart about what "ready" means). Auth-scoped to the caller's
    own org: receipts name row counts and internal claims, which is operator material, not
    public liveness.
    """
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from genios_engine.platform.receipts import evaluate
    rows = evaluate(_graph.engine, org_id)
    failed = [r for r in rows if r["status"] != "PASS"]
    return {"org_id": org_id, "ready": not failed,
            "passing": len(rows) - len(failed), "total": len(rows),
            "receipts": rows, "concurrency": _resolved_concurrency()}


def _resolved_concurrency() -> dict:
    """What the pipeline ACTUALLY resolved to in this process.

    These numbers derive themselves from the pooler port, so the deployed value depends on an
    environment variable no code path can see. Tuning them turned into an argument from throughput
    arithmetic — "~14 events/min at a 5.2s LLM call implies about three workers, not eight" — which
    is inference, not a reading, and inference is what has been wrong here repeatedly. A number
    this load-bearing has to be observable from outside the process.

    Behind the same tenant auth as the receipts: it describes deployment shape, not liveness.
    """
    from genios_engine.capture.acquire.sync_runner import _CAPTURE_WORKERS
    from genios_engine.capture.connectors.composio import _FETCH_WORKERS
    from genios_engine.context.runner import _BATCH, _MAX_WORKERS
    url = (getattr(get_settings(), "database_url", "") or "")
    return {"l1_capture_workers": _CAPTURE_WORKERS, "l1_fetch_workers": _FETCH_WORKERS,
            "l2_workers": _MAX_WORKERS, "l2_batch": _BATCH,
            "pooler": "transaction" if ":6543/" in url else "session"}


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
    # D8 · file the sweep's CONFLICTS FIRST, and unconditionally.
    #
    # This used to sit at the BOTTOM of the function, below the `_graph is None` return two
    # lines down — so an engine with a conflict store but no L2 graph store filed nothing at
    # all, silently and with no log line, because that early return is about the sync LEDGER
    # and knows nothing about ALG-12. Two unrelated subsystems sharing one off-switch is how a
    # record that is supposed to be permanent becomes conditional on something it has no
    # relationship with. `persist_sweep_conflicts` never raises, so nothing below it can be
    # made worse by running it first.
    persist_sweep_conflicts(summary, org_id=org_id, store=_conflict_store)
    # L1.6.8 · qualify the sweep's signals against THIS tenant's floor, and file every refusal.
    #
    # Filed from the same hook and for the same reason the conflicts above are: this is the one
    # place every `run_sync` caller in the HTTP layer already reaches, so "the floor ran" does
    # not depend on which of the six sync call sites remembered to ask for it. It sits ABOVE the
    # `_graph is None` return two lines down for the same reason as well — the early return is
    # about the sync LEDGER, and a tenant with no L2 graph store must still be able to answer
    # "why did I never see X?".
    #
    # `qualify_sweep` never raises and never drops mail: it reads the summary's own frozen
    # instant, scores through L1.6.7, and writes `qualification_drops` rows for what the floor
    # refused. A signal it could not score TRAVELS.
    qualification = qualify_sweep(summary, org_id=org_id, floor_store=_floor_store,
                                  ledger=_drop_ledger)
    # L1.6.9 (ALG-19) · age this tenant's signals: expire the clocks that ran out, and let the
    # sweep's newer signals supersede what they replace.
    #
    # Filed from this hook on the same argument as the two above, and it matters more here than
    # for either of them: a lifecycle that ran on five of the six sync call sites would leave the
    # sixth tenant's signals standing live for ever, and "live for ever" is invisible — nothing
    # errors, a founder is simply nudged about a contract that was cancelled last week.
    #
    # ABOVE the `_graph is None` return for the third time and the same reason: that return is
    # about the sync LEDGER. `sweep_lifecycle` never raises and never drops mail — it reads the
    # sweep's own frozen instant, never a clock, so the same sweep replays to the same states.
    lifecycle = sweep_lifecycle(summary, org_id=org_id, store=_lifecycle_store)
    if lifecycle.transitions:
        # ALG-19's REPLAY CHECK, on the path that produces the states. `outcome_digest` is a
        # stable fingerprint of what a sweep decided, and it is the thing an operator compares
        # instead of eyeballing a list of records — "the same sweep at the same `eval_time`
        # produces byte-identical lifecycles" is the property the whole no-clock discipline in
        # `lifecycle.py` exists to buy, and until this line nothing outside its own unit test
        # had ever computed it. Logged rather than stored: it is a check on a decision the
        # `signal_lifecycle` rows already hold, not a second copy of them.
        _log.info("lifecycle swept org=%s transitions=%d records=%d digest=%s",
                  org_id, len(lifecycle.transitions), len(lifecycle.records),
                  outcome_digest(lifecycle))
    # ALG-19's verdict, carried onto the table LAYER 2 ACTUALLY READS.
    #
    # `sweep_lifecycle` above writes what it decided to `signal_lifecycle`.
    # `context/situation_bso.gather_l1_signals` — the one production reader of Layer 1's output —
    # filters a situation's LIVE set on `qualified_signals.state`, and the signals ALG-19
    # supersedes or expires are by definition the ones an EARLIER sweep published, which the
    # `publish_sweep` below never revisits (it writes this sweep's signals and nothing else). So
    # the two tables disagreed permanently: `signal_lifecycle` said `superseded` while
    # `qualified_signals` said `active`, and a founder kept being nudged about a renewal that a
    # later email had already replaced — which is the first thing migration 0093 says it closes.
    #
    # Update-only, terminal states only, and it never raises: see `apply_lifecycle`. `hasattr`
    # because a dev store older than this method must not take the sweep down.
    if lifecycle.records and hasattr(_signal_store, "apply_lifecycle"):
        retired = _signal_store.apply_lifecycle(lifecycle.records)
        if retired:
            _log.info("lifecycle retired %d stored signal(s) org=%s", retired, org_id)
    # L1.6.10 · THE L1 -> L2 BOUNDARY, and the last thing Layer 1 does on this path.
    #
    # `publish_sweep` runs `contracts/publication.validate_publication` (V-1..V-7) over the
    # signals the floor QUALIFIED — the dropped half already has its ledger row and stops there —
    # and writes what survives to `qualified_signals`. Before this call the engine detected,
    # scored, qualified and aged signals on every sync and then dropped every one of them on the
    # floor: L2 had no durable set to read, re-read or replay against, so "what does the engine
    # believe about this tenant" could only be answered by re-running capture over mail we had
    # already paid to read.
    #
    # AFTER the lifecycle pass, and that order is the design rather than an accident of where the
    # line was added. ALG-19 has just decided which of these signals supersedes something the
    # tenant already holds and whether any of them arrived already expired; its outcome is handed
    # straight in, so the stored row carries the state the lifecycle pass decided instead of a
    # publisher's guess of `active`. A row saying live about a signal the same sweep superseded is
    # exactly the kind of disagreement a store that feeds every downstream surface must not have.
    #
    # ABOVE the `_graph is None` return for the fourth time and the same reason: that return is
    # about the sync LEDGER, and a tenant with no L2 graph store must still have its signals
    # stored — otherwise the table built to feed Layer 2 is switched off by an unrelated
    # subsystem's off-switch, which is the defect D8 already had to fix once for conflicts.
    #
    # `publish_sweep` never raises and never drops mail: a signal it cannot publish leaves a park
    # row (V-1) or a logged refusal, never an exception into the ingestion path.
    publish_sweep(summary, qualification, org_id=org_id, store=_signal_store,
                  parked_store=_parked, rejections=_rejection_ledger, lifecycle=lifecycle)
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
    # (The conflict filing this hook is also responsible for happens at the TOP of the function
    # — this is the one hook that already receives every sweep's summary, and `run_sync` hands
    # that summary to six different callers, all of which read the counts and dropped the
    # object. Filing it here rather than at those six call sites is the same argument
    # `push_ingest` makes about its own wiring: a record that depends on which caller
    # remembered is a record that is missing somewhere.)


def _connection_still_valid(connector) -> bool | None:
    """`SourceConnector.validate_connection()` — asked, at last, on a real path.

    EVERY connector in this build implements this method and NOTHING in the engine called it.
    The consequence is not cosmetic: when a sync fails, revoked credentials and a provider hiccup
    produce the same `l1_err`, the same `sync_failed` alert and the same next tick that fails
    again. A tenant whose Google grant was withdrawn got an identical, unactionable notification
    every six hours, for ever, and the one method that could have said "reconnect" was never
    consulted.

    Three-valued on purpose. `True` = the credential still works, so the failure was transient
    and the connection stays connected. `False` = the provider itself refused the credential.
    `None` = we could not ask (the check raised, the connector has no such method), which is NOT
    evidence of revocation — degrading a working connection because a health probe timed out
    would take a tenant's ingestion down over the probe.
    """
    check = getattr(connector, "validate_connection", None)
    if not callable(check):
        return None
    try:
        return bool(check())
    except Exception:      # noqa: BLE001 — a health probe must never widen the original failure
        _log.debug("validate_connection raised during failure triage", exc_info=True)
        return None


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
        process_pending(org_id=org_id, store=_graph, llm=_llm,
                        registry=_registry,
                        crypto_key=get_settings().crypto_key)
        from genios_engine.reason.runner import run_all as run_l3    # L3 after the graph updates
        run_l3(org_id=org_id, store=_graph, registry=_registry)
        if _card_store is not None:                              # L5: new gated signals → cards
            from genios_engine.deliver.pipeline import build_cards_for_org
            build_cards_for_org(graph=_graph, card_store=_card_store, org_id=org_id,
                                llm=_llm, registry=_registry)
    except Exception:
        _log.exception("L2/L3/L5 background pass failed for org_id=%s", org_id)


def _mailbox_owner_for(org_id: str) -> str | None:
    """The connected account's own address, for the visibility participants set.

    `connections.external_account_id` is NULL on every live row (Composio does not report it),
    so the org's signup email is the honest stand-in: the founder connected their own mailbox.
    Same source of truth L2's `_internal_emails` treats as "us", so the two cannot disagree
    about who the tenant is. None when the org has no email — the participants set is then
    sender + recipients, which is still valid, just missing the owner."""
    if _graph is None:
        return None
    try:
        with _graph.engine.connect() as c:
            return c.execute(text("select lower(email) from orgs where id=:o and email is not null"),
                             {"o": org_id}).scalar()
    except Exception:      # noqa: BLE001 — visibility enrichment never blocks a sync
        return None


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
                 mailbox_owner=_mailbox_owner_for(connection.org_id),
                 sender_resolver=_sender_resolver_for(connection.org_id),
                 cursor_store=_cursors,
                 document_job_store=_documents, source=connection.source_type, max_pages=20,
                 run_ledger=_run_ledger,
                 coverage_fn=_coverage_fn_for(connection.org_id),
                 esqe=_esqe_stage_for(connection.org_id),
                 semantic=_semantic_lane_for(connection.org_id),
                 structured=_structured_lane_for(connection.org_id))
    except Exception as e:
        _log.exception("L1 sync failed for org_id=%s connection_id=%s",
                       connection.org_id, connection.connection_id)
        # A total failure (bad auth, provider outage) never reaches run_ledger inside run_sync — write
        # the row here so it's visible in the admin console instead of only in the server log.
        _run_ledger(org_id=connection.org_id, connection_id=connection.connection_id,
                    source=connection.source_type, mode=mode, error=str(e)[:500])
        _notify_sync_failure(org_id=connection.org_id, source=connection.source_type, error=str(e))
    _run_l2(connection.org_id)


def _org_paused(org_id: str) -> bool:
    """Is this tenant's 'stop everything' switch off?

    `check_org_kill` enforces the same flag, but it is a FastAPI dependency — it only ever runs on
    an inbound request. The scheduler sweep is a background thread that never passes through one,
    so a paused org kept being swept: a wipe would delete every row and the next tick refilled the
    graph from Gmail, which reads exactly like the delete silently failed. A switch labelled "stop
    everything" has to stop the largest writer in the system too.

    Fails OPEN like the request-path check: an infra hiccup must not silently halt ingestion.
    """
    if _graph is None:
        return False
    try:
        from sqlalchemy import text
        with _graph.engine.connect() as c:
            row = c.execute(text("select enabled from feature_flags where key=:k"),
                            {"k": f"kill_switch:{org_id}"}).first()
        return row is not None and not bool(row.enabled)
    except Exception:                                # noqa: BLE001 — never block ingestion on this
        return False


def run_sync_sweep(mode: str = "incremental", limit: int | None = None) -> dict:
    """Full auto-sync sweep across EVERY active connection (all orgs): L1 pull for all connections,
    THEN one L2/L3/L5 pass per org (not per-connection — an org with 3 sources shouldn't re-reason 3×).
    Synchronous, per-connection error-isolated, in-process (no Celery/Upstash). Reused by the background
    scheduler (platform/scheduler.py) — the same work /ingest/all does, callable without a request.
    Idempotent at the data layer (source_events dedup), so a re-run (or a second instance) never
    double-writes."""
    limit = get_settings().sync_batch_limit if limit is None else limit
    conns = _connections.list_active()
    # Which tenants are on the L1 semantic lane, read ONCE for the whole cross-org sweep rather
    # than once per connection — the same reason the budget and pause checks are hoisted below.
    activated = _semantic_activated_orgs()
    # L1.2.6 · WHOSE TURN IT IS, ASKED ONCE FOR THE WHOLE SWEEP.
    #
    # `run_sync` has always made this decision per connection, INSIDE itself, and it stays the
    # authority. What no caller ever did was ask it for the BATCH — so `schedules_for`,
    # `schedule_for` and `select_due` (L1.2.6's batch half) had no call site anywhere in the
    # engine, and this sweep paid for both of the things they exist to prevent:
    #
    # * ORDER. The sweep ran `list_active()` in store order. `select_due`'s own docstring names
    #   the consequence — "a sweep with a wall-clock budget that runs its list in store order
    #   starves whatever sorts last" — and this sweep has exactly such a budget: the per-org
    #   daily LLM cap below. Oldest-due first is fairness, and the connection that has waited
    #   longest is the one closest to needing a catch-up.
    # * A ROUND TRIP PER CONNECTION. `run_sync` falls back to `_configured_override_seconds`,
    #   which OPENS A NEW `PostgresConnectionStore` and re-reads the row for every connection on
    #   every tick — to recover a field the `Connection` object in this very loop already holds.
    #   `schedule_for` reads it off that object, and it is forwarded into `run_sync` below.
    #
    # This ORDERS the sweep; it does not gate it. `run_sync` remains the single authority on
    # whether a connection polls, and every connection still reaches it — a connection whose
    # turn it is not is skipped INSIDE `run_sync`, against a cursor it reads itself at poll
    # time, and reported there. A second gate out here, deciding from a snapshot taken a few
    # seconds earlier, would be two answers to one question, and the stale one would win.
    #
    # Incremental only: backfill and recovery are deliberate, cadence-free requests, and
    # `run_sync` does not gate those either.
    from datetime import datetime as _dt, timezone as _tz
    schedule_by_id: dict[str, ConnectionSchedule] = {}
    l1_due = 0
    if mode == "incremental":
        schedules = schedules_for(conns, _cursors)
        schedule_by_id = {s.connection_id: s for s in schedules}
        rank = {d.connection_id: i for i, d in enumerate(select_due(
            schedules, now=_dt.now(_tz.utc), policy=sweep_cadence_policy(),
            base_page_budget=20, sweep_tick_seconds=sweep_tick_seconds()))}
        l1_due = len(rank)
        # Due first, oldest-due first; everything else keeps store order behind them. A tick
        # that runs out of budget now runs out of it on the connections that have waited least.
        conns_to_poll = sorted(conns, key=lambda c: (rank.get(c.connection_id, len(rank)),))
    else:
        conns_to_poll = list(conns)
    rc = make_relevance_classifier()
    l1_ok = l1_err = l1_paused = l1_revoked = 0
    paused: dict[str, bool] = {}
    # Per-org budget decisions are made ONCE per sweep, not per connection: an org with gmail +
    # gcal + drive would otherwise pay for three checks to reach the same answer.
    over_budget: dict[str, bool] = {}
    l1_skipped = 0
    for conn in conns_to_poll:                    # L1: pull each connection (one bad source ≠ others)
        # This background sweep is the largest LLM spender in the system (the S2 gate runs on
        # every unknown sender) and it was the one path the daily cap did not gate — the breaker
        # guarded the onboarding sync only. A runaway here spends unattended, every tick.
        if conn.org_id not in paused:
            paused[conn.org_id] = _org_paused(conn.org_id)
        if paused[conn.org_id]:
            l1_paused += 1
            continue
        if conn.org_id not in over_budget:
            over_budget[conn.org_id] = _llm_over_daily_cap(conn.org_id)
        if over_budget[conn.org_id]:
            l1_skipped += 1
            continue
        _bind_gate_costs(rc, conn.org_id)
        try:
            run_sync(make_connector_for(conn), org_id=conn.org_id, connection_id=conn.connection_id,
                     repo=_repo, mode=mode, limit=limit, parked_store=_parked, relevance=rc,
                     trace_repo=_trace_repo, payload_store=_payload_store,
                     prepared_store=_prepared_store,
                     mailbox_owner=_mailbox_owner_for(conn.org_id),
                     sender_resolver=_sender_resolver_for(conn.org_id),
                     cursor_store=_cursors,
                     document_job_store=_documents, source=conn.source_type, max_pages=20,
                     run_ledger=_run_ledger,
                     coverage_fn=_coverage_fn_for(conn.org_id, connections=conns),
                     esqe=_esqe_stage_for(conn.org_id),
                     semantic=_semantic_lane_for(conn.org_id, activated=activated),
                     # The tenant's own `cadence_minutes`, off the row this loop already holds,
                     # so `run_sync` does not reopen a connection store per connection per tick
                     # to re-read it. `None` outside an incremental sweep, where it is unused.
                     cadence_override_seconds=(
                         schedule_by_id[conn.connection_id].override_seconds
                         if conn.connection_id in schedule_by_id else None),
                     structured=_structured_lane_for(conn.org_id))
            l1_ok += 1
        except Exception as e:
            l1_err += 1
            _log.exception("auto-sync L1 failed org=%s conn=%s", conn.org_id, conn.connection_id)
            # WHY it failed, asked of the provider rather than guessed from the message. A
            # revoked grant needs the tenant to reconnect and will fail identically on every
            # future tick; a transient error needs nothing but the next tick. Only an explicit
            # `False` — the provider refusing the credential — marks the connection, so a probe
            # that could not run leaves a working connection alone.
            reason = "sync_error"
            if _connection_still_valid(make_connector_for(conn)) is False:
                l1_revoked += 1
                reason = "credentials_revoked"
                _connections.set_status(conn.connection_id, "disconnected")
                _log.warning("connection credential refused by provider org=%s conn=%s source=%s"
                             " — marked disconnected", conn.org_id, conn.connection_id,
                             conn.source_type)
            _run_ledger(org_id=conn.org_id, connection_id=conn.connection_id,
                        source=conn.source_type, mode=mode,
                        error=f"{reason}: {str(e)[:480]}")
            _notify_sync_failure(org_id=conn.org_id, source=conn.source_type,
                                 error=f"{reason}: {e}")
    orgs = {c.org_id for c in conns if not paused.get(c.org_id)}
    for org in orgs:                              # L2/L3/L5: once per org, after all its sources pulled
        _run_l2(org)
    _log.info("auto-sync sweep complete: %d/%d connection(s) pulled, %d due this tick, %d "
              "skipped on budget, %d skipped as paused, %d org(s) reasoned",
              l1_ok, len(conns), l1_due, l1_skipped, l1_paused, len(orgs))
    return {"connections": len(conns), "l1_ok": l1_ok, "l1_err": l1_err,
            # Reported rather than silent: "why did this connection not sync" is the question
            # L1.2.6 is always asked, and a sweep that left no number behind could not answer
            # it. `l1_due` is the scheduler's own count for this tick — how many of the active
            # connections it said were due, in the order it put them in.
            "l1_due": l1_due,
            "l1_skipped_over_budget": l1_skipped, "l1_skipped_paused": l1_paused,
            # Connections the PROVIDER refused this tick. Separated from `l1_err` because the
            # two need different responses: this one is the tenant's to fix.
            "l1_credentials_revoked": l1_revoked,
            "orgs": len(orgs)}


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
    # `unclassified_observations` (L1.4.5) rides the same clock: 180 days for an unpromoted
    # observation, forever for a promoted one, and NO new Celery beat — the broker is a
    # quota-limited Upstash Redis, so the lane's retention is one more purge on this heartbeat.
    for name, store in (("raw_payloads", _payload_store), ("prepared_content", _prepared_store),
                        ("unclassified_observations", _open_lane_store)):
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
        # expertise_packages, and this one is not theoretical: it reached 995 MB — 67% of the whole
        # database — and took the project over its disk quota into read-only, which stops every
        # write the product makes. Content-addressing (see contracts/domain_expertise.py) stops the
        # rewrite-when-nothing-changed half; a package still legitimately mints a new id whenever
        # the org-global graph version advances, so the table needs a sweep as well as a fix.
        try:
            from genios_engine.packs.compiler.expertise_publisher import (
                purge_superseded_expertise_packages,
            )
            retention["expertise_packages"] = purge_superseded_expertise_packages(_graph.engine)
        except Exception:                                    # noqa: BLE001 — never kill the heartbeat
            _log.exception("retention purge failed for expertise_packages")
            retention["expertise_packages"] = "error"
    # L1 PARKED DRAIN: a park is "look at this again", so something has to look. Riding the
    # existing heartbeat on purpose — a new Celery periodic task would spend the quota-limited
    # Upstash broker on a pass that is cheap and idempotent here.
    parked_drain = None
    if _graph is not None:
        try:
            from genios_engine.capture.parked.drain import drain_parked
            parked_drain = drain_parked(_graph.engine, now=now)
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("parked drain failed")
            parked_drain = {"error": True}
    # L1.3.8-U1 ATTACHMENT REFETCH: the half `drain_parked` deliberately cannot do. Its
    # NEEDS_REFETCH class (DOC-02/04/05/06) holds attachment STUBS whose bytes never existed
    # locally, so re-running the pipeline over them re-parks them and reports progress that did
    # not happen. This asks the tenant connector for the bytes again, bounded by a five-rung
    # ladder with a dead letter at the end. Same heartbeat, same reason: it is cheap, idempotent
    # and claims with `skip locked`, so it costs nothing when the queue is empty and cannot
    # collide with an operator running it by hand.
    attachment_refetch = None
    if _graph is not None:
        try:
            attachment_refetch = _drain_attachment_refetch(now)
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("attachment refetch failed")
            attachment_refetch = {"error": True}
    # L1.3.8-U3 RECAPTURE DRAIN: the THIRD class, and the one nothing owned. `visibility_unknown`
    # and `MUT-01` are parks about an event's AUDIENCE and its IDENTITY, so neither re-emitting
    # the stored row (`drain_parked`) nor asking for bytes (`refetch_parked_attachments`) can
    # settle them — they were in no drain set at all, which meant `parked_aging` reported them
    # as "terminal" and the G2 report could not see them. Same heartbeat, same argument: one
    # bounded, idempotent pass that costs nothing when the queue is empty.
    recapture_drain = None
    if _graph is not None:
        try:
            recapture_drain = _drain_recapture(now)
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("recapture drain failed")
            recapture_drain = {"error": True}
    # PROVISIONING: every org must have a seat and the durable pull surface before ANY layer can
    # route for it, and neither existed for any tenant. `org_seats` had
    # zero rows for every tenant, and it is the join L2 (self-exclusion), L4 (owner), L5
    # (escalation ladder) and L6 (card recipient) all reach for. Its emptiness was never a
    # configuration anyone chose; signup simply never created the row.
    seats = None
    if _graph is not None:
        try:
            from genios_engine.platform.seats import backfill_provisioning
            with _graph.engine.begin() as c:
                seats = backfill_provisioning(c)
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("owner seat backfill failed")
            seats = {"error": True}
    # L6 TIMEZONE: fill `orgs.timezone` for any org that has never been asked, from the org's own
    # outbound send hours. Quiet hours are defined in LOCAL time, and with the column empty every
    # tenant's window was evaluated in UTC — 21:00-08:00 UTC is 02:30-13:30 in Kolkata, so the
    # politeness window covered the working morning and left the evening open. Never overwrites a
    # set value: a human who typed a zone outranks a histogram.
    timezones = None
    if _graph is not None:
        try:
            from genios_engine.deliver.timezone_infer import infer_and_store
            with _graph.engine.begin() as c:
                pending = [r[0] for r in c.execute(text(
                    "select id from orgs where timezone is null"))]
                timezones = [infer_and_store(c, o) for o in pending]
        except Exception:                                    # noqa: BLE001 — never kill the beat
            _log.exception("timezone inference failed")
            timezones = {"error": True}
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
            try:
                orgs = _executive_orgs()
            except Exception as exc:                 # noqa: BLE001 — enumeration ≠ the whole pass
                # A bare {"error": True} hid a NameError here for 15 days: the pass reported a
                # generic failure every tick and nobody could tell enumeration from execution.
                _log.exception("executive org enumeration failed")
                raise RuntimeError(f"org enumeration: {type(exc).__name__}: {exc}") from exc
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
        except Exception as exc:                             # noqa: BLE001 — never kill the beat
            # Surface the type and message: an opaque {"error": True} is why L5-01 went
            # undiagnosed through 60+ heartbeat ticks of production logs.
            _log.exception("executive sweep pass failed")
            executive = {"error": True, "reason": f"{type(exc).__name__}: {exc}"}
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
        # NO `from sqlalchemy import text` HERE. `text` is imported at module scope (line 54),
        # and a function-local import of the same name makes `text` a LOCAL for the WHOLE
        # function body — including the L6 TIMEZONE block ~60 lines above, which reads it
        # before this line executes. That block therefore raised `UnboundLocalError` on every
        # single tick and was swallowed by its own `except Exception`, so `orgs.timezone` was
        # never inferred for any tenant that had not typed one: quiet hours were evaluated in
        # UTC, and `platform/wiring._org_timezone` — the zone the STRUCTURED lane resolves a
        # typed close date in — answered UTC for every org. Built, scheduled, and dead.
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
            "parked_drain": parked_drain,
            "attachment_refetch": attachment_refetch,
            "recapture_drain": recapture_drain,
            "timezones": timezones,
            "seats": seats,
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
    from sqlalchemy import text                     # module has no top-level sqlalchemy import
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
    activated = _semantic_activated_orgs()      # once for the whole cross-org run
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
                               mailbox_owner=_mailbox_owner_for(conn.org_id),
                               sender_resolver=_sender_resolver_for(conn.org_id),
                               cursor_store=_cursors, document_job_store=_documents,
                               source=conn.source_type, max_pages=20,
                               run_ledger=_run_ledger,
                               coverage_fn=_coverage_fn_for(conn.org_id, connections=conns),
                               esqe=_esqe_stage_for(conn.org_id),
                               semantic=_semantic_lane_for(conn.org_id, activated=activated),
                               structured=_structured_lane_for(conn.org_id))
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


def _semantic_activated_orgs() -> frozenset[str]:
    """The tenants switched on in `l1_semantic_activation`, for a cross-org sweep to read once."""
    from genios_engine.platform.activation import semantic_activated_orgs
    return semantic_activated_orgs(getattr(_graph, "engine", None))


def _semantic_lane_for(org_id: str, activated=None):
    """The S2 lane for one org, or None when this tenant is not on it.

    A separate helper from `_coverage_fn_for` because the two answer different questions and only
    one of them costs money: coverage is always computed, extraction runs only for a tenant
    somebody deliberately switched on in `l1_semantic_activation`. Ships with that table empty, so
    every sweep behaves exactly as it does today until a person adds a row.
    """
    return make_semantic_lane(org_id, engine=getattr(_graph, "engine", None), activated=activated)


def _structured_lane_for(org_id: str):
    """L1.3.9-U5's bundle for one org. UNCONDITIONAL, unlike `_semantic_lane_for` above.

    The typed route calls no model, so there is nothing here for an activation row to gate: a
    CRM object that lands for a tenant nobody switched on is still a typed record, and its close
    date is still resolved in that org's own zone rather than in UTC. This exists so that answer
    is the same at every door — the sweep, the backfill, the webhook — instead of UTC at
    whichever ones were forgotten.
    """
    return make_structured_lane(org_id, engine=getattr(_graph, "engine", None))


def _coverage_fn_for(org_id: str, connections=None):
    """The org's coverage declaration, computed once, as `domain -> verdict`.

    Every capture entry reachable from this module goes through here — the sweep, the Composio
    webhook, the manual door and the dev sample — so that "which capture paths declare coverage"
    has exactly one answer instead of four independent omissions. The declaration is filed to
    `source_coverage` as a side effect, which is the only writer that table has ever had.
    """
    return make_coverage_fn(org_id,
                            connections=(_connections.list_active() if connections is None
                                         else connections),
                            engine=getattr(_graph, "engine", None),
                            store=_coverage_store)


def _esqe_stage_for(org_id: str):
    """The org's S4 bundle, computed ONCE per sweep — today, its L1.6.7 baseline.

    The sibling of `_coverage_fn_for` above, and it is here for the identical reason. ALG-17's
    money term and entity term are 50% of the importance formula and both are relative to the
    ORG: an $84K renewal is a quarter for a startup and noise for a bank, and a counterparty in
    the top decile of one book is a stranger in another. `EsqeStage.org_baseline` was the
    parameter that carried that, no capture entry ever supplied it, and every event of every
    sweep therefore scored against `OrgBaseline.cold_start` — the absolute ladder and
    `first_seen` for everybody. `compute_org_baseline` had no production caller at all.

    Computed here rather than inside `run_sync` because this is where the tenant's database
    handle lives, and once per sweep rather than per event because a p50 over a year does not
    move inside one run.
    """
    return make_esqe_stage(org_id, engine=getattr(_graph, "engine", None))


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
                document_job_store=_documents, run_ledger=_run_ledger,
                # L1.2.5-U1 · the SAME owner every other ingest door supplies. Without it the
                # drain's rows carry a participants set missing the account that owns the
                # mailbox, so a message's ACL depended on which door it came through — and this
                # is the door that lands a tenant's whole history.
                mailbox_owner=_mailbox_owner_for(conn.org_id),
                coverage_fn=_coverage_fn_for(conn.org_id),
                esqe=_esqe_stage_for(conn.org_id),
                semantic=_semantic_lane_for(conn.org_id),
                structured=_structured_lane_for(conn.org_id))
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
        # The dev sample writes REAL source_events rows, so leaving it undeclared reproduces the
        # same hole in the same table — a developer aid is still a capture entry.
        res = capture_event(o, org_id=conn.org_id, connection_id=conn.connection_id,
                            repo=_demo_repo, coverage_fn=_coverage_fn_for(conn.org_id))
        out.append({"outcome": res.outcome,
                    "trace": [{"stage": r.stage, "action": r.action.value,
                               "reason": r.reason_code} for r in res.trace.records],
                    "gated_event": res.gated.model_dump(mode="json") if res.gated else None})
    return {"store_size": _demo_repo.count(), "results": out}


# ── L1.6.8 · the qualification floor and its ledger ───────────────────────────────
#
# THE READ SIDE OF ALG-18, AND THE ONLY WAY ITS TABLES CAN EVER BE WRITTEN BY A HUMAN.
#
# Migration 0088 created three tables and `qualify_sweep` wrote to exactly one of them. The
# floor was therefore a per-tenant setting no tenant could set: `PostgresFloorStore.set` and
# `.history` had no caller anywhere but a test, so `qualification_floor_changes` could not
# receive a row in production and every org ran on `genios-default` 2500 — the global constant
# doc 06 forbids, wearing a table. `PostgresDropLedger.list`/`.get` had no caller either, which
# made "why did I never see X?" — the entire justification for keeping a refused signal's
# components and payload ref — unanswerable from outside the database.
#
# Five routes, no new logic: they resolve the same `_floor_store` / `_drop_ledger` the sweep
# hook at `_run_ledger` already uses, so what an operator reads here is what the sweep decided
# on, not a second opinion assembled from the same rows.
class FloorUpdate(BaseModel):
    """A floor move, with the attribution the changelog requires. `reason` is not decoration —
    "the floor was raised and misses started" is only diagnosable if the raise left one."""

    floor_bp: int
    reason: str = ""
    note: str = ""


def _floor_json(floor) -> dict:
    return {"org_id": floor.org_id, "floor_bp": floor.floor_bp, "owner": floor.owner,
            "note": floor.note, "origin": floor.origin,
            "updated_at": floor.updated_at.isoformat() if floor.updated_at else None}


def _drop_json(row) -> dict:
    """One refused signal as the ledger holds it — components and payload ref included, because
    a drop a tenant cannot reconstruct is regrettable rather than auditable."""
    return {"drop_id": row.drop_id, "signal_id": row.signal_id, "event_id": row.event_id,
            # `getattr`, not `.value`: `drop_rows` stores `verdict.signal_type.value` and
            # `_to_drop_row` decodes a text column, so EVERY row the ledger actually produces
            # carries a `str` here. `.value` alone was an AttributeError — a 500 on every real
            # drop — and it passed because the only test that reached this line hand-built a
            # `DropRow` holding the enum. Both spellings are accepted rather than one coerced at
            # the boundary, because the row type is documented as crossing the database in both
            # directions without re-validation.
            "signal_type": getattr(row.signal_type, "value", row.signal_type),
            "predicate": row.predicate,
            "subject_key": row.subject_key, "importance_bp": row.importance_bp,
            "importance_version": row.importance_version, "floor_bp": row.floor_bp,
            "components": dict(row.components), "payload_ref": row.payload_ref,
            "evaluated_at": row.evaluated_at.isoformat(),
            "retain_until": row.retain_until.isoformat()}


@router.get("/qualification/floor")
def get_qualification_floor(org_id: str = Depends(get_current_org)) -> dict:
    """This tenant's cut-off and WHO answers for it. `origin` separates "somebody chose 6000"
    from "nobody ever set anything" — opposite remedies for the same 92% drop rate."""
    from genios_engine.capture.esqe.qualification import resolve_floor
    return _floor_json(resolve_floor(org_id, _floor_store))


@router.put("/qualification/floor")
def set_qualification_floor(body: FloorUpdate,
                            ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Move the floor. Owner-only: this number decides what the tenant is shown at all, and a
    scoped key that could halve a tenant's signal volume is a wider grant than any read."""
    from datetime import datetime, timezone

    from genios_engine.capture.esqe.qualification import QualificationFloor
    if not 0 <= body.floor_bp <= 10000:
        raise HTTPException(400, "floor_bp must be between 0 and 10000")
    if _floor_store is None:
        raise HTTPException(503, "no qualification floor store configured")
    actor = ctx.actor_id or ctx.org_id
    try:
        floor = _floor_store.set(ctx.org_id, body.floor_bp, owner=actor, changed_by=actor,
                                 at=datetime.now(timezone.utc), reason=body.reason,
                                 note=body.note)
    except ValueError as exc:                     # QualificationFloor's own range/owner checks
        raise HTTPException(400, str(exc)) from exc
    assert isinstance(floor, QualificationFloor)
    return _floor_json(floor)


@router.get("/qualification/floor/history")
def qualification_floor_history(org_id: str = Depends(get_current_org)) -> dict:
    """The changelog. Append-only, newest first — the answer to "who moved it, and why"."""
    if _floor_store is None:
        return {"changes": []}
    return {"changes": [{"change_id": c.change_id, "from_bp": c.from_bp, "to_bp": c.to_bp,
                         "changed_by": c.changed_by, "reason": c.reason,
                         "changed_at": c.changed_at.isoformat()}
                        for c in _floor_store.history(org_id)]}


# ── L1.6.7 term 4 rung 1 · the mission-critical tag, and the only way it is ever written ──
#
# `EntityStanding.MISSION_CRITICAL` is the top rung of a term worth 2000 of ALG-17's 10000 basis
# points, and until migration 0091 it was unreachable: `baseline_reader.load_org_baseline` took
# `mission_critical` as a parameter with an empty default and nothing in the build passed one.
# The consequence was silent — a tenant's payroll provider could rank no higher than its largest
# customer, because money was the only evidence the reader could reach — and it is exactly what
# put doc 06's own headline acceptance row 400 bp below its stated band on the production path.
#
# Three routes, no new logic. The table is read once per sweep by the SAME factory
# (`_esqe_stage_for` -> `make_esqe_stage` -> `load_org_baseline`) that reads the priced history,
# so what an operator sets here is what the next sweep scores against.
class MissionCriticalEntity(BaseModel):
    """One vendor, customer or partner the tenant declares mission-critical.

    `note` is not decoration, on migration 0088's argument about the floor: this tag outranks the
    org's largest contract, and the next operator to see a small vendor above a big customer
    needs the reason ("single-source payroll") rather than only the fact.
    """

    name: str
    note: str = ""


def _mission_critical_rows(org_id: str) -> list[dict]:
    if _graph is None:
        return []
    from sqlalchemy import text
    with _graph.engine.connect() as conn:
        return [{"name": r.display_name, "entity_key": r.entity_key, "owner": r.owner,
                 "note": r.note, "added_at": r.added_at.isoformat()}
                for r in conn.execute(text(
                    "select entity_key, display_name, owner, note, added_at "
                    "from org_mission_critical_entities where org_id = :o "
                    "order by display_name"), {"o": org_id})]


@router.get("/qualification/mission-critical")
def list_mission_critical(org_id: str = Depends(get_current_org)) -> dict:
    """Which entities this tenant has declared mission-critical, and who declared each one."""
    return {"entities": _mission_critical_rows(org_id)}


@router.put("/qualification/mission-critical")
def tag_mission_critical(body: MissionCriticalEntity,
                         ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Declare one entity mission-critical. Owner-only, for the reason the floor route is:
    this changes what the tenant is shown first, and it does it by a judgement rather than by
    a measurement.

    The key is L1.5.4's CANONICAL entity key (`importance.fold_entity_key`), computed here once.
    Not a `casefold()`: ALG-11 has already dropped the legal-form token by the time a name
    reaches term 4, so a signal about "Northwind Ltd" is looked up as `northwind`, and a tag
    stored as `northwind ltd` would never compare equal to it — a mission-critical vendor
    scoring `first_seen`, silently, which is the exact fault `fold_entity_key`'s own docstring
    records for the baseline's sets. It also makes "Northwind" and "Northwind Ltd" one row
    instead of two tags for one vendor.
    """
    from datetime import datetime, timezone

    from sqlalchemy import text

    from genios_engine.capture.esqe.importance import fold_entity_key
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    key = fold_entity_key(name)
    if not key:
        raise HTTPException(400, "name is required")
    if _graph is None:
        raise HTTPException(503, "no database configured")
    actor = ctx.actor_id or ctx.org_id
    with _graph.engine.begin() as conn:
        conn.execute(text(
            "insert into org_mission_critical_entities "
            "(org_id, entity_key, display_name, owner, note, added_at) "
            "values (:o, :k, :d, :w, :n, :at) on conflict (org_id, entity_key) do update set "
            "display_name = excluded.display_name, owner = excluded.owner, note = excluded.note"),
            {"o": ctx.org_id, "k": key, "d": name, "w": actor, "n": body.note,
             "at": datetime.now(timezone.utc)})
    return {"entities": _mission_critical_rows(ctx.org_id)}


@router.delete("/qualification/mission-critical/{name}")
def untag_mission_critical(name: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Remove a tag. The OFF path is a route for the same reason the ON path is: a judgement
    that can only be added is a ranking that drifts upward for ever."""
    from sqlalchemy import text

    from genios_engine.capture.esqe.importance import fold_entity_key
    if _graph is None:
        raise HTTPException(503, "no database configured")
    with _graph.engine.begin() as conn:
        removed = conn.execute(text(
            "delete from org_mission_critical_entities where org_id = :o and entity_key = :k"),
            {"o": ctx.org_id, "k": fold_entity_key(name) or ""}).rowcount
    return {"removed": int(removed), "entities": _mission_critical_rows(ctx.org_id)}


@router.get("/qualification/drops")
def list_qualification_drops(event_id: str | None = None,
                             org_id: str = Depends(get_current_org)) -> dict:
    """What this tenant never saw. `event_id` narrows it to the support question a founder can
    actually ask — "this email produced nothing; why?"."""
    if _drop_ledger is None:
        return {"drops": []}
    return {"drops": [_drop_json(r) for r in _drop_ledger.list(org_id, event_id)]}


@router.get("/qualification/drops/{drop_id}")
def get_qualification_drop(drop_id: str, org_id: str = Depends(get_current_org)) -> dict:
    """One refusal, with the sentence that explains it.

    L1.6.7-U3 rendered from the row rather than from a live score: the components were stored
    precisely so a weight change next month cannot silently re-explain a drop made under the
    old ones, and re-scoring here to produce the sentence would throw that guarantee away.
    """
    from genios_engine.capture.esqe.qualification import explain_drop
    if _drop_ledger is None:
        raise HTTPException(404, "no drop ledger configured")
    row = _drop_ledger.get(org_id, drop_id)
    if row is None:
        raise HTTPException(404, "no such drop")
    return {**_drop_json(row), "explanation": explain_drop(row)}


# ── conflicts ────────────────────────────────────────────────────────────────────
def _card_json(card) -> dict:
    """L1.5.5-U3's card as JSON. `verdict` is carried as an explicit null rather than omitted:
    "authority did not settle this" is the fact doc 05 is strictest about, and a consumer that
    had to infer it from a missing key would eventually infer it wrong."""
    return {
        "headline": card.headline,
        "verdict": card.verdict,
        "lines": [{"authority": line.authority_label, "authority_rank": line.authority_rank,
                   "value": line.value_text, "quote": line.quote,
                   "source_ref": line.source_ref, "text": line.render()}
                  for line in card.lines],
        "text": card.render(),
    }


@router.get("/conflicts")
def list_conflicts(signal_id: str | None = None, limit: int = 50,
                   org_id: str = Depends(get_current_org)) -> dict:
    """Open disagreements, RENDERED — the first surface that turns `signal_conflicts` into
    something a human can read.

    ALG-12 has detected conflicts on every sweep and `persist_sweep_conflicts` has filed them
    since the store landed, but `render_conflict_card` (L1.5.5-U3, the card contract itself) had
    no caller anywhere in the engine: the rows existed and nothing could make a sentence out of
    them. A conflict nobody can see is the same product as no conflict detection at all — worse,
    because the founder is being told nothing while the disagreement is on record.

    `unrenderable` is reported rather than hidden. A row written under an older contract comes
    back from `render_stored_conflict` as None, and a page that silently dropped it would show a
    shorter list with no indication that a disagreement was left out.
    """
    from genios_engine.capture.validate.conflict import render_stored_conflict
    if _conflict_store is None:
        raise HTTPException(404, "no conflict store configured")
    limit = max(1, min(int(limit), 200))
    rendered: list[dict] = []
    unrenderable = 0
    for row in _conflict_store.list(org_id, signal_id)[:limit]:
        card = render_stored_conflict(row)
        if card is None:
            unrenderable += 1
            continue
        rendered.append({
            "conflict_id": row.conflict_id, "signal_id": row.signal_id,
            "subject_key": row.subject_key, "field": row.field,
            "resolution": row.resolution, "event_ids": list(row.event_ids),
            "detected_at": row.detected_at.isoformat() if row.detected_at else None,
            "card": _card_json(card)})
    return {"conflicts": rendered, "unrenderable": unrenderable}


# ── L1.6.10 · the rejection ledger and the signal store, given the doors they had none of ──
#
# `publication_rejections` (migration 0092) exists so that the five BLOCKING rules that reject a
# signal — V-2, V-3, V-4, V-6, V-7 — stop answering nobody. These two routes are what make the
# rows reachable: filed from `_run_ledger`'s hook, read here, off the SAME `_rejection_ledger`
# the sweep writes through, so what an operator reads is what the gate decided rather than a
# second opinion assembled from the same rows.
def _rejection_json(row) -> dict:
    """One refused signal as the ledger holds it — every broken rule, the sentence, and the
    payload ref, because a refusal a tenant cannot reconstruct is regrettable rather than
    auditable."""
    return {"rejection_id": row.rejection_id, "signal_id": row.signal_id,
            "event_id": row.event_id,
            "signal_type": getattr(row.signal_type, "value", row.signal_type),
            "outcome": row.outcome, "rules": list(row.rules), "reason": row.reason,
            "payload_ref": row.payload_ref,
            "evaluated_at": row.evaluated_at.isoformat(),
            "retain_until": row.retain_until.isoformat()}


@router.get("/qualification/rejections")
def list_publication_rejections(event_id: str | None = None,
                                org_id: str = Depends(get_current_org)) -> dict:
    """What the publication gate refused. `event_id` narrows it to the support question a founder
    can actually ask — "this email produced nothing; why?" — which for five of the seven rules
    had no answer at all before this ledger existed."""
    if _rejection_ledger is None:
        return {"rejections": []}
    return {"rejections": [_rejection_json(r)
                           for r in _rejection_ledger.list(org_id, event_id)]}


@router.get("/qualification/rejections/{rejection_id}")
def get_publication_rejection(rejection_id: str,
                              org_id: str = Depends(get_current_org)) -> dict:
    """One refusal, whole. Tenant-scoped by the ledger's own `(org, id)` read rather than by a
    filter applied after the fetch, so a guessed id from another tenant is a 404 and not a row."""
    if _rejection_ledger is None:
        raise HTTPException(404, "no rejection ledger configured")
    row = _rejection_ledger.get(org_id, rejection_id)
    if row is None:
        raise HTTPException(404, "no such rejection")
    return _rejection_json(row)


@router.get("/qualification/signals")
def list_qualified_signals(event_id: str | None = None, state: str | None = "active",
                           limit: int = 100,
                           org_id: str = Depends(get_current_org)) -> dict:
    """What Layer 1 currently BELIEVES about this tenant — `qualified_signals`, read.

    The table had no reader on any request path: the store built to be read by every downstream
    surface could be written and never queried, so "what does the engine believe about this
    tenant right now" could only be answered by re-running capture over mail already paid for.

    THIS IS ALSO WHERE CONFIDENCE AGES. `confidence_bp` on the row is what ALG-13 composed on the
    day of the sweep, and freshness is the one axis of that vector which keeps moving after the
    write — so a June read of an April signal must not be served April's certainty. Both numbers
    are returned: `confidence_bp` is what was composed (what a provenance panel quotes) and
    `aged_confidence_bp` is what it is worth now (what a ranking uses). The CLOCK is read here,
    at the edge, and handed to `age_signals` as `eval_time`; nothing under `capture/` reads one.
    """
    from datetime import datetime, timezone

    from genios_engine.capture.esqe.signal_store import age_signals
    if _signal_store is None:
        return {"signals": []}
    rows = _signal_store.list(org_id, state=state, event_id=event_id,
                              limit=max(1, min(int(limit), 500)))
    aged = age_signals(rows, eval_time=datetime.now(timezone.utc))
    return {"signals": [{
        "signal_id": a.row.signal_id, "event_id": a.row.event_id,
        "signal_type": a.row.signal_type, "state": a.row.state,
        "importance_bp": a.row.importance_bp,
        "importance_version": a.row.importance_version,
        "confidence_bp": a.row.confidence_bp,
        "aged_confidence_bp": a.confidence_bp, "decayed_bp": a.decayed_bp,
        "days_old": a.days_old, "authority_rank": a.row.authority_rank,
        "occurred_at": a.row.occurred_at.isoformat(),
        "expires_at": a.row.expires_at.isoformat() if a.row.expires_at else None,
    } for a in aged]}


# ── parked / coverage ────────────────────────────────────────────────────────────
@router.get("/parked")
def list_parked(reason_code: str | None = None, org_id: str = Depends(get_current_org)) -> dict:
    return {"parked": [p.model_dump(mode="json") for p in _parked.list(org_id, reason_code)]}


@router.get("/parked/aging")
def parked_aging_report(org_id: str = Depends(get_current_org)) -> dict:
    """Backlog per reason, with its oldest entry and whether the drain can ever clear it.

    ``status='pending'`` alone says nothing about whether the queue moves; 347 events sat that
    way from the day they landed and every dashboard read it as healthy.
    """
    if _graph is None:
        return {"aging": []}
    from genios_engine.capture.parked.drain import parked_aging
    return {"aging": parked_aging(_graph.engine, org_id=org_id)}


def _attachment_refetch_queue():
    """The L1.3.8 queue, or None when this deployment has no real database (dev/in-memory)."""
    s = get_settings()
    if not s.use_real_db:
        return None
    from genios_engine.capture.parked.refetch import PostgresRefetchQueue
    return PostgresRefetchQueue(s.database_url, s.crypto_key)


def _attachment_connector_for(candidate):
    """Resolve the tenant connector that can hand back one parked attachment's bytes.

    Returns None — never raises, and never a connector of the wrong shape — for a connection that
    has been removed or for a source with no attachment fetch. The drain treats None as a
    transient miss, so a tenant who reconnects tomorrow gets their backlog drained tomorrow
    instead of finding it dead-lettered.
    """
    conn = _connections.get(candidate.connection_id)
    if conn is None or conn.org_id != candidate.org_id:
        return None
    connector = make_connector_for(conn)
    return connector if hasattr(connector, "fetch_attachment") else None


def _drain_attachment_refetch(now) -> dict:
    queue = _attachment_refetch_queue()
    if queue is None:
        return {"skipped": "no database"}
    from genios_engine.capture.parked.refetch import refetch_parked_attachments
    report = refetch_parked_attachments(queue, connector_for=_attachment_connector_for,
                                        eval_time=now)
    return {"claimed": report.claimed, "recovered": report.recovered,
            "dead_lettered": report.dead_lettered, "retry_scheduled": report.retry_scheduled,
            "text_chars_recovered": report.text_chars_recovered,
            "failures_by_kind": dict(report.failures_by_kind)}


def _drain_recapture(now) -> dict:
    """One recapture cycle for every tenant, with each org's mailbox owner supplied.

    The owner resolver is INJECTED rather than looked up inside the drain because it is the one
    input that can widen an audience: `derive_visibility` adds the connected account to a
    participants set. Passing it here means a re-derived audience is exactly the audience the
    original capture would have produced, and omitting it (a tenant with no resolvable owner)
    narrows rather than widens — the only safe direction.
    """
    if _graph is None:
        return {"skipped": "no database"}
    from genios_engine.capture.parked.recapture import drain_recapture
    report = drain_recapture(_graph.engine, eval_time=now,
                             mailbox_owner_for=_mailbox_owner_for)
    return {"examined": report.examined, "rederived": report.rederived,
            "superseded": report.superseded, "still_blocked": report.still_blocked,
            "stale": report.stale,
            "blocked_by_reason": dict(report.blocked_by_reason)}


@router.get("/parked/recapture")
def recapture_status(org_id: str = Depends(get_current_org)) -> dict:
    """What is still held for a reason only new CODE or a new CAPTURE can clear.

    The read-only twin of the heartbeat drain, and the surface an operator needs to answer "why
    is this tenant's Notion silent" — the answer is a `visibility_unknown` backlog with an age,
    which used to be invisible on every surface in the system.
    """
    if _graph is None:
        raise HTTPException(400, "graph store not configured (needs DATABASE_URL)")
    from genios_engine.capture.parked.drain import parked_aging
    from genios_engine.capture.parked.recapture import NEEDS_RECAPTURE
    rows = [row for row in parked_aging(_graph.engine, org_id=org_id)
            if row["reason_code"] in NEEDS_RECAPTURE]
    return {"org_id": org_id, "codes": sorted(NEEDS_RECAPTURE), "rows": rows,
            "pending": sum(r["count"] for r in rows if r["status"] == "pending")}


@router.get("/parked/refetch")
def attachment_refetch_status(org_id: str = Depends(get_current_org)) -> dict:
    """The admin-console surface L1.3.8 asks for: what is still waiting on a refetch, how old the
    oldest of it is, and what we have STOPPED trying to recover — with the reason we stopped.

    A dead letter that is not listed anywhere is indistinguishable from an attachment that
    vanished, which is the failure this whole component exists to remove."""
    queue = _attachment_refetch_queue()
    if queue is None:
        return {"aging": [], "dead_letters": [], "available": False}
    from datetime import datetime as _dt, timezone as _tz
    from genios_engine.capture.parked.refetch import DEFAULT_POLICY
    aging = queue.aging(eval_time=_dt.now(_tz.utc), policy=DEFAULT_POLICY, org_id=org_id)
    dead = queue.dead_letters(org_id=org_id)
    return {
        "available": True,
        "stuck_after_seconds": aging.stuck_after_seconds,
        "pending": aging.pending, "stuck": aging.stuck,
        "stuck_attachments": aging.stuck_attachments,
        "aging": [{"reason_code": r.reason_code, "object_type": r.object_type,
                   "pending": r.pending, "stuck": r.stuck,
                   "oldest_age_seconds": r.oldest_age_seconds} for r in aging.rows],
        "dead_letters": [{"event_id": d.event_id, "reason_code": d.reason_code,
                          "source_object_id": d.source_object_id, "attempts": d.attempts,
                          "last_error": d.last_error,
                          "last_attempt_at": d.last_attempt_at.isoformat()
                          if d.last_attempt_at else None,
                          "parked_at": d.parked_at.isoformat()} for d in dead],
    }


@router.post("/parked/refetch/requeue")
def requeue_attachment_dead_letters(org_id: str = Depends(get_current_org)) -> dict:
    """Put this org's dead-lettered attachments back on the ladder.

    The action that makes a CAPABILITY dead letter honest: `ocr_unavailable` means "we could not
    read it yet", and the day an engine is wired somebody has to be able to say so to the whole
    backlog at once rather than to 369 event ids by hand."""
    queue = _attachment_refetch_queue()
    if queue is None:
        raise HTTPException(503, "attachment refetch requires a database")
    from datetime import datetime as _dt, timezone as _tz
    return {"requeued": queue.requeue_dead_letters(eval_time=_dt.now(_tz.utc), org_id=org_id)}


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


@router.get("/coverage")
def coverage(domain: str = "sales", org_id: str = Depends(get_current_org)) -> dict:
    """The same declaration the capture path is injected with — one computation, two readers.

    `_connected_capabilities` and `_company_knowledge_count` used to live here as private
    helpers of the HTTP layer, which meant a coverage answer could only be obtained by making a
    web request. A sweep cannot make a web request to itself, which is precisely why the capture
    path never had one. They now live in `capture/coverage/declaration.py` and this endpoint is
    a reader of the same unit rather than the owner of a second copy of it.
    """
    return dict(_coverage_fn_for(org_id)(domain))


@router.get("/coverage/declared")
def coverage_declared(org_id: str = Depends(get_current_org)) -> dict:
    """What we BELIEVED we could see, as last filed to `source_coverage` — read, not recomputed.

    The reader half of L1.7.5, and a different question from `GET /coverage`. That endpoint
    recomputes the declaration, which costs a connection read plus a canon count and always
    answers "now"; this one reads the row a sweep filed, so a caller can ask *what did we believe
    we could see when we decided this*, and can see `computed_at` — the only thing that makes doc
    07's retention line ("recomputed each sweep") checkable. A domain whose row is missing has
    never been declared for this tenant, which is itself the answer.
    """
    rows = _coverage_store.list(org_id)
    return {"declared": [{"domain": r.domain, "coverage_ready": r.coverage_ready,
                          "required": list(r.required), "connected": list(r.connected),
                          "freshness": dict(r.freshness),
                          "computed_at": r.computed_at.isoformat() if r.computed_at else None}
                         for r in rows]}


# ── connection lifecycle ─────────────────────────────────────────────────────────
@router.patch("/connections/{connection_id}/backfill-window")
def set_backfill_window(connection_id: str, days: int = Body(..., embed=True),
                        org_id: str = Depends(get_current_org)) -> dict:
    """L1.2.4-U1 · how far back this connection's FIRST sync reaches — the WRITE side.

    `backfill_window_for` (the read) is wired into `make_connector_for` and decides the window
    every Gmail and Calendar sync uses. `with_backfill_days` — the write it was built against,
    and the whole reason migration 0082 added the column — had no caller anywhere, so the
    setting was readable, per-connection, persisted, and unchangeable: every tenant was pinned
    to `DEFAULT_BACKFILL_DAYS` for ever, and a tenant who wanted three years of history or only
    ninety days had no way to say so.

    Validation happens INSIDE `with_backfill_days` (it constructs a `BackfillWindow` before it
    copies), so an out-of-range value is refused here, at the edit, rather than at the next sync
    — which is the difference between a 422 the caller sees and a sync that quietly clamps.

    Declared BEFORE `/connections/{connection_id}/{action}`: that route matches any single
    segment, so a later declaration would be shadowed by it and this would arrive as an
    `action` of "backfill-window" and 422 on the action check.
    """
    conn = _connections.get(connection_id)
    if conn is None or conn.org_id != org_id:
        raise HTTPException(404, "connection not found")
    from genios_engine.capture.connectors.backfill import (backfill_window_for,
                                                           with_backfill_days)
    try:
        updated = with_backfill_days(conn, days)
    except (ValueError, TypeError) as exc:          # BackfillWindow's own range rule
        raise HTTPException(422, str(exc))
    _connections.add(updated)                       # upserts `capture_scope`
    return {"connection_id": connection_id, "source": conn.source_type,
            "backfill_days": backfill_window_for(updated).days}


@router.get("/structured/mapping-coverage")
def structured_mapping_coverage(org_id: str = Depends(get_current_org)) -> dict:
    """L1.3.9-U2 · which of this tenant's connected structured sources have NO mapping.

    An unmapped structured source is not a quiet degradation: its rows carry no prose body, so
    the unstructured lane cannot read them and the structured lane has nothing to map them with
    — the object is parked as `mapping_missing` and the tenant sees nothing from a tool they
    connected. `mapping_coverage` is the unit that answers which sources are in that state and
    it had no caller, so the answer existed only inside its own test while the condition it
    describes was invisible in production.

    Reads the tenant's OWN connections and the live registry (`all_mappings`), never a list
    written down here — a mapping added to the registry changes this answer with no edit.
    """
    from genios_engine.capture.structured.coverage import ConnectedObject, mapping_coverage
    from genios_engine.capture.structured.registry import all_mappings
    conns = [c for c in _connections.list_active() if c.org_id == org_id]
    coverage = mapping_coverage(ConnectedObject(source=c.source_type) for c in conns)
    return {
        "org_id": org_id,
        "connected_sources": sorted({c.source_type for c in conns}),
        "rows": [{"source": r.source, "object_type": r.object_type,
                  "mapping_id": r.mapping_id, "structured": r.structured,
                  "mapped": r.mapped, "actionable": r.actionable} for r in coverage.rows],
        "mapped": len(coverage.mapped),
        # The ACTIONABLE gap — connected, structured, named, carried by no mapping. Unenumerated
        # rows (a client database whose tables are the tenant's to name) are deliberately in
        # neither half: they are not a success and not a failure, and counting them would make
        # connecting a database read as a coverage regression.
        "unmapped": len(coverage.unmapped),
        "unmapped_structured": coverage.unmapped_structured,
        "unenumerated": len(coverage.unenumerated),
        "coverage_bp": coverage.coverage_bp,
        # The whole registry, so a tenant reading "hubspot.deal is unmapped for you" can see
        # that the mapping exists and the connection is what is missing.
        "registered_mappings": sorted(m.mapping_id for m in all_mappings()),
    }


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


# ── L1.1-U2 · registry honesty: the catalog the UI must render from ─────────────
#
# Both connect endpoints below refuse any source outside BUILDABLE_SOURCES, and until now no
# endpoint exposed that set — so the dashboard hardcoded its own list of nine clickable tiles
# and four of them (slack, jira, gsheets, gdocs) are refused by the endpoint the tile calls.
# The UI must read THIS instead: `connectable` is the tile's enabled-state, `status` is the
# copy, and a "waitlist" source posts to /sources/waitlist rather than to /connect.
def _waitlisted_sources(org_id: str) -> tuple[set[str], list]:
    """This org's standing waitlist, or an empty one if the store cannot answer.

    The catalog must render even when the waitlist store is unavailable: which sources are
    connectable is a fact about the BUILD, and degrading it because a tenant's demand rows
    could not be read would break the connect page for a reason unrelated to connecting."""
    from genios_engine.platform.wiring import make_source_waitlist_store
    try:
        entries = list(make_source_waitlist_store().entries_for(org_id))
    except Exception:                                   # noqa: BLE001
        _log.warning("waitlist_read_failed", extra={"org_id": org_id})
        return set(), []
    return {e.source for e in entries}, entries


def _entry_json(entry) -> dict:
    return {"source": entry.source, "family": entry.family, "capability": entry.capability,
            "registered": entry.registered, "requests": entry.requests,
            "first_requested_at": entry.first_requested_at.isoformat(),
            "last_requested_at": entry.last_requested_at.isoformat(),
            "note": entry.latest_note, "requested_by": entry.latest_requested_by}


@router.get("/sources/catalog")
def sources_catalog(org_id: str = Depends(get_current_org)) -> dict:
    """Every source the product may show, and the ONE honest answer about each.

    Derived from capture/source_registry.py — the same descriptors both connect guards read —
    so a tile can no longer promise what /connect refuses."""
    from genios_engine.capture.source_registry import catalog
    waitlisted, _ = _waitlisted_sources(org_id)
    offers = catalog()
    return {
        "sources": [{"source": o.source, "family": o.family, "status": o.status,
                     "connectable": o.connectable, "capability": o.capability,
                     "aliases": list(o.aliases), "object_types": list(o.object_types),
                     "waitlisted": o.source in waitlisted} for o in offers],
        # The exact set the connect endpoints accept, so a client can check one membership
        # instead of filtering a list it might filter differently.
        "connectable": [o.source for o in offers if o.connectable],
    }


class WaitlistSourceRequest(BaseModel):
    source: str
    note: str | None = None


@router.post("/sources/waitlist")
def waitlist_source(body: WaitlistSourceRequest, org_id: str = Depends(get_current_org),
                    ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    """Record that this tenant wants a source it cannot connect — the action behind
    "coming soon". Refuses a source that IS connectable (the caller is reading a stale
    catalog) and one that has no connector by design (upload/internal/human/agent)."""
    from genios_engine.capture.source_waitlist import WaitlistRefused, request_source
    from genios_engine.platform.wiring import make_source_waitlist_store
    from datetime import datetime as _dt, timezone as _tz
    try:
        entry = request_source(make_source_waitlist_store(), org_id=org_id,
                               source=body.source, requested_by=ctx.actor_id, note=body.note,
                               eval_time=_dt.now(_tz.utc))
    except WaitlistRefused as exc:
        raise HTTPException(400, str(exc))
    return _entry_json(entry)


@router.get("/sources/waitlist")
def waitlist_entries(org_id: str = Depends(get_current_org)) -> dict:
    """What this tenant has asked for, strongest demand first."""
    _, entries = _waitlisted_sources(org_id)
    return {"entries": [_entry_json(e) for e in entries]}


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


def _mirror_connection(org_id: str, source_type: str, *, status: str = "connected") -> None:
    """Upsert a `connections` row once Composio confirms a source is really ACTIVE.

    This is the ONLY thing that lets the 6-hourly scheduler (run_sync_sweep → list_active()) ever
    pick an org+source up again after the first onboarding sync. Composio's live API is correctly
    the source of truth for STATUS (the connect endpoint deliberately doesn't write here — a click
    isn't a completed OAuth), but the scheduler can't call Composio for every org on every tick just
    to know what to sync — it needs a local index. Nothing in the real onboarding→sync flow ever
    wrote one, so `connections` had zero rows for every org that had ever onboarded, and recurring
    auto-sync was silently, permanently dead for 100% of clients past their first backfill.
    Deterministic connection_id (not the random default) so repeat calls upsert the same row
    instead of piling up duplicates that list_active() would then sync twice."""
    if _connections is None:
        return
    from genios_engine.contracts.connection import Connection
    try:
        _connections.add(Connection(connection_id=f"con_{org_id}_{source_type}", org_id=org_id,
                                    source_type=source_type, composio_user_id=org_id,
                                    status=status))
    except Exception:      # noqa: BLE001 — mirroring must never block the sync itself
        _log.exception("connection mirror failed org=%s source=%s", org_id, source_type)


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
    _mirror_connection(org_id, _norm_source(tool), status="disconnected")
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
                    mailbox_owner=_mailbox_owner_for(org_id),
                    run_ledger=_run_ledger, coverage_fn=_coverage_fn_for(org_id),
                    esqe=_esqe_stage_for(org_id),
                    semantic=_semantic_lane_for(org_id),
                    structured=_structured_lane_for(org_id))


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
    # ONE declaration for the whole backfill, hoisted out of the round loop: coverage is a fact
    # about the org's SOURCES, and re-reading the connection table once per page of history would
    # pay for the same answer a hundred times.
    coverage_fn = _coverage_fn_for(org_id)
    # L1.6.7-U2 · the org baseline, once for the whole backfill. Same discipline as the
    # coverage declaration above: a per-ORG quantity read once, not once per round.
    esqe = _esqe_stage_for(org_id)
    semantic = _semantic_lane_for(org_id)
    structured = _structured_lane_for(org_id)
    mailbox_owner = _mailbox_owner_for(org_id)      # one lookup for the whole backfill
    try:
        for rnd in range(max_rounds):
            summary = run_sync(
                connector, org_id=org_id, connection_id=conn.connection_id, repo=_repo,
                mode="backfill", cursor=cursor, limit=limit, source=source_type,
                cursor_store=None, max_pages=1, relevance=make_relevance_classifier(org_id),
                parked_store=_parked, sender_resolver=_sender_resolver_for(org_id),
                trace_repo=_trace_repo, payload_store=_payload_store,
                prepared_store=_prepared_store, document_job_store=_documents,
                run_ledger=_run_ledger, mailbox_owner=mailbox_owner,
                coverage_fn=coverage_fn, esqe=esqe, semantic=semantic,
                structured=structured)
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
    """How many captured events still await L2 — the drain's own filter, for a progress total.

    IMPORTS the drain's exclusion instead of restating it. This function used to carry its own
    copy of "and not in l1_extraction_results", which was correct while Layer 2 was that table's
    only writer and became a lie the moment Layer 1 v2 started filing extractions there: the
    progress bar would report zero pending for a tenant whose drain had a full queue. Two
    spellings of one filter is how a mirror stops mirroring, so there is now one spelling.
    """
    if _graph is None:
        return 0
    from sqlalchemy import text

    from genios_engine.context.runner import _L2_OWN_EXTRACTIONS
    with _graph.engine.connect() as c:
        return int(c.execute(text(
            "select count(*) from source_events se where se.org_id=:o and se.outcome='emitted' "
            f"and se.event_id not in ({_L2_OWN_EXTRACTIONS}) "
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
    coverage_fn = _coverage_fn_for(org_id)          # once per backfill, not once per round
    esqe = _esqe_stage_for(org_id)                  # L1.6.7-U2's baseline, likewise
    semantic = _semantic_lane_for(org_id)
    structured = _structured_lane_for(org_id)
    mailbox_owner = _mailbox_owner_for(org_id)
    for _rnd in range(max_rounds):
        summary = run_sync(
            connector, org_id=org_id, connection_id=conn.connection_id, repo=_repo,
            mode="backfill", cursor=cursor, limit=limit, source=source_type,
            cursor_store=None, max_pages=1, relevance=rel,
            parked_store=_parked, sender_resolver=_sender_resolver_for(org_id),
            trace_repo=_trace_repo, payload_store=_payload_store,
            prepared_store=_prepared_store, document_job_store=_documents,
            run_ledger=_run_ledger, mailbox_owner=mailbox_owner,
            coverage_fn=coverage_fn, esqe=esqe, semantic=semantic,
            structured=structured)
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
                              registry=_registry,
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
    """True when this org has exhausted either daily LLM budget: calls OR dollars.

    The call ceiling and ``settings.daily_llm_usd_cap`` were two caps that bound nothing in
    common — the count breaker guarded one entry point and the USD cap was read only by the
    intelligence route, so the background capture sweep answered to neither. A cap that the
    largest spender in the system does not consult is documentation, not a control.
    """
    if _graph is None:
        return False
    try:
        from sqlalchemy import text

        from genios_engine.platform.metrics import cost_usd_sql
        usd_cap = float(getattr(get_settings(), "daily_llm_usd_cap", 0) or 0)
        with _graph.engine.connect() as c:
            # cost_usd_sql() already returns the sum(...) aggregate — never wrap it again.
            row = c.execute(text(
                f"select count(*) as n, coalesce({cost_usd_sql()}, 0) as usd "
                "from llm_costs where org_id=:o "
                "and created_at >= date_trunc('day', now())"), {"o": org_id}).first()
        n, usd = int(row.n or 0), float(row.usd or 0.0)
        if _LLM_DAILY_CAP > 0 and n >= _LLM_DAILY_CAP:
            _log.warning("org=%s hit the daily LLM CALL cap: %d >= %d", org_id, n, _LLM_DAILY_CAP)
            return True
        if usd_cap > 0 and usd >= usd_cap:
            _log.warning("org=%s hit the daily LLM USD cap: $%.2f >= $%.2f", org_id, usd, usd_cap)
            return True
        return False
    except Exception:      # noqa: BLE001 — a broken cost check must never block a sync
        _log.exception("daily LLM cap check failed org=%s — allowing the sync", org_id)
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
    _mirror_connection(org_id, norm)
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
    for st in sources:
        _mirror_connection(org_id, st)
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
    from genios_engine.capture.connectors.dispatch import can_dispatch, webhook_to_raw_objects
    if not can_dispatch(conn.source_type):
        # TWO DIFFERENT FAILURES, TWO DIFFERENT ANSWERS. "This source has no real-time lane at
        # all" and "this source has one and today's payload did not parse" were both reported as
        # `unmapped payload`, so a source whose parser was never written (the hole HubSpot sat in
        # for the whole of L1.2.5) is indistinguishable from a one-off bad body — which is how a
        # dead lane stays dead: every push looks like a payload problem. `can_dispatch` is the
        # predicate that separates them and it had no caller anywhere in the engine.
        _log.warning("webhook: no real-time lane for source=%s org=%s",
                     conn.source_type, conn.org_id)
        return {"ingested": False, "reason": "no realtime lane", "source": conn.source_type}
    try:
        # PLURAL. This used to take `webhook_to_raw`, which returns objects[0] — so a pushed
        # message with a PDF landed the mail and silently dropped the document, while the same
        # message polled a minute later landed both.
        raw_objs = webhook_to_raw_objects(conn.source_type, data,
                                          connector_factory=lambda: make_connector_for(conn))
    except Exception:                                    # a foreign/bad payload must never 500 the webhook
        _log.exception("webhook parse failed org=%s source=%s", conn.org_id, conn.source_type)
        raw_objs = ()
    if not raw_objs:
        return {"ingested": False, "reason": "unmapped payload", "source": conn.source_type}
    # THE SAME WIRING THE SWEEP USES (`_sync_source`). A pushed message and a polled message must
    # reach L2 as the same object, so the always-on lane cannot be the least-guarded one: the
    # relevance gate, the prepared clean text S2 extracts from, the mailbox owner the ACL is built
    # from, the known-sender whitelist and the park ledger all belong to both doors or to neither.
    outcome = ingest_pushed_objects(
        raw_objs, org_id=conn.org_id, connection_id=conn.connection_id,
        wiring=PushIngestWiring(
            repo=_repo, trace_repo=_trace_repo, payload_store=_payload_store,
            prepared_store=_prepared_store, document_job_store=_documents,
            parked_store=_parked, relevance=make_relevance_classifier(conn.org_id),
            sender_resolver=_sender_resolver_for(conn.org_id),
            mailbox_owner=_mailbox_owner_for(conn.org_id),
            coverage_fn=_coverage_fn_for(conn.org_id),
            esqe=_esqe_stage_for(conn.org_id),
            # L1.6.8 · the push door files its refusals the way the sweep door does. Without
            # these two a tenant served by a webhook-driven source had NO answer to "why did I
            # never see this?", while the same tenant's polled sources had one — and the floor
            # that discards ~92% of traffic ran on one door and not the other.
            floor_store=_floor_store, drop_ledger=_drop_ledger,
            semantic=_semantic_lane_for(conn.org_id),
            structured=_structured_lane_for(conn.org_id)))
    primary = outcome.primary
    if primary is None:                                  # every object poisoned → quarantined, not lost
        return {"ingested": False, "reason": "capture failed", "source": conn.source_type,
                "quarantined": list(outcome.quarantined)}
    return {"ingested": True, "outcome": primary.outcome, "event_id": primary.event.event_id,
            # A push is one payload but not one row: the attachments landed too, and a caller
            # that only ever saw the message could not tell whether they had.
            "objects": [{"object_type": r.event.object_type, "event_id": r.event.event_id,
                         "outcome": r.outcome} for r in outcome.results],
            "quarantined": list(outcome.quarantined)}


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
                           registry=_registry,
                           crypto_key=get_settings().crypto_key, max_total=limit)


@router.post("/context/reason")
def context_reason(ctx: AuthCtx = Depends(require_owner)) -> dict:
    """L3: evaluate deterministic rules over the authed tenant's graph → scored signals (no LLM)."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    org_id = ctx.org_id
    from genios_engine.reason.runner import run_all as run_l3
    return run_l3(org_id=org_id, store=_graph, registry=_registry)


@router.post("/organization/reset")
def organization_reset(reason: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """The pivot primitive: declares that the org's business shape changed. Expires stale
    RUNTIME memory leases and forces an immediate L3 re-evaluation so open situations don't keep
    confidently reasoning against the old shape. Manual and explicit — GeniOS never guesses a
    pivot on its own.

    It does NOT reset the Adaptive brain, despite what this endpoint used to say and return.
    `learned_brain_entries` is untouched, and whether an Adaptive entry can even carry a TTL is
    unratified (ADR-10) — the contract refuses an expiry on non-Runtime targets while the
    consumer reads Adaptive with no expiry predicate at all. The response says
    `adaptive_ttl_unresolved` rather than implying a decision nobody has made."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from datetime import datetime, timezone

    from genios_engine.feedback.reset import apply_organization_reset, mark_situations_rerun
    from genios_engine.reason.runner import run_all as run_l3
    org_id = ctx.org_id
    at = datetime.now(timezone.utc)
    with _graph.engine.begin() as c:
        result = apply_organization_reset(c, org_id=org_id, reason=reason, at=at,
                                          actor=ctx.actor_id)
    rerun = run_l3(org_id=org_id, store=_graph, registry=_registry)
    with _graph.engine.begin() as c:
        mark_situations_rerun(c, reset_id=result["reset_id"])
    return {**result, "situations_rerun": rerun}


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


@router.get("/graph/as-of")
def graph_as_of(at: str | None = None, org_id: str = Depends(get_current_org)) -> dict:
    """L2.2.7-U1 · the graph as it stood at an instant — *"what did GeniOS know when it made that
    decision?"*, which doc 02 says every enterprise security review asks and which this system
    could not answer at all: `graph_versions` was a counter and there was no `as_of` query.

    `?at=` is an ISO-8601 instant; omitted, it reads the live graph, and the two paths are the
    SAME reader (`GraphStore.read_graph` / `.live_graph`) so an audit answer and the dashboard
    cannot disagree about what is currently true. An instant before the org's first write returns
    an empty graph with `graph_version: null` — a representable answer, not a 404.

    The clock is read HERE, at the seam, and nowhere in the store: `read_graph` takes the instant
    as a parameter so a replay of a March decision returns March's graph in September.
    """
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    from datetime import datetime, timezone
    if at:
        try:
            parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(400, f"at must be an ISO-8601 instant: {at!r}") from exc
        instant = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        view = _graph.read_graph(org_id, as_of=instant)
    else:
        view = _graph.live_graph(org_id)
    return view.as_record()


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
                # LIVE cards only. Every other card surface applies the authority gate; this one
                # selected the whole table, so a dead card and the live one that replaced it
                # appeared side by side in the same feed, each asserting a different elapsed time
                # for the same unchanged fact ("3d since they wrote" above "7d since they wrote").
                # The lifecycle already marks a lapsed card `expired` — the reader simply never
                # asked.
                "select headline, situation, urgency_band, created_at from cards "
                "where org_id=:o and state not in ('expired', 'resolved') "
                "and expires_at > now() "
                "order by created_at desc limit :l"), {"o": org_id, "l": limit}):
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
    # A correction is a capture entry like any other: it becomes a `source_events` row L2 reads,
    # so it belongs to the same population the coverage metric is computed over. Undeclared, every
    # correction a founder ever made carried `coverage_ready=None`.
    from genios_engine.capture.intake import ingest_human_event
    res = ingest_human_event(ev, repo=_repo, payload_store=_payload_store,
                             prepared_store=_prepared_store, trace_repo=_trace_repo,
                             coverage_fn=_coverage_fn_for(org_id))
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
    # `ev.org_id` is safe to declare against here: `_agent_registry.verify` above already proved
    # the key belongs to that org, so this is the agent's OWN tenant, not a caller-asserted one.
    from genios_engine.capture.intake import ingest_agent_event
    res = ingest_agent_event(ev, repo=_repo, payload_store=_payload_store,
                             prepared_store=_prepared_store, trace_repo=_trace_repo,
                             coverage_fn=_coverage_fn_for(ev.org_id))
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


def _actionability(reason_code: str | None, obs_kinds: set, fact_fields: set,
                   *, capability_id: str | None = None) -> dict:
    """Update 1 — the universal zero-clarity gate. A card may carry a confident action imperative
    ('reply now', 'deliver the commitment') ONLY when the decisive context for its type is grounded.
    When the action-critical fact is missing, fail closed: switch to a context-recovery outcome so
    the card says 'review the source' instead of inventing confidence. Deterministic, no LLM.

    The requirements are pack data now, not an if/elif chain here — see reason/actionability.py.
    This handled three reason codes and returned `actionable` for everything else, which left the
    sales-critical signals (closed_lost_risk, objection_open, demo_requested, timeline_slip)
    entirely ungated and gave every future rule the same free pass by default.
    """
    return _decisive.evaluate(reason_code, obs_kinds, fact_fields,
                              capability_id=capability_id)


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


def _confidence_block(facts: dict, score_block: dict, actionable: bool,
                      situation: dict | None = None) -> dict:
    """Separate confidence meanings (Update 1): evidence vs identity vs situation vs recommendation.
    These are DIFFERENT quantities and must never collapse into one number.

    Three of the four used to be invented right here: `identity` was `85 if 'company' in facts
    else 30`, `situation` an 80/50 ternary, and `recommendation` the evidence number re-emitted
    under a second name. The API layer owns none of those quantities. Layer 2 does — it computes a
    real five-dimension vector per situation (`context_situations.confidence_*`) from event counts,
    source counts, open discrepancies and open merge proposals.

    So each dimension is now either sourced from L2 or reported ABSENT. `null` is the honest answer
    for a card whose subject has no correlated situation, and it is the answer for 46 of 47 live
    cards — L2 anchors situations on a population that barely intersects the nodes L4 fires rules
    on. Four plausible numbers hid that completely; four fields where three are null makes it the
    first thing anyone reading the payload asks about.
    """
    evidence = int((score_block or {}).get("C") or 0)
    if situation:
        # L2 scores 0-100 on the same scale, so these pass through unchanged.
        identity = situation.get("confidence_identity")
        consistency = situation.get("confidence_consistency")
        overall = situation.get("confidence_overall")
    else:
        identity = consistency = overall = None
    return {
        "evidence": evidence,
        "identity": identity,
        "situation": overall,
        "consistency": consistency,
        # The recommendation is only as good as the weakest input it rests on, and it is not a
        # separate measurement — re-emitting `evidence` under a second name made the vector look
        # twice as substantiated as it was.
        "recommendation": (min(x for x in (evidence, overall) if x is not None)
                           if actionable else 10),
        # Which dimensions have no basis, named rather than inferred from nulls by every consumer
        # independently.
        "absent": [k for k, v in (("identity", identity), ("situation", overall),
                                  ("consistency", consistency)) if v is None],
        "source": "context_situations" if situation else "unavailable",
    }


def _decision_projection(reason_code, card, facts, obs_kinds, actionability,
                         situation: dict | None = None) -> dict:
    """card.v2 decision projection — the typed, grounding-aware read model. Deterministic, no LLM,
    no new reasoning: it only shapes what Layers 1-5 already produced. Fields we cannot ground
    (request text, promised outcome, cost-of-inaction, completion criteria) stay `missing` rather
    than being invented — that gap closes when source bodies are captured (Level 2).

    The recommendation's STEPS come from the signal's own decision columns when the row carries
    them (0070) — the reason_code chain below survives only as the fallback for pre-0070 rows.
    The chain was never lossy compression; it was a parallel independent generator sharing
    nothing with Layer 4 except one string, which is why cards read as activity reminders
    whatever the engine actually decided.
    """
    actionable = actionability.get("state") == "actionable"
    decided_steps = [str(step) for step in (card.get("candidate_steps") or []) if step]
    if not actionable:
        rec = {"verdict": "review_source",
               "objective": "Verify what's actually needed before acting",
               "steps": [actionability.get("recommended") or "Open the source and review the request"],
               "avoid": "Don't reply, deliver, or mark done until the request is verified"}
    elif decided_steps:
        rec = {"verdict": card.get("play") or reason_code or "act",
               "objective": (card.get("why_now") or card.get("situation") or "").strip()
               or f"Resolve the {str(reason_code or 'open').replace('_', ' ')} situation",
               "steps": decided_steps[:4],
               "avoid": "Don't mark done until the success signal is observed"}
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
        # Read from the card, not asserted here. These were hardcoded to "missing" — not absent
        # by accident but written that way — so a card that DID carry its stakes and completion
        # criteria still reported it did not, and no amount of upstream work could ever move the
        # number. They now have columns (migration 0065) and card_builder is their only producer.
        "stakes": gs(bool(card.get("do_nothing_consequence"))),
        "completion": gs(bool(card.get("success_signal"))),
    }
    return {"card_version": "card.v2", "recommendation": rec,
            # The choice's own receipt: which alternatives LOST (with disposition and utility)
            # and what the engine was unsure about. Empty lists on pre-0070 rows — absent, not
            # invented.
            "alternatives_rejected": card.get("rejected_candidates") or [],
            "uncertainty": card.get("decision_uncertainty") or [],
            "confidence": _confidence_block(facts, card.get("score_block") or {}, actionable,
                                            situation),
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
        # Layer 2's real confidence vector for this subject, if it correlated one. Highest-
        # confidence active situation wins when a node anchors several — an anchor holding both a
        # well-evidenced and a thin situation is not "averagely" known, and averaging would let a
        # thin one drag down a dimension it has no bearing on. Today this resolves for 1 card in
        # 47, which is the point: the other 46 now report the three dimensions ABSENT instead of
        # showing invented values that made the L2↔L4 severance invisible from the API.
        sit = c.execute(text(
            "select confidence_overall, confidence_identity, confidence_consistency "
            "from context_situations where org_id=:o and anchor_node_id=:n and status='active' "
            "order by confidence_overall desc nulls last limit 1"),
            {"o": org_id, "n": node_id}).mappings().first()
        situation = dict(sit) if sit else None
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
        actionability = _actionability(reason_code, obs_kinds, gate_facts,
                                       capability_id=card.get("capability_key"))
    decision = _decision_projection(reason_code, card, dec_facts, obs_kinds, actionability,
                                    situation)
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
    admin = ctx.sees_org_queue                       # owner session OR an org-level API key
    effective_assignee = assignee if admin else (ctx.actor_id or ctx.agent_id)
    return {"cards": _card_store.queue(
        ctx.org_id, assignee=effective_assignee, admin=admin)}


@router.get("/cards/{card_id}")
def get_card(card_id: str, ctx: AuthCtx = Depends(require_scope("cards.read"))) -> dict:
    """Full card.v1 — only if it belongs to the authenticated tenant."""
    _require_l5()
    card = _owns_authoritative_card(card_id, ctx.org_id)
    actor_id = ctx.actor_id or ctx.agent_id
    if (not ctx.sees_org_queue and card.get("assignee") is not None
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
                        allow_any_assignee=ctx.sees_org_queue)
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
        allow_any_assignee=ctx.sees_org_queue)
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
    admin = ctx.sees_org_queue           # same rule as /cards — the digest IS the queue, summarised
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
