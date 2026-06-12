"""Bus subscriber that fires the proactive pipeline after a CSV/sync burst.

Wire (registered in `app/main.py` lifespan):
    bus.subscribe("g-i-4 proactive-trigger", proactive_event_subscriber)

Why a debounce instead of "fire pipeline once per MemoryItem":

A single CSV upload emits N items (35 for the AR demo). Running the full
fact-load + rule-fire + webhook-deliver pipeline 35 times would:
  * burn 35× the DB reads,
  * fan out 35× the webhook calls (Hermes would get 35 mostly-redundant
    POSTs while the customer's facts are still mid-ingest),
  * read stale facts on the first 34 invocations because the ingest
    subscriber persists item-by-item.

Instead: each event marks the org "dirty" and resets a 5-second timer.
The timer fires the pipeline ONCE after the burst stops. The 35 items
land in the graph during the burst; the 36th tick is the scan.

Constraints honored:
  * Per-org concurrency — only one pipeline run per org at a time
    (overlapping triggers coalesce via a per-org lock).
  * Per-process scope — debounce state lives in memory. This is fine for
    the single-instance dev/test runtime; production swaps the Timer for
    Celery's `apply_async(countdown=5)` with a Redis idempotency key (see
    `event_subscriber_celery_TODO.md` for the prod recipe). The pipeline
    function (`run_for_org`) is the same in both cases.
  * Failure isolation — exceptions in the timer thread do NOT propagate
    back into the bus emit path. Each org's pipeline runs in its own
    DB session and logs to telemetry.

Plan alignment: respects g-i-1 (subscriber registered on the same
in-process pub/sub bus), g-i-4 (debounced scheduler delegates to
pipeline.run_for_org which is the canonical proactive emit), g-i-7
(webhook delivery + audit happen inside the pipeline).
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from core.foundations.telemetry import get_logger
from core.memory.types import MemoryItem

log = get_logger(__name__)


DEBOUNCE_SECONDS = 5.0  # tunable — short enough to feel "automatic", long enough to coalesce a 35-row CSV burst


# ─── Per-process debounce state ──────────────────────────────────────────────
#
# `_pending_timers` maps org_id -> the live Timer we'll cancel + replace on the
# next event. `_org_locks` ensures at most one pipeline runs per org at any
# instant (re-trigger arriving mid-run still gets a fresh timer scheduled
# AFTER the current run completes).

_state_lock = threading.Lock()
_pending_timers: dict[str, threading.Timer] = {}
_org_locks: dict[str, threading.Lock] = {}


def _get_or_create_org_lock(org_id: str) -> threading.Lock:
    with _state_lock:
        lock = _org_locks.get(org_id)
        if lock is None:
            lock = threading.Lock()
            _org_locks[org_id] = lock
        return lock


def _resolve_org_id(item: MemoryItem) -> Optional[str]:
    """Look up the org_id for this MemoryItem's source_id via the connections
    table. Mirrors `core.worldmodel.ingest_subscriber._org_for_source` so
    both subscribers see the same org-resolution semantics."""
    from sqlalchemy import select

    from core.foundations.db import get_session
    from core.memory.store import Connection

    try:
        with get_session() as session:
            row = (
                session.execute(
                    select(Connection)
                    .where(Connection.source_id == item.source_id)
                    .order_by(Connection.created_at.desc())
                    .limit(1)
                )
                .scalars()
                .one_or_none()
            )
            return row.org_id if row else None
    except Exception as e:
        log.warning(
            "proactive_event_org_resolve_failed",
            item_id=item.item_id,
            source_id=item.source_id,
            error=str(e),
        )
        return None


def _run_pipeline_for_org(org_id: str) -> None:
    """Timer callback — opens a fresh DB session, runs the proactive
    pipeline once for this org, commits, cleans up.

    Exceptions are caught + logged; they do not bubble into the bus."""
    org_lock = _get_or_create_org_lock(org_id)
    if not org_lock.acquire(blocking=False):
        # Another pipeline run is already in flight for this org. The
        # incoming events that triggered THIS timer have already been
        # accounted for in the running pipeline's fact load — safe to skip.
        log.info("proactive_event_skip_overlap", org_id=org_id)
        return

    try:
        # Tidy the pending-timers dict — we own this slot now.
        with _state_lock:
            _pending_timers.pop(org_id, None)

        from core.foundations.db import get_session
        from core.proactive.pipeline import run_for_org

        started_at = time.time()
        with get_session() as session:
            result = run_for_org(
                session, org_id=org_id, module_id="ar_collection", source="event"
            )
            session.commit()
        elapsed_ms = int((time.time() - started_at) * 1000)
        log.info(
            "proactive_event_run_completed",
            org_id=org_id,
            elapsed_ms=elapsed_ms,
            insights_fired=result.get("insights_fired"),
            suppressed=result.get("suppressed_dedupe"),
            webhooks=result.get("webhooks_called"),
        )
    except Exception as e:
        log.exception(
            "proactive_event_run_failed", org_id=org_id, error=str(e)
        )
    finally:
        org_lock.release()


def _is_structured_invoice_item(item: MemoryItem) -> bool:
    """Cheap filter — only invoices trigger the AR pipeline today.

    Once we have multiple modules wired (HR, CSM, etc.) this becomes a
    dispatcher reading `item.metadata.structured_facts.secondary_entity_type`
    and looking up which module(s) consume that entity type. For now,
    `invoice` → ar_collection is the only route.

    Unstructured items (gmail, pdfs) are deliberately ignored here. Those
    flow through their own LLM-extraction subscribers; the AR rules are
    schema-bound and would no-op on the loose facts those produce. When we
    add a module whose rules CAN consume LLM-extracted facts (sales / CSM)
    this filter loosens.
    """
    hint = item.metadata.structured_facts
    if hint is None:
        return False
    return hint.secondary_entity_type == "invoice"


def proactive_event_subscriber(item: MemoryItem) -> None:
    """Bus subscriber — debounce per org, schedule one pipeline run.

    Registered once at startup. Called synchronously by `bus.emit()` for
    every MemoryItem (alongside g-i-3 ingest). Fast path: a few µs of
    work + a thread spawn. The actual pipeline runs on a Timer thread
    DEBOUNCE_SECONDS later.
    """
    if not _is_structured_invoice_item(item):
        return

    org_id = _resolve_org_id(item)
    if org_id is None:
        # Can happen briefly during connection bootstrap. The cron tick
        # picks up anything missed here.
        return

    with _state_lock:
        existing = _pending_timers.get(org_id)
        if existing is not None:
            existing.cancel()
        timer = threading.Timer(DEBOUNCE_SECONDS, _run_pipeline_for_org, args=(org_id,))
        timer.daemon = True
        _pending_timers[org_id] = timer
        timer.start()


def register_proactive_event_subscriber() -> None:
    """Idempotent registration on the in-process bus. Safe to call again on
    reload — the bus replaces the same-named handler."""
    from core.memory.emit import subscribe

    subscribe("g-i-4 proactive-trigger", proactive_event_subscriber)
    log.info("proactive_event_subscriber_registered", debounce_seconds=DEBOUNCE_SECONDS)
