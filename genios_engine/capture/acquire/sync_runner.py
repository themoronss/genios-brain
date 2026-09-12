from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from functools import lru_cache
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace as _dc_replace
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence

from genios_engine.capture.acquire.cadence import (DEFAULT_CADENCE_POLICY,
                                                   MAX_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS,
                                                   CadencePolicy, load_cadence_policy)
from genios_engine.capture.acquire.cadence import (
    connection_override_seconds as _connection_override_seconds)
from genios_engine.capture.acquire.cursor_store import CursorStore
from genios_engine.capture.acquire.scheduler import ConnectionSchedule, PollDecision, plan_poll
from genios_engine.capture.connectors.base import RawObject, SourceBatch, SourceConnector
from genios_engine.capture.landing.repository import SourceEventRepository
from genios_engine.capture.parked.store import ParkedStore, parked_from_trace
from genios_engine.capture.payload_store import RawPayloadStore
from genios_engine.capture.pipeline import (CaptureResult, capture_event,
                                            prime_relevance_page)
from genios_engine.capture.validate.claim_group import (ClaimGroup, assemble_claim_groups,
                                                        claims_from_extraction)
from genios_engine.capture.validate.conflict import (ConflictLane, ConflictOutcome,
                                                     ExtractionClaimGrouper)
from genios_engine.capture.trace_store import TraceRepository
from genios_engine.contracts.gated_event import GatedEvent
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.source_event import SourceEvent, SyncMode
from genios_engine.platform.config import get_settings
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
    url = (getattr(get_settings(), "database_url", "") or "")
    return 10 if ":6543/" in url else 3


_CAPTURE_WORKERS = int(os.environ.get("GENIOS_L1_WORKERS", "0")) or _default_workers()


# ── L1.2.6 · WHEN a source is polled ────────────────────────────────────────────────────────────
#
# The poll decision used to be one global number: `settings.sync_interval_hours`, the period of
# the background thread, applied identically to a mailbox and to a quarterly-edited Notion page.
# `capture/acquire/{cadence,jitter,catchup}.py` replaced that number with three units — and for a
# release nothing called them, which made them exactly as effective as the constant they were
# built to remove. This is where they are consulted, in the one function EVERY polling path in
# the product goes through.


@lru_cache(maxsize=1)
def sweep_cadence_policy() -> CadencePolicy:
    """The configured per-source poll table, with `sync_interval_hours` as its fallback.

    The historical setting is not deleted, it is DEMOTED: it stops being "how often everything
    polls" and becomes "how often a source nobody has tuned polls", which is the only question a
    single global number can honestly answer. An operator retunes one provider with
    `GENIOS_SYNC_CADENCES="gmail=5m,notion=1d"` and every other source keeps the reviewed default.

    Cached because it is a pure function of process settings and the sweep asks once per
    connection per tick; `get_settings()` is itself cached, so a changed env needs a restart
    either way.
    """
    settings = get_settings()
    base = DEFAULT_CADENCE_POLICY
    hours = float(getattr(settings, "sync_interval_hours", 0) or 0)
    if hours > 0:
        seconds = max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, int(hours * 3600)))
        base = _dc_replace(base, default_seconds=seconds)
    return load_cadence_policy(getattr(settings, "sync_cadences", ""), base=base)


def sweep_tick_seconds() -> int:
    """How often the background sweep asks. Zero when the scheduler is off.

    The scheduler thread's period and the cadence table are two halves of one schedule: a
    connection whose turn falls a few minutes after a tick would otherwise wait a whole further
    tick, which is how a jittered 6-hour source becomes a 12-hour source. `tick_grace_seconds`
    closes that, and it needs this number to do it.
    """
    settings = get_settings()
    if not getattr(settings, "scheduler_enabled", True):
        return 0
    hours = float(getattr(settings, "sync_interval_hours", 0) or 0)
    return int(hours * 3600) if hours > 0 else 0


