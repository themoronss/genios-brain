from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from genios_engine.capture.acquire.cursor_store import CursorStore
from genios_engine.capture.connectors.base import RawObject, SourceBatch, SourceConnector
from genios_engine.capture.landing.repository import SourceEventRepository
from genios_engine.capture.parked.store import ParkedStore, parked_from_trace
from genios_engine.capture.payload_store import RawPayloadStore
from genios_engine.capture.pipeline import CaptureResult, capture_event
from genios_engine.capture.trace_store import TraceRepository
from genios_engine.contracts.gated_event import GatedEvent
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.source_event import SyncMode

# Acquisition orchestration — pulls batches from a connector (backfill or incremental)
# and runs each raw object through the L1 pipeline. This loop is OURS regardless of
# whether the connector is Composio or native; the connector is just the read primitive.

SenderResolver = Callable[[RawObject], bool]        # deterministic "is this a known sender?"

# Per-page capture concurrency. Each email's capture is independent (dedup is DB-enforced, the
# watermark is an order-independent max), so we run them in parallel to overlap the per-email DB
# round-trips — the real L1 cost. Kept ≤ the Supabase client cap (L2 uses 5); NO data changes,
# only faster.
_CAPTURE_WORKERS = int(os.environ.get("GENIOS_L1_WORKERS", "3"))   # pool-safe default (Supabase
# session-mode caps total clients at 15; keep L1+L2 workers + the live app well under it). Both are
# env-overridable — raise once the pooler moves to transaction mode. See genios-graph-capture-gaps.


@dataclass
class SyncSummary:
    """Batch-level 'how much came in, how much filtered where'. Complements the
    per-event trace with an aggregate view."""
    scanned: int = 0
    emitted: int = 0
    dropped: int = 0
    parked: int = 0
    duplicate: int = 0
    quarantined: int = 0
    next_cursor: str | None = None
    gated: list[GatedEvent] = field(default_factory=list)
    results: list[CaptureResult] = field(default_factory=list)


def _capture_bounded(raw: RawObject, *, retries: int, **kw):
    """capture_event with bounded retries. A poison object (still failing after
    retries) returns (None, error) so the caller quarantines it — the batch never
    crashes and nothing is silently lost."""
    err = None
    for _ in range(retries + 1):
        try:
            return capture_event(raw, **kw), None
        except Exception as e:      # noqa: BLE001 — deliberately broad; poison isolation
            err = e
    return None, err


