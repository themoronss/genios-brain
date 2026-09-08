"""L1.3.8-U1 · Refetch of parked stubs — the drain that actually goes and gets the bytes.

WHAT WAS BROKEN. `connectors/composio.py::_attachment_stub` emits a real, named attachment with
``body: ""`` when the download fails or the format is unreadable, so the gate PARKS it (DOC-02
unsupported / DOC-04 ocr review / DOC-05 fetch failed / DOC-06 no engine) instead of dropping it
silently. That was half a fix. `parked/drain.py` then classified those four reasons as NEEDS
REFETCH, wrote the count into its report, and moved on — because re-running the pipeline over a
stub re-parks the stub. **No code path ever asked the connector for the bytes again.** A contract
that failed to download on first sync was lost permanently, quietly, and the only evidence was a
number in a drain summary nobody reads. The attachment is the most intelligence-dense object in an
email; this was the single largest silent loss in Layer 1.

THE SHAPE OF THE FIX, and why it is a queue rather than a loop.

    claim ──lease──▶ fetch ──▶ extract ──▶ recover  (payload + prepared text + outcome='emitted')
      │                 │          │
      │                 │          └── unreadable ─▶ WAIT a day (capability: only our code fixes
      │                 │                                        it, and code ships)
      │                 └── gone ──────────────────▶ DEAD LETTER (permanent: no bytes will come)
      │                 └── blipped ───────────────▶ WAIT (transient: the ladder)
      └── attempts exhausted ─────────────────────▶ DEAD LETTER (carrying the kind it died of)

A TERMINAL STATE IS REACHABLE ONLY BY A REAL REASON, and there are exactly two: the provider said
the bytes are gone, or the ladder ran out. Everything else waits. That reads like a detail and is
not: `aging()` — the G2 number — counts `status='pending'`, so a dead letter makes the metric look
BETTER. Any classification that is too eager therefore hides its own damage, which is why
`refetch_policy.classify_fetch_error` resolves ties toward TRANSIENT and why a capability gap
(bytes we hold and no engine here can read) defers on a slow clock instead of dying: it is a fact
about this deployment at one instant, and the heartbeat drains with `ocr=None`, so the first tick
would otherwise have written off every DOC-02/04/06 park in the backlog in a single pass.

Three properties are non-negotiable and each one is structural rather than careful:

**Bounded.** The claim increments `refetch_attempts` BEFORE the network call and pushes
`refetch_next_attempt_at` out by a lease. A drain killed mid-fetch therefore still burns an
attempt, so a document that crashes the process cannot be retried forever — which is exactly the
failure a naive "select pending, try, update on success" loop has, and it is invisible until the
day it isn't.

**Idempotent.** Every write is an overwrite of a keyed row, and the one non-idempotent transition
— park → emitted — is guarded by `outcome='parked'`, so a second recovery of the same event
updates nothing. Two drains racing on one row cannot both claim it (`for update … skip locked`).

**Observable.** G2 asserts *0 attachments stuck in `NEEDS_REFETCH` over 1h*. "Stuck" is therefore
a query, not a feeling: `aging()` returns, per reason and object type, how many are pending, how
old the oldest is in whole seconds, and how many are past the stuck threshold. `dead_letters()` is
the admin-console surface the spec asks for — the queue of things we stopped trying, each with the
reason we stopped. A dead letter is a decision; an empty `status='pending'` backlog that nobody
can age is an accident.

WHY A PORT (`RefetchQueue`) RATHER THAN SQL IN THE LOOP. Everything interesting about this
component is a state machine, and a state machine tested through a database is a state machine
tested slowly, partially, and only where a server is available. The decisions are pure
(`refetch_policy.py`), the persistence is a protocol with two implementations, and the loop below
is the same code in both — so the hermetic gate test drives the full ladder including the
five-failure dead-letter, and the `pg` test proves the SQL that ladder rides on.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Protocol

from sqlalchemy import text

from genios_engine.capture.documents.base import BP_FULL, DocumentResult, DocumentStatus
from genios_engine.capture.parked.refetch_policy import (DEFAULT_POLICY, AttachmentRef,
                                                         AttemptFailure, AttemptResult,
                                                         NEEDS_REFETCH, ParkStatus,
                                                         RefetchAction, RefetchCandidate,
                                                         RefetchPlan, RefetchPolicy,
                                                         RefetchSettlement, classify_fetch_error,
                                                         plan_refetch, settle_attempt,
                                                         settle_without_attempt)
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.platform.crypto import decrypt, encrypt
from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.parked.refetch")

__all__ = [
    "AttachmentFetcher", "DeadLetter", "InMemoryRefetchQueue", "PostgresRefetchQueue",
    "ReasonAging", "RecoveredDocument", "RefetchAging", "RefetchQueue", "RefetchReport",
    "read_aging",
    "recovered_payload_ttl_days", "refetch_parked_attachments",
]

#: A recovered attachment is no longer a review item — it is an emitted event with real content,
#: so its raw payload gets the ordinary emitted TTL rather than the long parked one. Kept as a
#: named constant next to `pipeline._EMITTED_PAYLOAD_TTL_DAYS` rather than imported, because the
#: pipeline's constant is private and reaching through the underscore is how two retention clocks
#: end up silently coupled.
RECOVERED_PAYLOAD_TTL_DAYS = 30

#: The object type this unit resolves. Drive and Notion documents park under the same DOC-* codes
#: and are deliberately out of scope: their `source_object_id` is a file id with no message to
#: hang it off, so they need their own resolver rather than a special case inside this one.
ATTACHMENT_OBJECT_TYPE = "email_attachment"


def recovered_payload_ttl_days() -> int:
    """The raw-payload TTL a recovered attachment is stored under, in whole days."""
    return RECOVERED_PAYLOAD_TTL_DAYS


# ── ports ────────────────────────────────────────────────────────────────────────────────────

class AttachmentFetcher(Protocol):
    """The one thing this unit needs a connector to do.

    Deliberately NOT `SourceConnector`: a refetch does not sync, paginate or watermark, and
    depending on the whole connector interface would make the fake in a test a lie about how much
    of it matters. `ComposioGmailConnector.fetch_attachment` satisfies this, and unlike its
    private `_attachment_bytes` sibling it RAISES rather than returning ``b""`` — the ladder has
    to tell "the network blipped" from "the message was deleted", and an empty bytes object cannot
    say either.
    """

    def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes: ...


#: Resolves the tenant connector for one parked attachment, or None when the org has no live
#: connection for that source. A callable rather than a registry so the drain stays unit-testable
#: and so the caller — which is the only thing that knows about connections, credentials and the
#: Composio account — keeps that knowledge.
ConnectorFactory = Callable[[RefetchCandidate], "AttachmentFetcher | None"]

#: `documents/native.py::process_document`, narrowed to the arguments this unit passes. Injected
#: so the drain's tests do not depend on a PDF parser, an OCR toolchain, or on which of those two
#: packages lands first in this wave.
DocumentExtractor = Callable[..., DocumentResult]


@dataclass(frozen=True)
class RecoveredDocument:
    """Everything a successful refetch produces, ready to persist.

    Assembled by the orchestrator so that BOTH queue implementations write the same thing, and so
    the PII masking that ingestion applies is applied here too — a document recovered without
    `preprocess` would put an unmasked phone number into `prepared_content`, which is the one
    place Layer 1 promises there is none.
    """

    event_id: str
    org_id: str
    filename: str
    mime: str
    payload: dict[str, Any]          # the raw object, patched with the recovered body
    prepared: PreparedContent
    text_chars: int
    native_parse_used: bool
    ocr_used: bool
    ocr_engine: str | None
    ocr_pages: int
    confidence_bp: int | None        # integer basis points; never a float (documents/base.py)
    status: str


@dataclass(frozen=True)
class ReasonAging:
    """One row of the backlog: how many parks of this reason and object type are pending, and how
    old the oldest of them is. `oldest_age_seconds` is a whole number of seconds computed by the
    database, so nothing here rounds."""

    reason_code: str
    object_type: str
    pending: int
    stuck: int
    oldest_age_seconds: int


@dataclass(frozen=True)
class RefetchAging:
    """The G2 surface. `stuck` is the number the gate asserts is zero."""

    rows: tuple[ReasonAging, ...]
    pending: int
    stuck: int
    stuck_after_seconds: int

    @property
    def stuck_attachments(self) -> int:
        """Only the email attachments, which is what G2 names."""
        return sum(r.stuck for r in self.rows if r.object_type == ATTACHMENT_OBJECT_TYPE)


@dataclass(frozen=True)
class DeadLetter:
    """One attachment this unit stopped trying to recover, and why — the admin-console row."""

    event_id: str
    org_id: str
    reason_code: str
    source_object_id: str
    attempts: int
    last_error: str | None
    last_attempt_at: datetime | None
    parked_at: datetime
    #: `AttemptFailure.value` — the KIND of failure that ended it, not just its last message.
    #: The policy computes this on every settlement and it used to be thrown away at the write,
    #: which left the console with a free-text column and no way to answer the only question an
    #: operator has: is this queue full of files we cannot READ (wire an engine, then requeue) or
    #: of files we cannot FETCH (look at the connection)? A message can be truncated, translated
    #: or empty; the kind is a value.
    failure_kind: str | None = None


@dataclass(frozen=True)
class RefetchReport:
    """What one drain cycle did. Counts rather than a bare total, because "we ran" and "we
    recovered nothing because every connector was missing" must not look the same."""

    claimed: int = 0
    recovered: int = 0
    dead_lettered: int = 0
    retry_scheduled: int = 0
    released: int = 0
    text_chars_recovered: int = 0
    failures_by_kind: tuple[tuple[str, int], ...] = ()