def _configured_override_seconds(org_id: str, connection_id: str) -> int | None:
    """This connection's own cadence override, out of `connections.config`.

    Read here rather than taken as a parameter because the callers that matter — the sweep, the
    manual trigger, `/ingest/all` — hand `run_sync` an org, a connection id and a connector, and
    never the `Connection` row itself. A tenant-set `cadence_minutes` that only applies when a
    caller remembers to forward it is a setting that silently does nothing for the paths that
    actually poll.

    Read through the CONNECTION STORE rather than with SQL of its own, and the difference is
    not style. `connections.config` is stored in a column called `capture_scope` and comes back
    through `_open_config`, so a hand-written `select config from connections` fails in exactly
    the way a connection with no override succeeds — the tenant's knob would silently do nothing
    forever, which is the same defect as a unit with no caller wearing a different hat. The
    store owns that mapping; asking it cannot drift from it.

    Never fatal: a missing table, a pooler blip or no database at all means "no override", and
    the source's policy cadence applies. Failing a sync over a tuning knob would be a worse
    outcome than ignoring the knob.
    """
    url = getattr(get_settings(), "database_url", "") or ""
    if not url:
        return None
    try:
        from genios_engine.capture.connections.store import PostgresConnectionStore
        connection = PostgresConnectionStore(url).get(connection_id)
        if connection is None or connection.org_id != org_id:
            return None
        return _connection_override_seconds(connection)
    except Exception:      # noqa: BLE001 — a tuning knob must never take a sync down
        _log.debug("cadence override lookup failed for org=%s conn=%s", org_id, connection_id)
        return None


_SWEEP_MARK = threading.local()


@contextmanager
def scheduled_sweep():
    """Mark THIS thread as the background sweep's tick, for the length of the block.

    The cadence gate must bind the SCHEDULER and must not bind a person pressing "Sync now": one
    is a recurring poll whose whole point is that it happens on a rhythm, the other is an
    explicit instruction that would look broken if it silently did nothing. `run_sync` is the
    single function both go through and neither passes anything that tells them apart, so the
    distinction is carried by the one thing that genuinely differs — WHICH THREAD is asking.

    Thread-local rather than a module global because the sweep runs on its own worker while
    FastAPI's background tasks run on the request threadpool at the same moment; a global would
    make a manual sync inherit the sweep's rule whenever the two overlapped. Set in exactly one
    place (`platform/scheduler.py`), read in exactly one place (`run_sync`), and overridable at
    any call site with `respect_cadence=`.
    """
    previous = getattr(_SWEEP_MARK, "on", False)
    _SWEEP_MARK.on = True
    try:
        yield
    finally:
        _SWEEP_MARK.on = previous


def in_scheduled_sweep() -> bool:
    """True while the calling thread is inside `scheduled_sweep()`."""
    return bool(getattr(_SWEEP_MARK, "on", False))


def poll_decision(*, org_id: str, connection_id: str, source: str,
                  last_success_at: datetime | None, watermark: datetime | None,
                  now: datetime, base_page_budget: int,
                  override_seconds: int | None = None) -> PollDecision:
    """Is this connection's turn now, and how many pages does this run get — L1.2.6, composed.

    A thin, typed seam so the sweep's decision is one call with one answer, and so a test can
    drive the decision without reaching into three units. Everything it consults is a value it
    was handed or a setting; nothing here reads a clock.
    """
    return plan_poll(
        ConnectionSchedule(org_id=org_id, connection_id=connection_id, source=source,
                           override_seconds=override_seconds, last_success_at=last_success_at,
                           watermark=watermark),
        now=now, policy=sweep_cadence_policy(), base_page_budget=base_page_budget,
        sweep_tick_seconds=sweep_tick_seconds())


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
    #: The L1.2.6 decision this run was made under, or None when no schedule applied (a backfill,
    #: a recovery re-scan, a caller with no cursor store, or `respect_cadence=False`). Carried on
    #: the summary because "why did this connection not sync" is the question the subsystem is
    #: always asked, and a skipped poll that left no answer behind is the failure the whole
    #: decision object exists to prevent.
    poll: PollDecision | None = None
    #: ALG-23's answer for this sweep: every claim that must be compared with every other one,
    #: assembled ACROSS the page's events. It has to live here rather than on a CaptureResult
    #: because a Gmail message lands as an `email_message` PLUS one `email_attachment` per file
    #: (composio.py:512/:559) — two events — so a per-event group would never put the covering
    #: mail's $84,000 beside the signed PDF's $74,000, which is the one comparison the whole
    #: unit exists to make. L1.5.5 reads this; nothing in it is scored.
    claim_groups: tuple[ClaimGroup, ...] = ()
    #: ALG-12's answer for this sweep — every disagreement between the claims above, with BOTH
    #: sides retained, plus the material ones raised as `INFORMATION_CONFLICT` escalations.
    #: `None` when the sweep extracted nothing to compare. Detected here rather than inside
    #: `capture_event` for the reason `claim_groups` is: a conflict lives BETWEEN two events, and
    #: the covering mail's $84,000 only meets the signed PDF's $74,000 once both have landed.
    conflicts: ConflictOutcome | None = None
    #: WHEN THIS RUN BEGAN — wall time, at the edge, for the ledger and for nothing else.
    #: `l1_sync_runs.started_at` is a column the writer never filled, so every row in production
    #: reports a finish with no start and "this sync took eleven minutes" was a question the
    #: ledger could not answer. Nothing under `capture/` branches on it: it is observability, it
    #: is read once by `api/routes._run_ledger`, and it comes from the SAME `_now` seam the poll
    #: decision uses so a test can freeze it rather than race it.
    started_at: datetime | None = None

    @property
    def skipped_not_due(self) -> bool:
        """True when the scheduler declined this run — nothing was fetched and nothing failed."""
        return self.poll is not None and not self.poll.due