def _fetch_page(connector: SourceConnector, *, mode: str, cursor: str | None, limit: int,
                since, retries: int, backoff: float, sleep) -> SourceBatch:
    """Fetch ONE page with bounded exponential backoff. A transient connector failure (rate limit,
    network blip) is retried instead of aborting the whole sync — before this, one failed fetch threw
    out of run_sync, the watermark never advanced, and every following sync died on the same page,
    blocking the connection indefinitely."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return (connector.initial_snapshot(cursor, limit) if mode == "backfill"
                    else connector.incremental_changes(cursor, limit, since=since))
        except Exception as e:      # noqa: BLE001 — transient provider error → backoff + retry
            last = e
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
    raise last                      # retries exhausted → propagate (caller logs; watermark unmoved)


def run_sync(connector: SourceConnector, *, org_id: str, connection_id: str,
             repo: SourceEventRepository, mode: str = "incremental",
             cursor: str | None = None, limit: int = 100,
             sender_resolver: SenderResolver | None = None,
             parked_store: ParkedStore | None = None,
             relevance=None, trace_repo: TraceRepository | None = None,
             payload_store: RawPayloadStore | None = None,
             prepared_store=None,
             cursor_store: CursorStore | None = None,
             document_job_store=None,
             source: str = "gmail", max_pages: int = 1,
             reconcile_days: int = 7,
             run_ledger=None,
             fetch_retries: int = 2, fetch_backoff: float = 0.5, _sleep=time.sleep) -> SyncSummary:
    # No-miss: resume from the stored watermark (incremental only). The dedup ledger
    # drops the boundary overlap, so nothing is missed and nothing double-processed.
    # mode="recovery" = a safety re-scan of a fixed lookback window (ignores watermark,
    # doesn't move it) — anything the primary sync missed lands; dupes drop at dedup.
    since = None
    if mode == "recovery":
        since = datetime.now(timezone.utc) - timedelta(days=reconcile_days)
    elif cursor_store is not None and mode != "backfill":
        saved = cursor_store.get(org_id, connection_id, source)
        if saved is not None:
            cursor = cursor or saved.cursor
            since = saved.watermark

    sync_mode = SyncMode.backfill if mode == "backfill" else SyncMode.incremental
    summary = SyncSummary()
    watermark = since
    page_cursor = cursor
    for _page in range(max_pages):                    # drain up to max_pages (real API
        batch = _fetch_page(connector, mode=mode, cursor=page_cursor, limit=limit, since=since,
                            retries=fetch_retries, backoff=fetch_backoff, sleep=_sleep)
        summary.next_cursor = batch.next_cursor
        summary.scanned += len(batch.objects)

        def _cap(raw: RawObject):
            sk = sender_resolver(raw) if sender_resolver else False
            res, err = _capture_bounded(raw, retries=2, org_id=org_id,
                                        connection_id=connection_id, repo=repo,
                                        sender_known=sk, relevance=relevance,
                                        trace_repo=trace_repo, payload_store=payload_store,
                                        prepared_store=prepared_store,
                                        document_job_store=document_job_store,
                                        sync_mode=sync_mode)
            return raw, res, err

        # capture the whole page CONCURRENTLY — DB round-trips overlap. Each email is independent,
        # so this changes nothing about WHAT is captured, only how fast.
        if batch.objects:
            with ThreadPoolExecutor(max_workers=_CAPTURE_WORKERS) as ex:
                captured = list(ex.map(_cap, batch.objects))
        else:
            captured = []

        for raw, res, err in captured:              # aggregate SINGLE-THREADED → no races on summary
            if res is None:                          # poison → quarantine, batch continues
                summary.quarantined += 1
                if parked_store is not None:
                    parked_store.add(ParkedEvent(
                        event_id=f"{raw.source}:{raw.source_object_id}", org_id=org_id,
                        source=raw.source, reason_code="poison_quarantine", stage="capture",
                        trace=[{"error": type(err).__name__, "detail": str(err)[:200]}]))
                continue
            summary.results.append(res)
            setattr(summary, res.outcome, getattr(summary, res.outcome) + 1)
            if res.gated is not None:
                summary.gated.append(res.gated)
            if res.outcome == "parked" and parked_store is not None:
                reason = res.trace.records[-1].reason_code if res.trace.records else "unknown"
                parked_store.add(parked_from_trace(org_id, res.event.event_id,
                                                   res.event.source, reason or "unknown", res.trace))
            if watermark is None or raw.occurred_at > watermark:
                watermark = raw.occurred_at
        page_cursor = batch.next_cursor
        if not page_cursor or not batch.objects:      # provider exhausted → stop
            break

    # recovery is a pure safety re-scan — never regress/advance the primary watermark
    if cursor_store is not None and mode != "recovery":
        cursor_store.save(org_id, connection_id, source, cursor=summary.next_cursor,
                          watermark=watermark)
    if run_ledger is not None:                    # l1_sync_runs — observability, never fatal
        try:
            run_ledger(org_id=org_id, connection_id=connection_id, source=source,
                       mode=mode, summary=summary)
        except Exception:       # noqa: BLE001 — a ledger hiccup must not fail the sync
            pass
    return summary


def backfill_drain(connector: SourceConnector, *, org_id: str, connection_id: str,
                   repo: SourceEventRepository, source: str, limit: int = 100,
                   max_rounds: int = 500, **kw) -> SyncSummary:
    """Drain a source's FULL history: page in BACKFILL mode until the cursor is exhausted, so a large
    mailbox's older tail is never left behind. The incremental sync only pulls NEW mail (via the
    watermark), so on a huge first connect every page beyond `max_pages` was skipped PERMANENTLY —
    newest-first + an advancing watermark meant the older tail was never re-requested. Run this as a
    background task after connect; dedup makes overlap/restart safe. It passes cursor_store=None so it
    NEVER advances the incremental watermark — the two paths stay independent. `max_rounds` is a
    runaway guard."""
    total = SyncSummary()
    cursor: str | None = None
    for _ in range(max_rounds):
        summary = run_sync(connector, org_id=org_id, connection_id=connection_id, repo=repo,
                           mode="backfill", cursor=cursor, limit=limit, source=source,
                           cursor_store=None, max_pages=1, **kw)
        for f in ("scanned", "emitted", "dropped", "parked", "duplicate", "quarantined"):
            setattr(total, f, getattr(total, f) + getattr(summary, f))
        total.gated.extend(summary.gated)
        total.results.extend(summary.results)
        cursor = summary.next_cursor
        if not cursor:
            break
    total.next_cursor = cursor
    return total