class RefetchQueue(Protocol):
    """The persistence port. Two implementations, one loop."""

    def claim_due(self, *, eval_time: datetime, policy: RefetchPolicy,
                  org_id: str | None = None, limit: int = 50) -> tuple[RefetchCandidate, ...]: ...

    def load_payload(self, candidate: RefetchCandidate) -> dict[str, Any]: ...

    def persist_recovery(self, settlement: RefetchSettlement,
                         recovered: RecoveredDocument) -> None: ...

    def persist_settlement(self, settlement: RefetchSettlement) -> None: ...

    def aging(self, *, eval_time: datetime, policy: RefetchPolicy,
              org_id: str | None = None) -> RefetchAging: ...

    def dead_letters(self, *, org_id: str | None = None,
                     limit: int = 100) -> tuple[DeadLetter, ...]: ...

    def requeue_dead_letters(self, *, eval_time: datetime, org_id: str | None = None,
                             reason_codes: frozenset[str] | None = None,
                             not_attempted_since: datetime | None = None) -> int: ...


# ── the orchestrator (the public callable of L1.3.8-U1) ──────────────────────────────────────

def refetch_parked_attachments(queue: RefetchQueue, *, connector_for: ConnectorFactory,
                               eval_time: datetime, policy: RefetchPolicy = DEFAULT_POLICY,
                               org_id: str | None = None, limit: int = 50,
                               extract: DocumentExtractor | None = None, ocr: Any = None,
                               mask_phone: bool = False) -> RefetchReport:
    """One drain cycle: claim due parked attachments, fetch them, and settle every one.

    Returns a report rather than logging one, so a caller (the sync route, a cron, a test) can
    assert on what happened. Never raises for one bad attachment: a fetch or an extractor that
    blows up settles that row as a failed attempt and the cycle continues — the whole point of the
    component is that one unreadable file cannot stop the others from being recovered.
    """
    extractor = extract if extract is not None else _default_extractor
    claimed = queue.claim_due(eval_time=eval_time, policy=policy, org_id=org_id, limit=limit)

    recovered_count = 0
    dead = 0
    retried = 0
    released = 0
    chars = 0
    failures: dict[str, int] = {}

    for candidate in claimed:
        payload = queue.load_payload(candidate)
        enriched = _with_payload_facts(candidate, payload)
        plan = plan_refetch(enriched, eval_time=eval_time, policy=policy)

        if plan.action is not RefetchAction.ATTEMPT:
            settlement = settle_without_attempt(plan, eval_time=eval_time, policy=policy)
            queue.persist_settlement(settlement)
            if settlement.status is ParkStatus.DEAD_LETTER:
                dead += 1
                failures[AttemptFailure.PERMANENT.value] = \
                    failures.get(AttemptFailure.PERMANENT.value, 0) + 1
            else:
                released += 1
            continue

        result, recovered = _attempt(plan, payload=payload, connector_for=connector_for,
                                     extract=extractor, ocr=ocr, mask_phone=mask_phone)
        settlement = settle_attempt(plan, result, eval_time=eval_time, policy=policy)
        if settlement.status is ParkStatus.RECOVERED and recovered is not None:
            queue.persist_recovery(settlement, recovered)
            recovered_count += 1
            chars += recovered.text_chars
            continue

        queue.persist_settlement(settlement)
        if result.failure is not None:
            failures[result.failure.value] = failures.get(result.failure.value, 0) + 1
        if settlement.status is ParkStatus.DEAD_LETTER:
            dead += 1
        else:
            retried += 1

    report = RefetchReport(claimed=len(claimed), recovered=recovered_count, dead_lettered=dead,
                           retry_scheduled=retried, released=released,
                           text_chars_recovered=chars,
                           failures_by_kind=tuple(sorted(failures.items())))
    if report.claimed:
        _log.info("attachment refetch: claimed=%d recovered=%d dead_lettered=%d retry=%d",
                  report.claimed, report.recovered, report.dead_lettered, report.retry_scheduled)
    return report