def _capture_bounded(raw: RawObject, *, retries: int, **kw):
    """capture_event with bounded retries. A poison object (still failing after
    retries) returns (None, error) so the caller quarantines it — the batch never
    crashes and nothing is silently lost.

    A RETRY THAT COMES BACK "duplicate" IS THE FIRST ATTEMPT'S FAILURE, NOT A DUPLICATE.
    `capture_event` writes its `source_events` row after the gate and BEFORE extraction, so an
    exception anywhere downstream of that write — an extractor, a store, a lane — leaves the
    ledger row behind. The next attempt's dedup check then finds it, returns `outcome
    "duplicate"`, and this function reported success. The batch counted 96 duplicates, wrote 96
    rows, produced zero extractions and raised nothing: a total loss that looks exactly like a
    quiet re-sync. Only the FIRST attempt can legitimately report a duplicate, so a duplicate
    after a failure is re-raised as that failure and the caller quarantines the object, which is
    what it does with every other poison result.
    """
    err = None
    for attempt in range(retries + 1):
        try:
            result = capture_event(raw, **kw)
        except Exception as e:      # noqa: BLE001 — deliberately broad; poison isolation
            err = e
            continue
        if err is not None and getattr(result, "outcome", None) == "duplicate":
            return None, err
        return result, None
    return None, err


def _assemble_groups(results: Sequence[CaptureResult]) -> tuple[ClaimGroup, ...]:
    """ALG-23 over everything this sweep extracted — the production call site for L1.5.0.

    Assembled here, once, over the WHOLE batch rather than inside `capture_event`, because the
    grouping key is the document group and an attachment's claims only meet its message's claims
    when both events are in hand. Events with no extraction still travel: they are the parents
    the thread walk needs to get from a file to its thread.

    Never fatal. A malformed claim costs the sweep its grouping, not its mail.
    """
    events = [result.event for result in results]
    # The index is built over the WHOLE batch BEFORE any claim is derived. Built incrementally it
    # would depend on capture order, and the page is captured by a thread pool — an attachment
    # finishing ahead of its message would silently lose its thread on some runs and keep it on
    # others, which is the nondeterminism the whole unit is written to avoid.
    parent_lookup = _by_source_object(events).get
    claims = []
    for result in results:
        if result.extraction is not None:
            claims.extend(claims_from_extraction(result.event, result.extraction,
                                                 event_lookup=parent_lookup))
    if not claims:
        return ()
    try:
        return assemble_claim_groups(claims, events)
    except Exception:           # noqa: BLE001 — grouping is downstream of capture, never above it
        _log.warning("claim grouping failed for a batch of %d claims", len(claims), exc_info=True)
        return ()


def _by_source_object(events: Sequence[SourceEvent]) -> dict[str, SourceEvent]:
    """`source_object_id` -> event: the index ALG-23's parent walk reads.

    Keyed on the SOURCE's id and not ours, because that is what `parent_object_id` points at —
    an attachment names its message by the provider's message id, never by our `event_id`.
    First writer wins, so a re-landed duplicate cannot displace the event already indexed."""
    index: dict[str, SourceEvent] = {}
    for event in events:
        key = (event.source_object_id or "").strip()
        if key and key not in index:
            index[key] = event
    return index


