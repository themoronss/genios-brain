from __future__ import annotations

import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
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
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.sync")

# Acquisition orchestration — pulls batches from a connector (backfill or incremental)
# and runs each raw object through the L1 pipeline. This loop is OURS regardless of
# whether the connector is Composio or native; the connector is just the read primitive.

SenderResolver = Callable[[RawObject], bool]        # deterministic "is this a known sender?"

# Per-page capture concurrency. Each email's capture is independent (dedup is DB-enforced, the
# watermark is an order-independent max), so we run them in parallel to overlap the per-email DB
# round-trips — the real L1 cost. Kept ≤ the Supabase client cap (L2 uses 5); NO data changes,
# only faster.
def _default_workers() -> int:
    """Capture concurrency, derived from the pooler we are actually connected to.

    This used to be a flat 3 with a note saying "raise once the pooler moves to transaction
    mode". The pooler moved; the 3 stayed. Nobody regressed anything — the number simply went
    stale somewhere nobody looks, and the capture path throttled itself against a 15-client cap
    that no longer applied. A default that reads the port cannot drift out of sync with it again.

    Session mode holds a client slot for the whole connection, so 3 is right there. Transaction
    mode returns the backend at the end of each transaction, which is what makes real
    concurrency safe — and L1 is entirely bound by round-trip latency, not by CPU.
    """
    from genios_engine.platform.config import get_settings
    url = (getattr(get_settings(), "database_url", "") or "")
    return 10 if ":6543/" in url else 3


_CAPTURE_WORKERS = int(os.environ.get("GENIOS_L1_WORKERS", "0")) or _default_workers()


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
             source: str | None = None, max_pages: int = 1,
             mailbox_owner: str | None = None,
             reconcile_days: int = 7,
             run_ledger=None,
             fetch_retries: int = 2, fetch_backoff: float = 0.5, _sleep=time.sleep) -> SyncSummary:
    # The connector knows its own source; a caller must never have to restate it. This used to
    # default to "gmail", so any caller that forgot `source=` silently read AND wrote the cursor
    # under the wrong key — a gcal sync would resume from the gmail watermark and persist a
    # `(connection_id=…_gcal, source='gmail')` row alongside the real one. Two cursors for one
    # connection is indistinguishable from a healthy one in every dashboard.
    connector_source = getattr(connector, "source", None)
    if source is None:
        source = connector_source or "gmail"
    elif connector_source and source != connector_source:
        raise ValueError(
            f"source={source!r} contradicts connector.source={connector_source!r}; "
            "the connector is authoritative")

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
    # PREFETCH the next page while this one is being captured.
    #
    # Measured against the live mailbox, one page costs ~16s of pure provider wait — the Composio
    # list call alone is ~10.8s, the relevance gate ~4.5s, and the 12-way body fetch only ~1.1s —
    # and the capture that follows it is another ~16s of DB work. Run back to back they add to the
    # ~32s/round the ledger shows; overlapped they cost the larger of the two. Nothing about the
    # ordering forces them to be serial: `next_cursor` is known the instant a page lands, so the
    # following fetch can be in flight before we look at the current one.
    #
    # One worker, not a pool: pages must stay in order, and a second concurrent list call would
    # only queue behind the provider anyway. Safe against the shared relevance cache — it is a
    # plain dict keyed by source_object_id, and two pages never share an id.
    prefetch: Future | None = None
    pool = (ThreadPoolExecutor(max_workers=1, thread_name_prefix="l1-prefetch")
            if max_pages > 1 else None)
    try:
        for _page in range(max_pages):                  # drain up to max_pages (real API
            if prefetch is not None:
                batch, prefetch = prefetch.result(), None
            else:
                batch = _fetch_page(connector, mode=mode, cursor=page_cursor, limit=limit, since=since,
                                    retries=fetch_retries, backoff=fetch_backoff, sleep=_sleep)
            # Kick the next page off BEFORE the expensive local work, not after it — that ordering is
            # the whole optimisation. A page fetched and then discarded by an early break costs one
            # wasted read; a page fetched serially costs every user 16s.
            if (pool is not None and batch.next_cursor and batch.objects
                    and _page + 1 < max_pages):
                prefetch = pool.submit(
                    _fetch_page, connector, mode=mode, cursor=batch.next_cursor, limit=limit,
                    since=since, retries=fetch_retries, backoff=fetch_backoff, sleep=_sleep)
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
                                            mailbox_owner=mailbox_owner,
                                            sync_mode=sync_mode)
                return raw, res, err

            # BATCH the S2 relevance gate for the whole page in a few LLM calls (prime the classifier's
            # cache) BEFORE per-event capture — turns ~25 gate calls/page into ~2. Best-effort: if the
            # classifier doesn't support priming or a batch fails, capture just calls it per-email.
            if batch.objects and relevance is not None and hasattr(relevance, "prime"):
                try:
                    relevance.prime(batch.objects)
                except Exception:      # noqa: BLE001 — never let batching break the sync
                    pass

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
                if watermark is None or raw.watermark_at > watermark:
                    watermark = raw.watermark_at
            page_cursor = batch.next_cursor
            if not page_cursor or not batch.objects:      # provider exhausted → stop
                break
    finally:
        # A pending fetch after an early break is a read we no longer need; never let it hold the
        # process open. shutdown(wait=False) so a hung provider call cannot outlive the sync.
        if prefetch is not None:
            prefetch.cancel()
        if pool is not None:
            pool.shutdown(wait=False)

    # recovery is a pure safety re-scan — never regress/advance the primary watermark
    if cursor_store is not None and mode != "recovery":
        # Fail-closed clamp: a watermark in the future asks the provider for changes "since" a
        # date that has not arrived, so the connector goes silent while still reporting success.
        # gcal sat at 2026-08-24 for 9 runs this way. No connector may outrun the clock.
        if watermark is not None:
            ceiling = datetime.now(timezone.utc)
            if watermark > ceiling:
                _log.warning("watermark %s for source=%s conn=%s is in the future; clamping to now",
                             watermark.isoformat(), source, connection_id)
                watermark = ceiling
        cursor_store.save(org_id, connection_id, source, cursor=summary.next_cursor,
                          watermark=watermark)
    if run_ledger is not None:                    # l1_sync_runs — observability, never fatal
        try:
            run_ledger(org_id=org_id, connection_id=connection_id, source=source,
                       mode=mode, summary=summary)
        except Exception:       # noqa: BLE001 — a ledger hiccup must not fail the sync
            pass
    # "Data is flowing" is a funnel step, so it needs an event and not just a ledger row. Counts
    # only — no subject, sender or body ever leaves the engine.
    try:
        from genios_engine.platform import analytics
        analytics.capture(org_id, "sync_completed", {
            "source": source, "mode": mode,
            "scanned": getattr(summary, "scanned", 0), "emitted": getattr(summary, "emitted", 0),
            "dropped": getattr(summary, "dropped", 0), "parked": getattr(summary, "parked", 0),
        })
    except Exception:           # noqa: BLE001
        pass
    return summary