def _default_extractor(*, mime: str, data: bytes, filename: str, ocr: Any) -> DocumentResult:
    """The real extractor, imported at call time.

    Late import on purpose: `documents/native.py` pulls in PDF and OCR machinery, and this module
    is imported by the report script and by the API route, neither of which should pay for a PDF
    parser to ask how many attachments are stuck.
    """
    from genios_engine.capture.documents.native import process_document
    return process_document(mime=mime, data=data, filename=filename, ocr=ocr)


def _with_payload_facts(candidate: RefetchCandidate, payload: dict[str, Any]) -> RefetchCandidate:
    """Fill in the filename and mime the ledger does not carry.

    Both live inside the encrypted raw payload (`subject` is the filename for an attachment
    event — see `_attachment_stub`), and both are load-bearing: the mime chooses the extractor,
    and the filename is how `parse_attachment_ref` recognises the case where the composite id's
    second half is a FILENAME rather than a provider attachment id. Without it that row is fetched
    with a filename as an id, five times, and dead-letters for the wrong reason.
    """
    filename = candidate.filename or _as_str(payload.get("subject"))
    mime = candidate.mime or _as_str(payload.get("mime"))
    return replace(candidate, filename=filename, mime=mime)


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _attempt(plan: RefetchPlan, *, payload: dict[str, Any], connector_for: ConnectorFactory,
             extract: DocumentExtractor, ocr: Any,
             mask_phone: bool) -> tuple[AttemptResult, RecoveredDocument | None]:
    """Fetch and extract one attachment. Returns what happened; writes nothing."""
    candidate = plan.candidate
    ref = plan.ref
    if ref is None or not ref.is_fetchable:            # plan_refetch guarantees this; be explicit
        return AttemptResult(ok=False, failure=AttemptFailure.PERMANENT,
                             error="attachment reference is not addressable"), None

    try:
        fetcher = connector_for(candidate)
    except Exception as exc:                            # noqa: BLE001 — a broken factory is one row
        # NEVER classified. The factory resolves the TENANT'S CONNECTION out of our own registry,
        # before a provider has been asked anything, so whatever it raises is a fact about this
        # process — a connection row being rewritten by a reconnect, a registry not yet warm, a
        # credential mid-rotation. Feeding its message through the provider-error table is how a
        # `KeyError: connection not found` came to mean "this attachment no longer exists" and
        # dead-lettered an org's whole backlog on one tick.
        return AttemptResult(ok=False, failure=AttemptFailure.TRANSIENT,
                             error=f"connector factory raised: {_describe(exc)}"[:400]), None
    if fetcher is None:
        # Not terminal: a disconnected source is usually reconnected. The ladder bounds it.
        return AttemptResult(ok=False, failure=AttemptFailure.TRANSIENT,
                             error=f"no live connector for source {candidate.source!r}"), None

    try:
        data = fetcher.fetch_attachment(ref.message_id, ref.attachment_id or "")
    except Exception as exc:                            # noqa: BLE001 — classified, then bounded
        return _failed(_describe(exc)), None
    if not data:
        return AttemptResult(ok=False, failure=AttemptFailure.TRANSIENT,
                             error="provider returned no attachment bytes"), None

    filename = candidate.filename or ref.filename or "attachment"
    mime = candidate.mime or ""
    try:
        doc = extract(mime=mime, data=data, filename=filename, ocr=ocr)
    except Exception as exc:                            # noqa: BLE001 — an unreadable file, not a crash
        return AttemptResult(ok=False, byte_count=len(data), failure=AttemptFailure.CAPABILITY,
                             error=f"extractor raised: {_describe(exc)}"), None

    body = doc.text or ""
    if doc.status != DocumentStatus.ACCEPTED.value or not body.strip():
        # We HAVE the bytes and still cannot use them. Nothing about the ATTACHMENT will change,
        # so retrying it on the ten-minute network ladder is a lie about progress — but our
        # toolchain does change, so the policy defers this on `capability_backoff` rather than
        # ending it, and the row drains itself the day an engine or a parser lands.
        detail = doc.detail or "no usable text"
        return AttemptResult(ok=False, byte_count=len(data), failure=AttemptFailure.CAPABILITY,
                             error=f"{doc.status}: {detail}"), None

    return (AttemptResult(ok=True, text_chars=len(body), byte_count=len(data)),
            _build_recovery(candidate, payload=payload, doc=doc, filename=filename, mime=mime,
                            mask_phone=mask_phone))


