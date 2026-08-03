from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from genios_engine.capture.acquire.cursor_store import CursorStore
from genios_engine.capture.connectors.base import RawObject, SourceConnector
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


def run_sync(connector: SourceConnector, *, org_id: str, connection_id: str,
             repo: SourceEventRepository, mode: str = "incremental",
             cursor: str | None = None, limit: int = 100,
             sender_resolver: SenderResolver | None = None,
             parked_store: ParkedStore | None = None,
             relevance=None, trace_repo: TraceRepository | None = None,
             payload_store: RawPayloadStore | None = None,
             cursor_store: CursorStore | None = None,
             document_job_store=None,
             source: str = "gmail", max_pages: int = 1,
             reconcile_days: int = 7) -> SyncSummary:
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
        batch = (connector.initial_snapshot(page_cursor, limit) if mode == "backfill"
                 else connector.incremental_changes(page_cursor, limit, since=since))
        summary.next_cursor = batch.next_cursor
        for raw in batch.objects:
            summary.scanned += 1
            sender_known = sender_resolver(raw) if sender_resolver else False
            res, err = _capture_bounded(raw, retries=2, org_id=org_id,
                                        connection_id=connection_id, repo=repo,
                                        sender_known=sender_known, relevance=relevance,
                                        trace_repo=trace_repo, payload_store=payload_store,
                                        document_job_store=document_job_store,
                                        sync_mode=sync_mode)
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
    return summary