def _detected_at(semantic) -> datetime:
    """The instant ALG-12 stamps on this sweep's conflicts.

    The semantic lane's frozen `eval_time` when there is one, and only otherwise a clock read.
    A replayed sync re-extracts against the instant it is replaying, and a conflict row stamped
    `now()` would make the replay disagree with the run it is reproducing on the one field that
    is supposed to prove they are the same run.
    """
    frozen = getattr(semantic, "eval_time", None)
    return frozen if isinstance(frozen, datetime) else datetime.now(timezone.utc)


def _detect_conflicts(results: Sequence[CaptureResult], *,
                      groups: Sequence[ClaimGroup],
                      detected_at: datetime) -> ConflictOutcome | None:
    """ALG-12 over everything this sweep extracted — the production call site for L1.5.5.

    Run HERE, after the page is captured, rather than through `capture_event`'s `conflict_lane`
    parameter, and the reason is the thread pool twenty lines below: `ConflictLane` accumulates
    claims across events, and a stateful lane driven from `_CAPTURE_WORKERS` threads would both
    race on its own claim list and hand the conflict to whichever event happened to finish
    second. Detection would then depend on thread scheduling, which is the nondeterminism
    `_assemble_groups` is written the same way to avoid. `ex.map` preserves input order and this
    aggregation is single-threaded, so the sweep sees one fixed sequence of claims.

    The cost of that placement, stated rather than hidden: S4 has already qualified each event by
    the time this runs, so a conflict found here does NOT raise `INFORMATION_CONFLICT` on the
    events it spans within the same sweep — `detection.conflicts` is the sweep's answer and the
    escalations carry it. Making the ESQE predicate see it would mean re-qualifying an event
    after its siblings land, which is L1.6's sequencing decision and not this runner's to take.

    Never fatal, on the same terms as grouping: a malformed claim costs the sweep its conflict
    detection, not its mail.
    """
    events = [result.event for result in results]
    parent_lookup = _by_source_object(events).get
    # ALG-23 already decided which claims are about the same thing, across the parent walk that
    # joins an attachment to its covering mail. Reading its answer here is what puts the signed
    # PDF's amount and the email's amount in ONE comparison; re-deriving a subject per claim
    # would leave them apart, which is the exact defect the whole unit exists to catch.
    group_key = {(claim.event_id, claim.ordinal): group.group_key
                 for group in groups for claim in group.claims}
    # The prepared row per event, so an amount's receipt can be LOCATED rather than dropped:
    # `Money` carries no evidence list, and the text its offsets are measured against is the only
    # place a real span for it can come from.
    prepared = {result.event.event_id: result.prepared for result in results}
    lane = ConflictLane(
        grouper=ExtractionClaimGrouper(
            event_lookup=parent_lookup,
            prepared_for=lambda event: prepared.get(getattr(event, "event_id", None)),
            group_key_for=group_key.get),
        detected_at=detected_at)
    outcome: ConflictOutcome | None = None
    try:
        for result in results:
            if result.extraction is not None:
                outcome = lane.observe(result.event, result.extraction)
    except Exception:       # noqa: BLE001 — detection is downstream of capture, never above it
        _log.warning("conflict detection failed for a sweep of %d results", len(results),
                     exc_info=True)
        return None
    return outcome


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
             # L1.2.6 · does this run answer to the poll cadence?
             #   None  — ask the thread: the scheduler's tick does, a manual trigger does not.
             #           This is what every existing caller gets, and it is why pressing "Sync
             #           now" still reaches the provider two minutes after a sweep did.
             #   True  — gate it. An external cron driving /ingest/all wants this.
             #   False — never gate it.
             # The gate only ever applies to an INCREMENTAL run carrying a cursor store: a
             # backfill and a recovery re-scan are explicit acts with their own bounds and were
             # never on a cadence.
             respect_cadence: bool | None = None,
             #: The connection's own cadence override. `None` means "look it up", which is what
             #: every production caller wants; pass an int to decide it at the call site.
             cadence_override_seconds: int | None = None,
             _now: Callable[[], datetime] | None = None,
             # `domain -> coverage verdict`, computed ONCE for this org before the sweep starts
             # (platform/wiring.make_coverage_fn). Passing it here is what puts a non-null
             # `coverage_ready` on every event a sweep emits: the parameter existed on
             # `capture_event` from the beginning and this, the largest capture entry in the
             # system, never supplied it — so 100% of swept events carried None.
             coverage_fn=None,
             # S2 (L1.4), or None when this tenant is not activated. One lane per sweep, so its
             # T3 allowance is shared by every event of the sweep instead of being reset per
             # message — a per-event budget is not a budget.
             semantic=None,
             # L1.3.9-U5 (the TYPED route), as ONE bundle for the whole sweep, and NOT on the
             # same terms as `semantic` above: this lane runs for every tenant with a mapping,
             # activated or not, because it calls no model. The bundle carries only what the
             # pipeline cannot derive per event — the org's zone and the discovery store — so
             # `None` costs UTC and unpersisted discoveries, never the lane itself.
             structured=None,
             # S4 (L1.6), as ONE bundle, for the whole sweep. Its job here is L1.6.7-U2's org
             # baseline: what a typical contract costs at THIS company and which counterparties
             # matter to it. A per-ORG quantity, so it is read once (platform/wiring.make_esqe_stage)
             # and handed to every event, exactly like `coverage_fn` above and for the same reason
             # — a p50 over a year does not move inside one sweep, and computing it per message
             # would put a table scan on the ingestion path of every email.
             #
             # `None` is not "do not score": `capture_event` then falls back to
             # `OrgBaseline.cold_start`, which is what EVERY sweep did before this parameter
             # existed — the money term off an absolute ladder and every counterparty
             # `first_seen`, i.e. half of ALG-17's formula pinned to two constants.
             #
             # The bundle deliberately leaves `eval_time` unset: the frozen instant is per EVENT
             # (the lane's, else the message's own `occurred_at`) and `capture_event` fills it in.
             esqe=None,
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
    # The run's own start, taken once, from the injectable seam rather than a bare clock so the
    # ledger row and the cadence decision below cannot disagree about when "now" was.
    started_at = (_now or (lambda: datetime.now(timezone.utc)))()
    saved = None
    if mode == "recovery":
        since = started_at - timedelta(days=reconcile_days)
    elif cursor_store is not None and mode != "backfill":
        saved = cursor_store.get(org_id, connection_id, source)
        if saved is not None:
            cursor = cursor or saved.cursor
            since = saved.watermark

    # L1.2.6 · WHOSE TURN IT IS. Consulted here, in the one function every polling path shares,
    # because the alternative — asking at each of the six call sites — is five places to forget.
    # A connection that is not due costs ZERO provider calls and zero model calls: this returns
    # before the connector is touched, carrying the decision so the caller can say why.
    decision: PollDecision | None = None
    gate = in_scheduled_sweep() if respect_cadence is None else respect_cadence
    if cursor_store is not None and mode == "incremental" and gate:
        now_fn = _now or (lambda: datetime.now(timezone.utc))
        override = (cadence_override_seconds if cadence_override_seconds is not None
                    else _configured_override_seconds(org_id, connection_id))
        decision = poll_decision(
            org_id=org_id, connection_id=connection_id, source=source,
            last_success_at=saved.synced_at if saved is not None else None,
            watermark=saved.watermark if saved is not None else None,
            now=now_fn(), base_page_budget=max_pages, override_seconds=override)
        if not decision.due:
            _log.info("poll skipped: org=%s conn=%s source=%s not due until %s "
                      "(cadence %ss, origin=%s)", org_id, connection_id, source,
                      decision.next_run_at.isoformat(), decision.cadence.interval_seconds,
                      decision.cadence.origin)
            return SyncSummary(next_cursor=cursor, poll=decision, started_at=started_at)
        if decision.is_catch_up:
            # An outage is paid for in PAGES, once, resuming from the stored watermark — never by
            # re-reading history the watermark already covers.
            _log.warning("catch-up poll: org=%s conn=%s source=%s gap=%ss over %s interval(s); "
                         "page budget %s -> %s", org_id, connection_id, source,
                         decision.catch_up.gap_seconds, decision.catch_up.missed_intervals,
                         max_pages, decision.max_pages)
            max_pages = max(max_pages, decision.max_pages)
            if since is None and decision.catch_up.since is not None:
                # Only when there is NO watermark to resume from — a connection whose last poll
                # completed without seeing a single object. `since` is then the gap itself,
                # bounded to 30 days by `MAX_CATCH_UP_LOOKBACK_SECONDS` so a recovery can never
                # quietly become a full backfill. It cannot lose anything: everything older than
                # the last completed poll was already offered to that poll.
                since = decision.catch_up.since

    sync_mode = SyncMode.backfill if mode == "backfill" else SyncMode.incremental
    summary = SyncSummary(poll=decision, started_at=started_at)
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
                                            coverage_fn=coverage_fn, semantic=semantic,
                                            structured=structured,
                                            esqe=esqe, sync_mode=sync_mode)
                return raw, res, err

            # A re-read message brings its attachments back under NEW Gmail attachmentIds, which
            # the dedup key cannot see. Drop them here, before the parallel capture below can land
            # them a second time (`capture/landing/reread.py`); they count as duplicates.
            from genios_engine.capture.landing.reread import drop_reread_attachments
            objects, reread = drop_reread_attachments(batch.objects, org_id=org_id, repo=repo)
            summary.duplicate += reread

            # BATCH the S2 relevance gate for the whole page in a few LLM calls (prime the classifier's
            # cache) BEFORE per-event capture — turns ~25 gate calls/page into ~2. Best-effort: if the
            # classifier doesn't support priming or a batch fails, capture just calls it per-email.
            if objects and relevance is not None and hasattr(relevance, "prime"):
                try:
                    relevance.prime(objects)
                except Exception:      # noqa: BLE001 — never let batching break the sync
                    pass

            # D6 · L1.6.5's PAGE seam, for the poll door. `prime_relevance_page` names both
            # capture doors in its own docstring and only ONE of them called it: the webhook
            # (`connectors/push_ingest.ingest_pushed_objects`). This is the door every tenant is
            # actually served by, and without this line each ambiguous message on the page fell
            # to `RelevancePage.decide`'s per-event branch and bought its own LLM-5 call —
            # measured on an 18-message page: 12 prompts, 12 calls, 0 cache hits, against the
            # one prompt the seam exists to buy. Nothing functional went red, because the
            # per-event path returns the SAME verdicts; only the cost differed, which is why a
            # green suite hid it.
            #
            # `relevance` above is a DIFFERENT object — the legacy S2 gate classifier passed in
            # by the caller. Priming that one does not prime this one.
            #
            # Best-effort inside `prime_relevance_page` itself: a page that could not be primed
            # costs the door its batching, never its mail.
            if objects:
                prime_relevance_page(objects, semantic, sender_resolver)

            # capture the whole page CONCURRENTLY — DB round-trips overlap. Each email is independent,
            # so this changes nothing about WHAT is captured, only how fast.
            if objects:
                with ThreadPoolExecutor(max_workers=_CAPTURE_WORKERS) as ex:
                    captured = list(ex.map(_cap, objects))
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
                if res.extraction_parked is not None and parked_store is not None:
                    # S2 parks are separate from GATE parks: the event itself emitted, and this
                    # row exists so a transport failure can be retried and a schema refusal can
                    # be read. Dropping it because the event was fine would lose the only record
                    # that a message reached the model and came back unusable.
                    parked_store.add(res.extraction_parked)
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
    # ALG-23 (L1.5.0-U2) — group the sweep's claims by SUBJECT before anything compares them.
    summary.claim_groups = _assemble_groups(summary.results)
    # ALG-12 (L1.5.5) — compare them. Grouping decides what is about the same thing;
    # this decides whether those things agree.
    summary.conflicts = _detect_conflicts(summary.results, groups=summary.claim_groups,
                                          detected_at=_detected_at(semantic))
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
        # The FIRST round's start is the backfill's start; later rounds would report the last
        # page's, which is the one number a duration cannot be computed from.
        total.started_at = total.started_at or summary.started_at
        total.gated.extend(summary.gated)
        total.results.extend(summary.results)
        cursor = summary.next_cursor
        if not cursor:
            break
    total.next_cursor = cursor
    # Re-assembled over EVERY page, not merged per page: a reply on page two and the signed
    # attachment on page one are one claim group, and concatenating two per-page groupings would
    # leave them apart — the same across-events defect one level up.
    total.claim_groups = _assemble_groups(total.results)
    total.conflicts = _detect_conflicts(total.results, groups=total.claim_groups,
                                        detected_at=_detected_at(kw.get("semantic")))
    return total