def _failed(message: str) -> AttemptResult:
    """A fetch failure, classified by what the provider said."""
    return AttemptResult(ok=False, failure=classify_fetch_error(message), error=message[:400])


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _build_recovery(candidate: RefetchCandidate, *, payload: dict[str, Any], doc: DocumentResult,
                    filename: str, mime: str, mask_phone: bool) -> RecoveredDocument:
    """Patch the stub's payload with the text we just extracted, and re-derive the L1→L2 seam.

    The payload is PATCHED rather than rebuilt because the stub carries facts a refetch cannot
    reproduce: the recipients, the parent message id, the subject. Rebuilding it would recover the
    document and lose the conversation it belonged to.

    `preprocess` is re-run because `prepared_content` is what L2 reads (`context/runner.py::_pull`
    selects `pc.clean_text`) — a recovery that updated only the raw payload would put the contract
    in the database and still not put it in front of the extractor. The subject is prepended and
    masked WITH the body exactly as `pipeline.capture_event` does it; the HTML strip that pipeline
    applies is deliberately NOT repeated, because document text has already been through a parser
    and running an HTML stripper over a contract's prose is a way to lose an angle bracket.
    """
    recovered_payload = dict(payload)
    recovered_payload["subject"] = payload.get("subject") or filename
    recovered_payload["body"] = doc.text
    recovered_payload["mime"] = payload.get("mime") or mime
    recovered_payload["has_attachment"] = True
    recovered_payload["document"] = {
        "status": doc.status, "native_parse_used": doc.native_parse_used,
        "ocr_used": doc.ocr_used, "ocr_engine": doc.ocr_engine, "ocr_pages": doc.ocr_pages,
        "confidence_bp": doc.confidence_bp, "detail": doc.detail,
        "recovered_by": "l1_3_8_attachment_resolver",
    }
    subject = str(recovered_payload["subject"])
    full_text = f"{subject}\n\n{doc.text}" if subject else doc.text
    prepared = preprocess(full_text, event_id=candidate.event_id, mask_phone=mask_phone)
    return RecoveredDocument(
        event_id=candidate.event_id, org_id=candidate.org_id, filename=filename,
        mime=recovered_payload["mime"] or "", payload=recovered_payload, prepared=prepared,
        text_chars=len(doc.text), native_parse_used=doc.native_parse_used,
        ocr_used=doc.ocr_used, ocr_engine=doc.ocr_engine, ocr_pages=doc.ocr_pages,
        confidence_bp=doc.confidence_bp, status=doc.status)


# ── in-memory queue (the hermetic implementation) ────────────────────────────────────────────