def backfill_drain(connector: SourceConnector, *, org_id: str, connection_id: str,
                   repo: SourceEventRepository, source: str, limit: int = 100,
                   max_rounds: int = 500, pages_per_round: int = 8, **kw) -> SyncSummary:
    """Drain a source's FULL history: page in BACKFILL mode until the cursor is exhausted, so a large
    mailbox's older tail is never left behind. The incremental sync only pulls NEW mail (via the
    watermark), so on a huge first connect every page beyond `max_pages` was skipped PERMANENTLY —
    newest-first + an advancing watermark meant the older tail was never re-requested. Run this as a
    background task after connect; dedup makes overlap/restart safe. It passes cursor_store=None so it
    NEVER advances the incremental watermark — the two paths stay independent. `max_rounds` is a
    runaway guard, counted in PAGES.

    `pages_per_round` was effectively 1, which quietly disabled run_sync's page prefetch: with one
    page per call there is never a next page to fetch ahead, so every round paid the provider's
    ~16s serially and then captured for ~16s more. The live backfill showed exactly that — 35
    rounds at a median 32.1s. Batching pages into the call that knows how to overlap them is what
    makes the prefetch reach the path new tenants actually use; the outer loop still exists because
    each round re-reads the cursor and re-checks the runaway guard."""
    total = SyncSummary()
    cursor: str | None = None
    # The guard counts PAGES, not loop iterations. A round used to BE one page, so the two were the
    # same number and `max_rounds` could be read as either; batching pages into a round silently
    # multiplied the ceiling by pages_per_round — a 500-page runaway budget became 4000. Spending
    # the budget explicitly keeps the bound identical to what it has always been, whatever the
    # batch size is tuned to next.
    budget = max_rounds
    while budget > 0:
        take = min(pages_per_round, budget)
        budget -= take
        summary = run_sync(connector, org_id=org_id, connection_id=connection_id, repo=repo,
                           mode="backfill", cursor=cursor, limit=limit, source=source,
                           cursor_store=None, max_pages=take, **kw)
        for f in ("scanned", "emitted", "dropped", "parked", "duplicate", "quarantined"):
            setattr(total, f, getattr(total, f) + getattr(summary, f))
        total.gated.extend(summary.gated)
        total.results.extend(summary.results)
        cursor = summary.next_cursor
        if not cursor:
            break
    total.next_cursor = cursor
    return total
