"""L1.3.8-U1 · the refetch DECISION, with no I/O in it.

`drain.py` split parks into RE-ADJUDICABLE (the payload can answer it again) and NEEDS REFETCH
(the payload is an attachment stub, so only the connector can answer it) and then — honestly, and
uselessly — counted the second class and walked away. This module is the missing half: given one
parked attachment and a clock reading, decide whether to fetch it now, wait, or stop.

WHY THE DECISION IS A SEPARATE MODULE. Every interesting property of a retry loop is a property of
its arithmetic, not of its SQL: that the ladder terminates, that a permanently-deleted attachment
reaches a terminal state instead of costing a download every ten minutes forever, that a park too
young to have settled is not attempted, that a crash between claim and settle still burns an
attempt. Behind a database those are integration tests that need a server; in front of one they are
a table with a row per condition. So the decisions live here — pure, integer, clock-as-parameter —
and `refetch.py` does the fetching and the writing.

THE TERMINAL STATES, and why there are three kinds of failure rather than one:

  TRANSIENT   the download failed and might not next time (network, rate limit, an empty body from
              the provider). This is what the backoff ladder is for, and it ends: after
              `max_attempts` the park is dead-lettered with the last error attached.
  PERMANENT   the provider says the attachment is gone — a deleted message, a revoked share. No
              number of retries produces bytes. Dead-letter on the FIRST such answer; spending
              five downloads to re-learn a 404 is not diligence.
  CAPABILITY  the bytes arrived and we still cannot read them: no OCR engine is wired, or nothing
              parses this mime. That is a fact about THIS DEPLOYMENT at one instant, not about the
              attachment — so it defers on a slow clock (`capability_backoff`) and only reaches a
              dead letter when the same ladder every other failure walks runs out. That is why a
              dead letter carries its failure KIND: "we could not read it" and "we could not fetch
              it" have different fixes, and a single `failed` flag would have hidden which one the
              queue is full of.

WHY CAPABILITY IS NOT TERMINAL ON THE FIRST ANSWER, which it used to be. `DOC-02` (unsupported
binary), `DOC-04` (OCR below the floor) and `DOC-06` (pages, no engine wired) are parked precisely
BECAUSE the toolchain could not read them, and the heartbeat drains with ``ocr=None``. So the
first tick after this component shipped was guaranteed to re-learn that for the whole backlog and,
under the old rule, to write every one of those parks off permanently in a single pass — with the
G2 metric (`status='pending'` older than an hour) reading BETTER the more of them were lost,
because a dead letter is not pending. A capability gap closes when our code changes, and a queue
that needs an operator to remember a requeue route is a queue that stays full. Deferring costs at
most `max_attempts` downloads spread over days, and the backlog drains itself the day an engine
lands.

WHY CLASSIFICATION IS TRANSIENT-FIRST. `classify_fetch_error` is the only thing standing between a
temporary provider failure and a permanent dead letter, and it reads PROSE — every one of these
reaches us as free text inside a tool-execution error rather than as a status code. Real
re-authentication and rate-limit messages carry permanent-looking words ("connected account not
found", "503 upstream gone"), so a table matched permanent-first classified a five-minute token
refresh as an attachment that no longer exists. The transient markers are therefore checked FIRST
and win ties, and the permanent markers match on WORD BOUNDARIES so a `404` inside an opaque
request id is not a verdict.

INTEGER TIME. The ladder is a tuple of whole seconds and the arithmetic is `timedelta(seconds=int)`.
Nothing here divides, nothing here scores, and `total_seconds()` — which returns a float — is never
called. A backoff computed in floats is not wrong so much as unnecessary, and this file is the one
that has to be obviously correct.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

#: Park reasons whose payload is an attachment stub — the set `drain.py` refuses, verbatim, and
#: imported from there rather than restated so the two can never disagree about what "needs a
#: refetch" means.
from genios_engine.capture.parked.drain import NEEDS_REFETCH

__all__ = [
    "AttachmentRef", "AttemptFailure", "AttemptResult", "DEFAULT_POLICY", "NEEDS_REFETCH",
    "ParkStatus", "RefetchAction", "RefetchCandidate", "RefetchPlan", "RefetchPolicy",
    "RefetchSettlement", "backoff_after", "classify_fetch_error", "parse_attachment_ref",
    "plan_refetch", "settle_attempt", "settle_without_attempt", "with_attempts",
]


class ParkStatus(str, Enum):
    """The `parked_events.status` values this unit reads and writes.

    `relabeled` and `dropped` exist in the column too (a human review path and the drain's
    no-payload exit); they are terminal for us and simply never selected, which is why they are
    absent here rather than represented as states this unit can reach.
    """

    PENDING = "pending"
    RECOVERED = "recovered"
    DEAD_LETTER = "dead_letter"


class RefetchAction(str, Enum):
    """What `plan_refetch` decided to do with one park, right now."""

    ATTEMPT = "attempt"              # fetch the bytes and try to extract them
    WAIT = "wait"                    # too young, or its backoff has not elapsed
    DEAD_LETTER = "dead_letter"      # bounded out, or unresolvable — stop, with a reason
    SKIP = "skip"                    # not this unit's row at all


class AttemptFailure(str, Enum):
    """Why one attempt did not produce readable text. See the module docstring: the KIND is what
    decides between "try again later" and "stop now", so it is part of the contract rather than a
    string in a log line."""

    TRANSIENT = "transient"          # might work next time → ladder
    PERMANENT = "permanent"          # the provider says it is gone → terminal now
    CAPABILITY = "capability"        # we fetched it and cannot read it → terminal until we improve


@dataclass(frozen=True)
class RefetchPolicy:
    """The bounds. A frozen value rather than module constants so a caller — a test, an operator
    draining a backlog faster, the admin console — can state different bounds without reaching
    into the module, and so the bounds a run used can be reported alongside its result."""

    #: A park younger than this is not attempted. The spec says ten minutes, and the reason is
    #: not politeness: the sync that parked it may still be running, and the connector it would
    #: use is the one currently rate-limited by that sync.
    min_park_age: timedelta = timedelta(minutes=10)
    #: Attempts before a TRANSIENT failure becomes a dead letter. Five, per the spec.
    max_attempts: int = 5
    #: Whole seconds to wait after attempt 1, 2, 3, 4. The last entry is reused if a caller raises
    #: `max_attempts` past the ladder's length, so the ladder can never index out of range.
    backoff_seconds: tuple[int, ...] = (600, 1_800, 7_200, 21_600)
    #: The wait after a CAPABILITY failure — we HAVE the bytes and no engine here could read them.
    #: A separate, much slower clock from `backoff_seconds` on purpose: the network ladder is
    #: waiting for a provider to recover in minutes, this one is waiting for a DEPLOYMENT to grow
    #: a parser, which happens on the scale of releases. A day keeps the whole re-download cost of
    #: an unreadable class at `max_attempts` fetches spread across `max_attempts` days.
    capability_backoff: timedelta = timedelta(days=1)
    #: How long a claimed row is hidden from the next claim. A claim is a lease: the attempt count
    #: is incremented and `next_attempt_at` pushed out BEFORE the network call, so a process that
    #: dies mid-fetch leaves a row that is bounded and re-attemptable, not one that is invisible
    #: forever or one that two drains fetch at once.
    lease: timedelta = timedelta(minutes=15)
    #: The G2 threshold. A pending refetch older than this is STUCK and is what the gate counts.
    stuck_after: timedelta = timedelta(hours=1)


DEFAULT_POLICY = RefetchPolicy()


@dataclass(frozen=True)
class AttachmentRef:
    """Where the bytes live at the provider.

    `source_object_id` for a Gmail attachment is `f"{message_id}::{attachment_id or filename}"`
    (`connectors/composio.py::_attachment_stub`), and `parent_object_id` is the message id. Both
    are read, because the second half of that string is a FILENAME whenever Gmail gave the part no
    attachment id — and a filename cannot be fetched. That case is exactly the "unresolvable"
    dead letter below: it is better to say so than to send a filename to `attachments.get` five
    times.
    """

    message_id: str
    attachment_id: str | None
    filename: str | None
    mime: str | None

    @property
    def is_fetchable(self) -> bool:
        """True when the provider can be asked for these bytes at all."""
        return bool(self.message_id and self.attachment_id)


@dataclass(frozen=True)
class RefetchCandidate:
    """One parked attachment, as the queue knows it. Every field the decision reads is here, so
    `plan_refetch` can be exercised without a database and a row can be reconstructed from a
    report."""

    event_id: str
    org_id: str
    reason_code: str
    status: str
    object_type: str
    source: str
    source_object_id: str
    parent_object_id: str | None
    connection_id: str
    parked_at: datetime
    attempts: int = 0
    next_attempt_at: datetime | None = None
    filename: str | None = None
    mime: str | None = None


@dataclass(frozen=True)
class RefetchPlan:
    """`plan_refetch`'s answer: the action, why, and — for an ATTEMPT — the lease to write before
    the network call and the attempt number that call will be."""

    candidate: RefetchCandidate
    action: RefetchAction
    reason: str
    ref: AttachmentRef | None = None
    attempt_number: int = 0
    lease_until: datetime | None = None
    #: For a DEAD_LETTER decision, WHICH kind of failure ended it. There are two, and stamping
    #: both PERMANENT — which is what the settlement used to do — made the admin console say "the
    #: attachment is gone" about every row whose ladder simply ran out, an attachment nobody ever
    #: proved was gone. Absent for every other action, because only a terminal state has a kind.
    failure: AttemptFailure | None = None


@dataclass(frozen=True)
class AttemptResult:
    """What one fetch-and-extract attempt produced. `text_chars` rather than the text itself: the
    decision is only ever "did we get readable content", and putting a document body into a
    decision contract invites somebody to log it."""

    ok: bool
    text_chars: int = 0
    byte_count: int = 0
    failure: AttemptFailure | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        # A result that claims success with no text is the exact silent-loss shape this whole
        # component exists to remove — an "accepted" document carrying nothing. Refuse to
        # construct one rather than letting it settle as RECOVERED.
        if self.ok and self.text_chars <= 0:
            raise ValueError("an attempt cannot be ok with no extracted text — that is the "
                             "empty-document failure, not a recovery")
        if not self.ok and self.failure is None:
            raise ValueError("a failed attempt must name its failure kind, because the kind is "
                             "what decides retry versus terminal")


@dataclass(frozen=True)
class RefetchSettlement:
    """The row state one attempt produces. This is what the queue writes; nothing else changes
    `parked_events` for a refetch, so every state transition in this component is visible in one
    dataclass."""

    event_id: str
    org_id: str
    status: ParkStatus
    attempts: int
    last_attempt_at: datetime
    next_attempt_at: datetime | None
    last_error: str | None
    failure: AttemptFailure | None = None


def backoff_after(attempt: int, policy: RefetchPolicy = DEFAULT_POLICY) -> timedelta:
    """Wait after the given (1-based) attempt number.

    Clamped at both ends on purpose. Attempt 0 or below is not a real attempt and gets the first
    rung rather than an IndexError; an attempt past the ladder's length reuses the last rung, so
    raising `max_attempts` in a policy widens the ladder instead of crashing the drain.
    """
    rungs = policy.backoff_seconds
    if not rungs:
        raise ValueError("a backoff ladder with no rungs cannot bound anything")
    index = min(max(attempt, 1), len(rungs)) - 1
    return timedelta(seconds=rungs[index])


def parse_attachment_ref(candidate: RefetchCandidate) -> AttachmentRef | None:
    """The provider coordinates for a parked attachment, or None when the row is not one.

    Returns a ref whose `is_fetchable` is False — rather than None — when the id half is missing
    or is really a filename, because "this is an attachment we cannot address" is a different fact
    from "this is not an attachment", and they take different exits in `plan_refetch`.
    """
    if candidate.object_type != "email_attachment":
        return None
    raw_id = candidate.source_object_id or ""
    message_id, sep, tail = raw_id.partition("::")
    if not sep:
        # No separator at all: the ledger row does not carry the composite id this connector
        # writes, so nothing here can be trusted to address a provider object.
        return None
    message_id = message_id or (candidate.parent_object_id or "")
    filename = candidate.filename
    attachment_id: str | None = tail or None
    if attachment_id and filename and attachment_id == filename:
        # `_attachment_stub` falls back to the FILENAME when Gmail gave the part no attachmentId.
        # A filename is not an address; keep it for the report and refuse to fetch with it.
        attachment_id = None
    return AttachmentRef(message_id=message_id, attachment_id=attachment_id,
                         filename=filename, mime=candidate.mime)


def plan_refetch(candidate: RefetchCandidate, *, eval_time: datetime,
                 policy: RefetchPolicy = DEFAULT_POLICY) -> RefetchPlan:
    """Decide what to do with one parked attachment at `eval_time`.

    Order matters and is not arbitrary: ownership first (is this row ours at all), then terminal
    conditions (already settled, already bounded out, unaddressable), then timing. Checking timing
    first would let a park that can never succeed keep answering WAIT forever, which is how a
    bounded ladder turns back into a black hole.
    """
    def _plan(action: RefetchAction, reason: str, *, ref: AttachmentRef | None = None,
              attempt_number: int = 0, lease_until: datetime | None = None,
              failure: AttemptFailure | None = None) -> RefetchPlan:
        return RefetchPlan(candidate=candidate, action=action, reason=reason, ref=ref,
                           attempt_number=attempt_number, lease_until=lease_until,
                           failure=failure)

    if candidate.status != ParkStatus.PENDING.value:
        return _plan(RefetchAction.SKIP, f"already settled as {candidate.status!r}")
    if candidate.reason_code not in NEEDS_REFETCH:
        return _plan(RefetchAction.SKIP, f"{candidate.reason_code} is not a refetch reason")

    ref = parse_attachment_ref(candidate)
    if ref is None:
        return _plan(RefetchAction.SKIP,
                     f"object_type {candidate.object_type!r} is not a fetchable attachment")
    if candidate.attempts >= policy.max_attempts:
        # The ladder ran out. That is a statement about how many times WE tried, so the kind is
        # TRANSIENT — the last thing the provider said is still the last thing we know.
        return _plan(RefetchAction.DEAD_LETTER,
                     f"exhausted {candidate.attempts} of {policy.max_attempts} attempts", ref=ref,
                     failure=AttemptFailure.TRANSIENT)
    if not ref.is_fetchable:
        # The only non-attempt terminal state that IS about the object: no request can be built
        # from a filename, so no number of ticks will produce one.
        return _plan(RefetchAction.DEAD_LETTER,
                     "no provider attachment id — the parked reference carries only a filename",
                     ref=ref, failure=AttemptFailure.PERMANENT)
    if eval_time - candidate.parked_at < policy.min_park_age:
        return _plan(RefetchAction.WAIT, "parked too recently to have settled", ref=ref)
    if candidate.next_attempt_at is not None and candidate.next_attempt_at > eval_time:
        return _plan(RefetchAction.WAIT, "backoff has not elapsed", ref=ref)

    return _plan(RefetchAction.ATTEMPT, "due", ref=ref,
                 attempt_number=candidate.attempts + 1,
                 lease_until=eval_time + policy.lease)


def settle_attempt(plan: RefetchPlan, result: AttemptResult, *, eval_time: datetime,
                   policy: RefetchPolicy = DEFAULT_POLICY) -> RefetchSettlement:
    """The row state that follows one attempt. Pure: the caller writes it.

    Takes the PLAN rather than the candidate so the attempt number that was leased is the attempt
    number that is settled. Deriving it again from `candidate.attempts` would double-count under
    the one condition that matters — a second drain that claimed the same row.
    """
    if plan.action is not RefetchAction.ATTEMPT:
        raise ValueError(f"only an ATTEMPT plan can be settled, not {plan.action.value!r}")
    candidate = plan.candidate
    attempts = plan.attempt_number

    def _settled(status: ParkStatus, next_at: datetime | None, error: str | None,
                 failure: AttemptFailure | None) -> RefetchSettlement:
        return RefetchSettlement(event_id=candidate.event_id, org_id=candidate.org_id,
                                 status=status, attempts=attempts, last_attempt_at=eval_time,
                                 next_attempt_at=next_at, last_error=error, failure=failure)

    if result.ok:
        return _settled(ParkStatus.RECOVERED, None, None, None)

    failure = result.failure or AttemptFailure.TRANSIENT

    if failure is AttemptFailure.PERMANENT:
        # One answer is enough: the provider said the bytes do not exist. This is the ONLY early
        # exit from the ladder, and it is reachable only through `classify_fetch_error` seeing a
        # word-bounded "gone" marker that no transient marker outranked.
        return _settled(ParkStatus.DEAD_LETTER, None, result.error, failure)

    if attempts >= policy.max_attempts:
        # Bounded, whichever ladder was being walked. The KIND is preserved so the console can
        # say what the queue is full of — five timeouts and five unreadable scans want different
        # fixes, and "dead" alone hides which one this is.
        return _settled(ParkStatus.DEAD_LETTER, None, result.error, failure)

    if failure is AttemptFailure.CAPABILITY:
        # We hold the bytes and no engine here read them. Nothing about the ATTACHMENT will
        # change, but our toolchain will — so wait on the capability clock rather than the
        # network one, and stay `pending` so the backlog is still visible and still drains
        # itself the day a parser lands.
        return _settled(ParkStatus.PENDING, eval_time + policy.capability_backoff,
                        result.error, failure)

    return _settled(ParkStatus.PENDING, eval_time + backoff_after(attempts, policy),
                    result.error, failure)


def with_attempts(candidate: RefetchCandidate, attempts: int) -> RefetchCandidate:
    """A copy of the candidate with its attempt count replaced — the one mutation a queue performs
    when it leases a row, expressed as a value so callers never rebuild the dataclass by hand."""
    return replace(candidate, attempts=attempts)


def settle_without_attempt(plan: RefetchPlan, *, eval_time: datetime,
                           policy: RefetchPolicy = DEFAULT_POLICY) -> RefetchSettlement:
    """The row state for a claimed park that was never fetched.

    A queue claims by LEASE — it increments the attempt count and pushes `next_attempt_at` out
    before any network call, so a process killed mid-fetch still burns an attempt and the ladder
    still terminates. That accounting has to be reversible in the one case where the claim was
    wrong: `plan_refetch` looked at the row the SQL filter selected and said WAIT or SKIP. No
    bytes were requested, so the attempt is REFUNDED (`attempts` goes back to what the row
    carried) and the lease is cleared, which is the difference between a race that costs nothing
    and a race that spends a retry.

    A DEAD_LETTER plan is the other reason a claimed row is never fetched — bounded out,
    unaddressable — and it settles terminally with the plan's own reason as the recorded error,
    because "why did you stop" is the only question a dead letter has to answer. It also carries
    the plan's own failure KIND rather than a hardcoded PERMANENT: an exhausted ladder is five
    transient failures, and recording it as "the attachment is gone" is a claim about the provider
    that nothing in the run supports.
    """
    candidate = plan.candidate
    if plan.action is RefetchAction.ATTEMPT:
        raise ValueError("an ATTEMPT plan settles through settle_attempt, with its result")
    if plan.action is RefetchAction.DEAD_LETTER:
        return RefetchSettlement(
            event_id=candidate.event_id, org_id=candidate.org_id,
            status=ParkStatus.DEAD_LETTER, attempts=candidate.attempts,
            last_attempt_at=eval_time, next_attempt_at=None, last_error=plan.reason,
            failure=plan.failure or AttemptFailure.PERMANENT)
    return RefetchSettlement(
        event_id=candidate.event_id, org_id=candidate.org_id, status=ParkStatus.PENDING,
        attempts=candidate.attempts, last_attempt_at=eval_time, next_attempt_at=None,
        last_error=None, failure=None)


#: Phrases that mean "this failed NOW", whatever else the sentence happens to contain. Checked
#: BEFORE the permanent table and outranking it, because the two overlap constantly in real
#: provider prose: a Composio call made while a Gmail grant is being refreshed answers "401
#: Unauthorized: connected account not found", a rate limiter answers "429 … not found in cache",
#: and a load balancer answers "503 upstream gone". Under a permanent-first table every one of
#: those retired a recoverable attachment on its first tick.
#:
#: `403` / `forbidden` lives here for the same reason it was kept out of the permanent table: a
#: permission error is usually an expired or re-scoped token, and the tenant reconnects.
_TRANSIENT_FETCH_MARKERS: tuple[str, ...] = (
    # rate limiting and explicit "come back later"
    "429", "rate limit", "ratelimit", "too many requests", "quota", "throttl", "backoff",
    "back off", "try again", "retry", "temporarily", "temporary",
    # the server is up but not answering for this request. "service unavailable" and
    # "temporarily unavailable" rather than a bare "unavailable", which would swallow the
    # permanent "no longer available" below — a transient marker only ever ADDS retries, so an
    # over-broad one costs nothing except the one thing it hides.
    "500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable",
    "temporarily unavailable", "currently unavailable", "gateway timeout", "upstream",
    "overloaded",
    # the wire
    "timeout", "timed out", "connection reset", "connection aborted", "connection refused",
    "connection closed", "connection error", "connectionreset", "broken pipe", "eof occurred",
    "remote end closed", "name or service not known", "dns", "ssl",
    # authorisation in flight — a reconnect fixes these, and a reconnect is routine. These are
    # deliberately whole PHRASES about the connection rather than the loose word "connection":
    # a provider's 404 about an attachment routinely quotes the connection it was made on, and a
    # marker that matched that would classify a genuinely deleted attachment as retryable.
    "401", "403", "unauthorized", "unauthorised", "forbidden", "token", "credential", "oauth",
    "invalid_grant", "expired", "refresh", "reauth", "re-auth",
    "connected account not found", "not connected", "no active connection",
    "connection not found",
)

#: Provider phrases that mean the bytes are GONE, not merely unavailable right now. Matched
#: case-insensitively and on WORD BOUNDARIES against the error text, because every one of these
#: reaches us as prose inside a tool-execution error rather than as a status code we can read —
#: and a bare substring match reads a verdict out of an opaque request id (`404abc93`) or a
#: message id that happens to contain one of these letters.
_PERMANENT_FETCH_MARKERS: tuple[str, ...] = (
    "404", "410", "not found", "notfound", "does not exist", "no longer exists",
    "no longer available", "has been deleted", "was deleted", "messagenotfound",
    "attachmentnotfound", "invalid attachment", "gone", "permanently removed",
)

#: `\b…\b` around each marker, joined once at import. Word boundaries are what make "404" a status
#: code rather than three digits, and they are safe for the multi-word phrases too — the marker's
#: own spaces still have to appear in the text.
_PERMANENT_PATTERN = re.compile(
    "|".join(rf"\b{re.escape(marker)}\b" for marker in _PERMANENT_FETCH_MARKERS))


def classify_fetch_error(message: str | None) -> AttemptFailure:
    """Whether a failed fetch is worth trying again.

    Pure string classification, and deliberately so: this is the ONE place the retry ladder's
    terminating condition depends on what a provider said, and a rule that lives in a table can
    be read, tested row by row, and corrected without touching the drain.

    TRANSIENT WINS TIES, and that asymmetry is the whole safety argument. An unknown error costs
    at most `max_attempts` downloads because the ladder bounds it; a mis-classified PERMANENT
    costs a real attachment forever, silently, and makes the G2 metric look better for having
    lost it. So a message that carries evidence of BOTH — which is what a re-authentication or a
    rate-limit response almost always looks like — is retried.
    """
    text = (message or "").lower()
    if any(marker in text for marker in _TRANSIENT_FETCH_MARKERS):
        return AttemptFailure.TRANSIENT
    if _PERMANENT_PATTERN.search(text):
        return AttemptFailure.PERMANENT
    return AttemptFailure.TRANSIENT