class InMemoryRefetchQueue:
    """The queue with the database taken out, and NOTHING else.

    It implements the same lease — increment then hide — and the same `outcome='parked'` guard on
    recovery, because a fake that is easier to satisfy than the real thing tests the fake. What it
    does not implement is concurrency: `skip locked` has no meaning in one process, so the `pg`
    test is the one that proves two drains cannot claim the same row.
    """

    def __init__(self) -> None:
        self.candidates: dict[str, RefetchCandidate] = {}
        self.payloads: dict[str, dict[str, Any]] = {}
        self.outcomes: dict[str, str] = {}              # event_id -> source_events.outcome
        self.recovered: dict[str, RecoveredDocument] = {}
        self.settlements: list[RefetchSettlement] = []
        self.last_attempt_at: dict[str, datetime] = {}

    def add(self, candidate: RefetchCandidate, *, payload: dict[str, Any] | None = None,
            outcome: str = "parked") -> None:
        self.candidates[candidate.event_id] = candidate
        self.payloads[candidate.event_id] = dict(payload or {})
        self.outcomes[candidate.event_id] = outcome

    def claim_due(self, *, eval_time: datetime, policy: RefetchPolicy,
                  org_id: str | None = None, limit: int = 50) -> tuple[RefetchCandidate, ...]:
        due: list[RefetchCandidate] = []
        for candidate in sorted(self.candidates.values(), key=lambda c: c.parked_at):
            if len(due) >= limit:
                break
            if org_id is not None and candidate.org_id != org_id:
                continue
            if candidate.status != ParkStatus.PENDING.value:
                continue
            if candidate.reason_code not in NEEDS_REFETCH:
                continue
            if candidate.object_type != ATTACHMENT_OBJECT_TYPE:
                continue
            # No attempt bound here either — `plan_refetch` owns it. A fake that filtered rows
            # the real claim admits would be easier to satisfy than the thing it stands in for,
            # which is the one property this class exists to avoid. See `_CLAIM_SQL`.
            if eval_time - candidate.parked_at < policy.min_park_age:
                continue
            if candidate.next_attempt_at is not None and candidate.next_attempt_at > eval_time:
                continue
            # LEASE: burn the attempt and hide the row before the caller does any I/O.
            self.candidates[candidate.event_id] = replace(
                candidate, attempts=candidate.attempts + 1,
                next_attempt_at=eval_time + policy.lease)
            self.last_attempt_at[candidate.event_id] = eval_time
            due.append(candidate)                       # the row AS IT WAS when we decided
        return tuple(due)

    def load_payload(self, candidate: RefetchCandidate) -> dict[str, Any]:
        return dict(self.payloads.get(candidate.event_id) or {})

    def persist_settlement(self, settlement: RefetchSettlement) -> None:
        self.settlements.append(settlement)
        current = self.candidates.get(settlement.event_id)
        if current is None:
            return
        self.candidates[settlement.event_id] = replace(
            current, status=settlement.status.value, attempts=settlement.attempts,
            next_attempt_at=settlement.next_attempt_at)
        self.last_attempt_at[settlement.event_id] = settlement.last_attempt_at

    def persist_recovery(self, settlement: RefetchSettlement,
                         recovered: RecoveredDocument) -> None:
        self.persist_settlement(settlement)
        self.payloads[recovered.event_id] = dict(recovered.payload)
        self.recovered[recovered.event_id] = recovered
        if self.outcomes.get(recovered.event_id) == "parked":
            self.outcomes[recovered.event_id] = "emitted"

    def aging(self, *, eval_time: datetime, policy: RefetchPolicy,
              org_id: str | None = None) -> RefetchAging:
        buckets: dict[tuple[str, str], list[RefetchCandidate]] = {}
        for candidate in self.candidates.values():
            if org_id is not None and candidate.org_id != org_id:
                continue
            if candidate.status != ParkStatus.PENDING.value:
                continue
            if candidate.reason_code not in NEEDS_REFETCH:
                continue
            buckets.setdefault((candidate.reason_code, candidate.object_type), []).append(candidate)
        rows = []
        for (reason, object_type), items in sorted(buckets.items()):
            oldest = min(c.parked_at for c in items)
            stuck = sum(1 for c in items if eval_time - c.parked_at > policy.stuck_after)
            rows.append(ReasonAging(reason_code=reason, object_type=object_type,
                                    pending=len(items), stuck=stuck,
                                    oldest_age_seconds=_whole_seconds(eval_time - oldest)))
        return RefetchAging(rows=tuple(rows), pending=sum(r.pending for r in rows),
                            stuck=sum(r.stuck for r in rows),
                            stuck_after_seconds=_whole_seconds(policy.stuck_after))

    def dead_letters(self, *, org_id: str | None = None,
                     limit: int = 100) -> tuple[DeadLetter, ...]:
        out = [DeadLetter(event_id=c.event_id, org_id=c.org_id, reason_code=c.reason_code,
                          source_object_id=c.source_object_id, attempts=c.attempts,
                          last_error=self._last_error(c.event_id),
                          last_attempt_at=self.last_attempt_at.get(c.event_id),
                          parked_at=c.parked_at,
                          failure_kind=self._failure_kind(c.event_id))
               for c in sorted(self.candidates.values(), key=lambda c: c.parked_at)
               if c.status == ParkStatus.DEAD_LETTER.value
               and (org_id is None or c.org_id == org_id)]
        return tuple(out[:limit])

    def requeue_dead_letters(self, *, eval_time: datetime, org_id: str | None = None,
                             reason_codes: frozenset[str] | None = None,
                             not_attempted_since: datetime | None = None) -> int:
        reasons = reason_codes if reason_codes is not None else NEEDS_REFETCH
        n = 0
        for event_id, candidate in list(self.candidates.items()):
            if candidate.status != ParkStatus.DEAD_LETTER.value:
                continue
            if org_id is not None and candidate.org_id != org_id:
                continue
            if candidate.reason_code not in reasons:
                continue
            if not_attempted_since is not None:
                last = self.last_attempt_at.get(event_id)
                if last is not None and last >= not_attempted_since:
                    continue
            self.candidates[event_id] = replace(candidate, status=ParkStatus.PENDING.value,
                                                attempts=0, next_attempt_at=None)
            # The kind goes with the ladder it described. A requeued row that kept its old
            # `capability` stamp would report a verdict about a run that no longer happened.
            self.settlements = [s for s in self.settlements if s.event_id != event_id]
            n += 1
        return n

    def _last_error(self, event_id: str) -> str | None:
        settlement = self._last_settlement(event_id)
        return settlement.last_error if settlement else None

    def _failure_kind(self, event_id: str) -> str | None:
        settlement = self._last_settlement(event_id)
        if settlement is None or settlement.failure is None:
            return None
        return settlement.failure.value

    def _last_settlement(self, event_id: str) -> RefetchSettlement | None:
        for settlement in reversed(self.settlements):
            if settlement.event_id == event_id:
                return settlement
        return None


