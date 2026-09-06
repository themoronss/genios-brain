from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe.qualification import (DropLedger, FloorStore,
                                                      QualificationOutcome, qualify_sweep)
from genios_engine.capture.landing.repository import SourceEventRepository
from genios_engine.capture.parked.store import ParkedStore, parked_from_trace
from genios_engine.capture.payload_store import RawPayloadStore
from genios_engine.capture.pipeline import (CaptureResult, capture_event,
                                            prime_relevance_page)
from genios_engine.capture.trace_store import TraceRepository
from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.source_event import SyncMode

# L1.2.5-U1 · ONE ingest for pushed objects — the webhook lane's half of "webhook and poll
# produce identical rows for the same message".
#
# THE DEFECT THIS FILE CLOSES. The webhook route called `capture_event` inline with four
# arguments — repo, trace_repo, payload_store, document_job_store — while the sweep
# (`capture/acquire/sync_runner.py:_cap`) called the same function with thirteen. A message that
# arrived by push therefore landed:
#
#   * with NO `mailbox_owner`, so `visibility_principals` was derived without the account that
#     owns the mailbox and the ACL on a pushed message did not match the ACL on the same polled
#     message;
#   * with NO `prepared_store`, so no `prepared_content` row existed — no clean text for S2 to
#     extract from and no offset map for an evidence span to align against;
#   * with NO `relevance` gate, so the always-on lane the customer actually experiences was the
#     LEAST guarded one;
#   * with NO `parked_store`, so a park outcome — the recoverable one — was recorded nowhere and
#     a poison object took the whole request down instead of being quarantined;
#   * with NO `sender_known`, so the gate's W-01 known-sender whitelist never fired on a push.
#
# WHY A UNIT AND NOT MORE KEYWORDS AT THE CALL SITE. The route did not omit those arguments on
# purpose; nobody was ever told what the full set was. A wiring spread across two call sites in
# two files drifts the moment either grows a parameter, which is exactly the history here. This
# module names the set ONCE, as a type, so "what the pipeline must be given" is a thing a caller
# can pass whole rather than a list it has to remember. `tests/capture/test_webhook_parity.py`
# compares the keywords this unit sends with the keywords the sweep sends, so a parameter added
# to one door and not the other is a failing test rather than a thinner row.
#
# Park bookkeeping mirrors the sweep's aggregation loop for the same reason: an outcome the sweep
# files and the push drops is a row that exists or not depending on which door the message used.


@dataclass(frozen=True)
class PushIngestWiring:
    """Everything L1 needs to treat a pushed object exactly as a polled one.

    Every field except `repo` is optional in the same way it is optional on the sweep: a caller
    that genuinely has no such store passes nothing, and the pipeline behaves as it does for that
    caller today. The point of the type is that the caller sees the whole set.
    """

    repo: SourceEventRepository
    trace_repo: TraceRepository | None = None
    payload_store: RawPayloadStore | None = None
    prepared_store: object | None = None
    document_job_store: object | None = None
    parked_store: ParkedStore | None = None
    relevance: object | None = None
    #: `RawObject -> bool`, the gate's W-01 known-sender whitelist. Same shape as the sweep's.
    sender_resolver: Callable[[RawObject], bool] | None = None
    mailbox_owner: str | None = None
    #: `domain -> coverage verdict`, computed once for the org by `make_coverage_fn`.
    coverage_fn: object | None = None
    semantic: object | None = None
    #: L1.3.9-U5's bundle for the TYPED route (`platform/wiring.make_structured_lane`). Here for
    #: the same reason `esqe` below is: a pushed HubSpot deal must resolve its close date in the
    #: same zone the SAME deal polled a minute later does, or one object has two close dates
    #: decided by which door it came through.
    structured: object | None = None
    #: S4 (L1.6) as ONE bundle — today, L1.6.7-U2's org baseline, computed once for the org by
    #: `platform/wiring.make_esqe_stage`. The sweep passes it as `run_sync(esqe=...)`; without it
    #: here a pushed message is scored against `OrgBaseline.cold_start` while the SAME message
    #: polled a minute later is scored against the org's own p50 — two importances for one
    #: message, decided by which door it came through.
    esqe: object | None = None
    #: L1.6.8's per-tenant floor and its drop ledger. The sweep qualifies at
    #: `api/routes._run_ledger`; the push door has no sync ledger to hang that off, so it does it
    #: here. `None` for either one means the door does not file — which is what it did before,
    #: and which is why a tenant on a webhook-driven source had NO answer to "why did I never see
    #: this?" while the same tenant's polled sources had one.
    floor_store: FloorStore | None = None
    drop_ledger: DropLedger | None = None
    #: A live push is by definition an incremental delivery; a drain says `backfill`. Chosen by
    #: the caller, never by the parser — which is why it is a field and not a constant.
    sync_mode: SyncMode = SyncMode.incremental
    #: Bounded retries per object before it is quarantined. The sweep's `_capture_bounded` uses 2.
    retries: int = 2