def _confidence_column(confidence_bp: int | None) -> Decimal | None:
    """Integer basis points -> the `numeric(4,3)` `document_jobs.avg_confidence` declares.

    `Decimal(9100) / Decimal(10000)` is exactly 0.9100; `9100 / 10000` would hand psycopg a float
    to round on its way into a three-decimal column. Same conversion, same reasoning and the same
    single place-of-narrowing rule as `documents/store.py::_confidence_column` — restated rather
    than imported because that one is private to its package and takes a raw job dict.
    """
    if confidence_bp is None:
        return None
    return Decimal(int(confidence_bp)) / Decimal(BP_FULL)


def _whole_seconds(delta: timedelta) -> int:
    """A timedelta in seconds as an INTEGER. `total_seconds()` returns a float and every age in
    this component is reported, compared and stored as a whole number."""
    return delta.days * 86_400 + delta.seconds


# ── postgres queue ───────────────────────────────────────────────────────────────────────────

#: THE ATTEMPT BOUND IS NOT HERE, and its absence is deliberate.
#:
#: This claim used to carry `pe.refetch_attempts < :max_attempts`, which duplicated the terminal
#: condition `plan_refetch` already owns — and duplicating it made the original UNREACHABLE. A
#: drain killed between the lease and the settlement on the FINAL attempt leaves a row at
#: `status='pending'` with `refetch_attempts = max_attempts`; under the old filter no later
#: heartbeat could ever select it, so it stayed pending forever. `read_aging` counts pending rows
#: by reason code and never looks at the attempt count, so that row was STUCK in the one number
#: G2 asserts is zero, with nothing in the system able to clear it. `RefetchPolicy.lease`'s own
#: docstring promises the opposite: *"a process that dies mid-fetch leaves a row that is bounded
#: and re-attemptable, not one that is invisible forever."*
#:
#: Claiming a bounded-out row costs one lease and no I/O: `plan_refetch` returns DEAD_LETTER
#: before the connector is touched, `settle_without_attempt` writes the terminal state with the
#: PRE-lease attempt count, and the row leaves `pending` for good on the next tick.
_CLAIM_SQL = """
with due as (
    select pe.event_id
      from parked_events pe
      join source_events se
        on se.event_id = pe.event_id and se.org_id = pe.org_id
     where pe.status = 'pending'
       and pe.reason_code = any(:reasons)
       and se.object_type = :object_type
       and pe.created_at <= :ready_before
       and (pe.refetch_next_attempt_at is null or pe.refetch_next_attempt_at <= :now)
       {org_filter}
     order by pe.created_at asc
     limit :lim
       for update of pe skip locked
), claimed as (
    update parked_events p
       set refetch_attempts          = p.refetch_attempts + 1,
           refetch_first_attempt_at  = coalesce(p.refetch_first_attempt_at, :now),
           refetch_last_attempt_at   = :now,
           refetch_next_attempt_at   = :lease_until
      from due
     where p.event_id = due.event_id
 returning p.event_id, p.org_id, p.reason_code, p.created_at, p.refetch_attempts
)
select c.event_id, c.org_id, c.reason_code, c.created_at, c.refetch_attempts,
       se.object_type, se.source, se.source_object_id, se.parent_object_id, se.connection_id
  from claimed c
  join source_events se on se.event_id = c.event_id
 order by c.created_at asc
"""


def read_aging(conn, *, eval_time: datetime, policy: RefetchPolicy = DEFAULT_POLICY,
               org_id: str | None = None) -> RefetchAging:
    """The NEEDS_REFETCH backlog, aged, over an existing connection.

    A free function taking a connection rather than a method taking a URL because the G2 report
    script (`scripts/l1_s1_report.py`) runs every one of its queries inside ONE transaction it has
    declared `read only` at the server. A helper that opened its own connection would run outside
    that declaration, which is the difference between a script that is read-only and a script that
    intends to be.

    Ages are computed by the database as whole seconds (`extract(epoch …)::bigint`), so nothing
    here rounds and nothing here is a float.
    """
    where_org = "and pe.org_id = :org" if org_id else ""
    params: dict[str, Any] = {
        "reasons": sorted(NEEDS_REFETCH), "now": eval_time,
        "stuck_before": eval_time - policy.stuck_after,
    }
    if org_id:
        params["org"] = org_id
    rows = conn.execute(text(
        "select pe.reason_code, coalesce(se.object_type, 'unknown') as object_type, "
        "       count(*) as pending, "
        "       count(*) filter (where pe.created_at < :stuck_before) as stuck, "
        "       cast(extract(epoch from (:now - min(pe.created_at))) as bigint) as age "
        "  from parked_events pe "
        "  left join source_events se on se.event_id = pe.event_id "
        " where pe.status = 'pending' and pe.reason_code = any(:reasons) "
        f"  {where_org} "
        " group by pe.reason_code, coalesce(se.object_type, 'unknown') "
        " order by pending desc, pe.reason_code asc"), params).fetchall()
    aging_rows = tuple(ReasonAging(reason_code=r.reason_code, object_type=r.object_type,
                                   pending=int(r.pending), stuck=int(r.stuck),
                                   oldest_age_seconds=int(r.age or 0)) for r in rows)
    return RefetchAging(rows=aging_rows, pending=sum(r.pending for r in aging_rows),
                        stuck=sum(r.stuck for r in aging_rows),
                        stuck_after_seconds=_whole_seconds(policy.stuck_after))


class PostgresRefetchQueue:
    """The real queue. Holds the crypto key because a recovery rewrites the encrypted raw payload,
    which is the same reason `PostgresRawPayloadStore` holds one."""

    def __init__(self, database_url: str, crypto_key: str) -> None:
        self._engine = get_engine(database_url)
        self._key = crypto_key

    # -- claim ---------------------------------------------------------------------------------
    def claim_due(self, *, eval_time: datetime, policy: RefetchPolicy,
                  org_id: str | None = None, limit: int = 50) -> tuple[RefetchCandidate, ...]:
        """Lease up to `limit` due parks and return them AS THEY WERE before the lease.

        The returned `attempts` is one less than the column now holds, on purpose: the caller
        plans against the state it decided on, so `plan.attempt_number` equals the attempt this
        row is actually making and the settlement it writes cannot double-count. `skip locked`
        is what makes two drains — a cron and an operator's manual run — safe to overlap.
        """
        sql = _CLAIM_SQL.format(org_filter="and pe.org_id = :org" if org_id else "")
        params: dict[str, Any] = {
            # No `max_attempts` bind: the ladder's terminal condition lives in `plan_refetch`,
            # and stating it here too is what made that branch unreachable. See `_CLAIM_SQL`.
            "reasons": sorted(NEEDS_REFETCH), "object_type": ATTACHMENT_OBJECT_TYPE,
            "ready_before": eval_time - policy.min_park_age,
            "now": eval_time, "lease_until": eval_time + policy.lease, "lim": limit,
        }
        if org_id:
            params["org"] = org_id
        with self._engine.begin() as c:
            rows = c.execute(text(sql), params).fetchall()
        return tuple(
            RefetchCandidate(
                event_id=r.event_id, org_id=r.org_id, reason_code=r.reason_code,
                status=ParkStatus.PENDING.value, object_type=r.object_type, source=r.source,
                source_object_id=r.source_object_id, parent_object_id=r.parent_object_id,
                connection_id=r.connection_id, parked_at=r.created_at,
                attempts=int(r.refetch_attempts) - 1, next_attempt_at=None)
            for r in rows)

    # -- payload -------------------------------------------------------------------------------
    def load_payload(self, candidate: RefetchCandidate) -> dict[str, Any]:
        """The stub's raw object, decrypted. An expired or missing payload is `{}` rather than an
        error: the refetch can still run — the filename and mime come from the ledger id and the
        provider — it simply cannot preserve the recipients it never got to read."""
        with self._engine.connect() as c:
            row = c.execute(text(
                "select enc_content from raw_payloads where org_id=:o and event_id=:e "
                "order by expires_at desc limit 1"),
                {"o": candidate.org_id, "e": candidate.event_id}).first()
        if row is None or row.enc_content is None:
            return {}
        try:
            loaded = json.loads(decrypt(bytes(row.enc_content), self._key))
        except Exception:                               # noqa: BLE001 — a key rotation, not a crash
            _log.warning("refetch: unreadable payload for event %s", candidate.event_id)
            return {}
        return loaded if isinstance(loaded, dict) else {}

    # -- writes --------------------------------------------------------------------------------
    def persist_settlement(self, settlement: RefetchSettlement) -> None:
        with self._engine.begin() as c:
            self._write_park(c, settlement)

    def persist_recovery(self, settlement: RefetchSettlement,
                         recovered: RecoveredDocument) -> None:
        """Payload, seam, ledger and park in ONE transaction.

        Anything less and a crash between the writes leaves an event marked `emitted` whose body
        is still the empty stub — L2 would extract nothing from it and record a successful run,
        which is the same silent loss wearing a different hat.
        """
        expires = settlement.last_attempt_at + timedelta(days=RECOVERED_PAYLOAD_TTL_DAYS)
        content = json.dumps(recovered.payload, default=str)
        prepared: PreparedContent = recovered.prepared
        with self._engine.begin() as c:
            updated = c.execute(text(
                "update raw_payloads set enc_content=:enc, content_type='application/json', "
                "expires_at=:exp where org_id=:o and event_id=:e"),
                {"enc": encrypt(content, self._key), "exp": expires,
                 "o": recovered.org_id, "e": recovered.event_id}).rowcount
            if not updated:
                payload_id = new_id("pay")
                c.execute(text(
                    "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                    "expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                    {"id": payload_id, "o": recovered.org_id, "e": recovered.event_id,
                     "enc": encrypt(content, self._key), "exp": expires})
                c.execute(text("update source_events set payload_ref=:p "
                               "where org_id=:o and event_id=:e"),
                          {"p": payload_id, "o": recovered.org_id, "e": recovered.event_id})

            c.execute(text(
                "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text, "
                "language, masked_spans, protected_spans, offset_map, signature_hints, "
                "preprocessor_version, expires_at) values (:e, :o, :pid, :txt, :lang, "
                "cast(:ms as jsonb), cast(:ps as jsonb), cast(:om as jsonb), cast(:sh as jsonb), "
                ":pv, :exp) on conflict (event_id) do update set "
                "prepared_content_id=excluded.prepared_content_id, clean_text=excluded.clean_text, "
                "language=excluded.language, masked_spans=excluded.masked_spans, "
                "protected_spans=excluded.protected_spans, offset_map=excluded.offset_map, "
                "signature_hints=excluded.signature_hints, "
                "preprocessor_version=excluded.preprocessor_version, "
                "expires_at=excluded.expires_at"),
                {"e": recovered.event_id, "o": recovered.org_id,
                 "pid": prepared.prepared_content_id, "txt": prepared.clean_text,
                 "lang": prepared.language,
                 "ms": json.dumps([m.model_dump() for m in prepared.masked_spans]),
                 "ps": json.dumps([list(p) for p in prepared.protected_spans]),
                 "om": json.dumps([s.model_dump() for s in prepared.offset_map]),
                 "sh": json.dumps(prepared.signature_hints, default=str),
                 "pv": prepared.preprocessor_version,
                 "exp": settlement.last_attempt_at + timedelta(days=180)})

            c.execute(text(
                "insert into document_jobs (id, org_id, event_id, format, native_parse_used, "
                "ocr_engine, ocr_pages, avg_confidence, status) values (:id, :o, :e, :fmt, :nat, "
                ":eng, :pages, :conf, :status)"),
                {"id": new_id("doc"), "o": recovered.org_id, "e": recovered.event_id,
                 "fmt": recovered.mime, "nat": recovered.native_parse_used,
                 "eng": recovered.ocr_engine, "pages": recovered.ocr_pages,
                 "conf": _confidence_column(recovered.confidence_bp),
                 "status": recovered.status})

            # The one non-idempotent transition, guarded: a second recovery updates no row.
            c.execute(text("update source_events set outcome='emitted' "
                           "where org_id=:o and event_id=:e and outcome='parked'"),
                      {"o": recovered.org_id, "e": recovered.event_id})
            self._write_park(c, settlement)

    @staticmethod
    def _write_park(c, settlement: RefetchSettlement) -> None:
        c.execute(text(
            "update parked_events set status=:s, refetch_attempts=:a, "
            "refetch_last_attempt_at=:t, refetch_next_attempt_at=:n, refetch_last_error=:err, "
            "refetch_failure_kind=:kind "
            "where org_id=:o and event_id=:e"),
            {"s": settlement.status.value, "a": settlement.attempts,
             "t": settlement.last_attempt_at, "n": settlement.next_attempt_at,
             "err": (settlement.last_error or None) and settlement.last_error[:1000],
             "kind": settlement.failure.value if settlement.failure else None,
             "o": settlement.org_id, "e": settlement.event_id})

    # -- read surfaces -------------------------------------------------------------------------
    def aging(self, *, eval_time: datetime, policy: RefetchPolicy,
              org_id: str | None = None) -> RefetchAging:
        """The G2 metric, as a query."""
        with self._engine.connect() as c:
            return read_aging(c, eval_time=eval_time, policy=policy, org_id=org_id)

    def dead_letters(self, *, org_id: str | None = None,
                     limit: int = 100) -> tuple[DeadLetter, ...]:
        where_org = "and pe.org_id = :org" if org_id else ""
        params: dict[str, Any] = {"lim": limit}
        if org_id:
            params["org"] = org_id
        with self._engine.connect() as c:
            rows = c.execute(text(
                "select pe.event_id, pe.org_id, pe.reason_code, pe.created_at, "
                "       pe.refetch_attempts, pe.refetch_last_error, pe.refetch_last_attempt_at, "
                "       pe.refetch_failure_kind, "
                "       coalesce(se.source_object_id, '') as source_object_id "
                "  from parked_events pe "
                "  left join source_events se on se.event_id = pe.event_id "
                f" where pe.status = 'dead_letter' {where_org} "
                " order by pe.created_at asc limit :lim"), params).fetchall()
        return tuple(DeadLetter(event_id=r.event_id, org_id=r.org_id, reason_code=r.reason_code,
                                source_object_id=r.source_object_id,
                                attempts=int(r.refetch_attempts),
                                last_error=r.refetch_last_error,
                                last_attempt_at=r.refetch_last_attempt_at,
                                parked_at=r.created_at,
                                failure_kind=r.refetch_failure_kind)
                     for r in rows)

    def requeue_dead_letters(self, *, eval_time: datetime, org_id: str | None = None,
                             reason_codes: frozenset[str] | None = None,
                             not_attempted_since: datetime | None = None) -> int:
        """Put dead letters back on the ladder — the action that makes a CAPABILITY dead letter
        honest. `ocr_unavailable` is not "we lost it", it is "we could not read it yet", and the
        day an OCR engine is wired somebody has to be able to say so to 369 documents at once.

        `not_attempted_since` is what lets the HEARTBEAT do the saying instead of an operator.
        Without it an automatic requeue is a loop: the rows come back, the ladder spends five
        attempts re-learning the same gap, they dead-letter again, and the next tick requeues
        them again. Bounded to rows nobody has touched since that instant, the pass can run every
        beat and still cost at most one ladder per row per window — which is the same slow clock
        `refetch_policy` already defers a capability failure on, applied one level up.
        """
        reasons = sorted(reason_codes if reason_codes is not None else NEEDS_REFETCH)
        where_org = "and org_id = :org" if org_id else ""
        where_age = ("and (refetch_last_attempt_at is null or refetch_last_attempt_at < :since)"
                     if not_attempted_since is not None else "")
        params: dict[str, Any] = {"reasons": reasons, "now": eval_time}
        if org_id:
            params["org"] = org_id
        if not_attempted_since is not None:
            params["since"] = not_attempted_since
        with self._engine.begin() as c:
            return c.execute(text(
                "update parked_events set status='pending', refetch_attempts=0, "
                "refetch_next_attempt_at=null, refetch_last_error=null, "
                "refetch_failure_kind=null "
                f"where status='dead_letter' and reason_code = any(:reasons) {where_org} "
                f"{where_age}"),
                params).rowcount