@dataclass(frozen=True)
class PushIngestOutcome:
    """What one push landed. `results` is in the order the objects were given — the primary
    object (the message/event/record) first, its attachments after it."""

    results: tuple[CaptureResult, ...]
    #: `source_object_id` of every object that still failed after `retries` and was quarantined.
    quarantined: tuple[str, ...]
    #: L1.6.8's verdicts for this push, or `None` when the caller wired no floor. Present on the
    #: outcome rather than only written to the ledger for the reason `SyncSummary.conflicts` is:
    #: a route that wants to say what it did with a payload cannot read it back out of a table it
    #: has no handle on.
    qualification: QualificationOutcome | None = None

    @property
    def primary(self) -> CaptureResult | None:
        """The message itself, or None when nothing survived — what the route answers with."""
        return self.results[0] if self.results else None


def _capture_bounded(raw: RawObject, *, retries: int, **kw) -> tuple[CaptureResult | None,
                                                                    Exception | None]:
    """capture_event with bounded retries. A poison object returns (None, error) so the caller
    quarantines it — one bad push must not 500 the endpoint, and must not vanish either."""
    err: Exception | None = None
    for _ in range(retries + 1):
        try:
            return capture_event(raw, **kw), None
        except Exception as e:      # noqa: BLE001 — deliberately broad; poison isolation
            err = e
    return None, err


def _file_parks(raw: RawObject, res: CaptureResult, *, org_id: str,
                parked_store: ParkedStore) -> None:
    """The sweep's park bookkeeping, for the push door. Two DIFFERENT parks can come out of one
    capture and both are filed: an S2 extraction park (the event emitted, the model came back
    unusable) and a GATE park (the event itself was held)."""
    if res.extraction_parked is not None:
        parked_store.add(res.extraction_parked)
    if res.outcome == "parked":
        reason = res.trace.records[-1].reason_code if res.trace.records else "unknown"
        parked_store.add(parked_from_trace(org_id, res.event.event_id, res.event.source,
                                           reason or "unknown", res.trace))


def ingest_pushed_objects(objects: tuple[RawObject, ...], *, org_id: str, connection_id: str,
                          wiring: PushIngestWiring) -> PushIngestOutcome:
    """Run every object of ONE pushed payload through the L1 pipeline the sweep runs.

    Plural because one payload is not one row: a Gmail message with an attachment is an
    `email_message` AND an `email_attachment`, and the document is usually the half carrying the
    contract. The webhook route landed `objects[0]` and dropped the rest.
    """
    prime_relevance_page(objects, wiring.semantic, wiring.sender_resolver)
    results: list[CaptureResult] = []
    quarantined: list[str] = []
    for raw in objects:
        sender_known = bool(wiring.sender_resolver(raw)) if wiring.sender_resolver else False
        res, err = _capture_bounded(
            raw, retries=wiring.retries, org_id=org_id, connection_id=connection_id,
            repo=wiring.repo, sender_known=sender_known, relevance=wiring.relevance,
            trace_repo=wiring.trace_repo, payload_store=wiring.payload_store,
            prepared_store=wiring.prepared_store,
            document_job_store=wiring.document_job_store,
            mailbox_owner=wiring.mailbox_owner, coverage_fn=wiring.coverage_fn,
            semantic=wiring.semantic, structured=wiring.structured, esqe=wiring.esqe,
            sync_mode=wiring.sync_mode)
        if res is None:
            quarantined.append(raw.source_object_id)
            if wiring.parked_store is not None:
                wiring.parked_store.add(ParkedEvent(
                    event_id=f"{raw.source}:{raw.source_object_id}", org_id=org_id,
                    source=raw.source, reason_code="poison_quarantine", stage="capture",
                    trace=[{"error": type(err).__name__, "detail": str(err)[:200]}]))
            continue
        results.append(res)
        if wiring.parked_store is not None:
            _file_parks(raw, res, org_id=org_id, parked_store=wiring.parked_store)
    outcome = PushIngestOutcome(results=tuple(results), quarantined=tuple(quarantined))
    return replace(outcome, qualification=_qualify(outcome, org_id=org_id, wiring=wiring))


def _qualify(outcome: PushIngestOutcome, *, org_id: str,
             wiring: PushIngestWiring) -> QualificationOutcome | None:
    """L1.6.8 for a PUSH, on exactly the sweep's terms.

    `qualify_sweep` is a function over anything carrying `.results` (and, optionally,
    `.conflicts`) — `persist_sweep_conflicts`'s own shape — so a `PushIngestOutcome` is a sweep
    of one payload as far as the floor is concerned, and the door does not have to grow a second
    qualification path to say so. It reads the score `capture_event` already stamped on each
    result, never a second one.

    `None` when no floor is wired, which is the honest answer: a caller with no ledger has
    decided nothing and must not be reported as having qualified anything. Never raises —
    `qualify_sweep` is downstream of capture and returns an empty outcome for a summary it could
    not read, exactly as it does for the sweep.
    """
    if wiring.floor_store is None and wiring.drop_ledger is None:
        return None
    return qualify_sweep(outcome, org_id=org_id, floor_store=wiring.floor_store,
                         ledger=wiring.drop_ledger)
