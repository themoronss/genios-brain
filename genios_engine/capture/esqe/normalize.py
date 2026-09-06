"""L1.6.2-U1 · Canonical signal shape. *One shape, whichever predicate produced it.*

ALG-15 reads different parts of an extraction for different types — commitments for
``COMMITMENT_DUE``, decision states for ``DECISION_PENDING``, a money plus a recurrence for
``CONTRACT_RENEWAL`` — and what it hands on is deliberately thin: a type, the predicate that
fired, and whatever spans that predicate happened to collect. Nine of its fourteen rows carry
no span at all (`roles` is a `list[dict]` by contract; `intent == escalate` is a field, not a
sentence), so a consumer holding a `DetectedSignal` still cannot say what the signal is ABOUT.

Without this unit, every downstream unit would answer that question its own way. The importance
scorer would ask "is there a commitment?" before it could find a date; ALG-19 would branch on
type to find the date it expires against; the publisher would learn all fourteen shapes. Each
of those is a place the fifteenth signal type silently produces `None` instead of an answer.

So a normalized signal has ONE field set, populated by tables keyed on `SignalType` rather than
by a cascade of `if`. Adding a signal type is adding three rows — an anchor preference, a date
policy, an amount policy — and the totality tests fail on a member that has none.

HOW A SPAN-ONLY DETECTION BECOMES A SUBJECT
---------------------------------------------
ALG-22 (`capture/validate/claim_group.subject_key`) derives a subject from a CLAIM, and a
detection carries none. The claims are recovered rather than re-detected, in two steps that are
both lookups against what S2 already returned:

1. **by receipt** — the extraction's claims whose evidence intersects the detection's spans.
   That is exact when the predicate collected spans: those spans came off those claims.
2. **by family preference** — of the survivors (all of them, when the predicate carried no
   span), the first whose contract type this signal type is about, per `ANCHOR_FAMILIES`.

Step 2 is the only place this unit encodes what a type MEANS, and it is a table for the reason
the group law gives: the answer has to be identical on two runs and inspectable without reading
control flow.

THE FIVE FIELDS DOC 06 NAMES, AND WHY THREE MAY BE ``None``
-------------------------------------------------------------
`subject_key` (ALG-22), `subject_label`, `primary_entity`, `primary_date`, `primary_amount`.
The doc's rule is one line and it is the whole safety property of this unit: *"Missing values
are `None`, never invented."* Two can never be None — ALG-22's last rung is the event itself,
and a label falls back to the key — and three genuinely can:

* `primary_date` — a `RELATIONSHIP_CHANGE` has no date and must not borrow the renewal date
  from the same email. That is doc 06's own acceptance line.
* `primary_amount` — an event naming two different amounts has no *primary* one. Picking the
  first is the invisible merge `contracts/extraction.py` warns about in its own field comment:
  the card then says "$84K" about a message that said $84K and $74K.
* `primary_entity` — two organisations in one message is an introduction email, in which
  nothing may be attributed to either.

WHAT "NORMALIZE TOWARD THE CONTRACT" MEANS, AND WHY NO C-12 IS BUILT HERE
--------------------------------------------------------------------------
The target is `contracts/signal.QualifiedEnterpriseSignal`, and every field below is either a
C-12 field under C-12's own name (`signal_type`, `evidence_refs`, `org_id`, `event_id`,
`source`, `object_type`, `occurred_at`, `internal_kind`, `recipients`, `visibility`) or one of
the five inputs its producer needs. What is absent is what nobody has computed at S4's second
step: `importance_bp` (L1.6.7), `confidence_bp` and its vector (ALG-13), `triage_lane`, `state`
and `expires_at` (ALG-19). Constructing a C-12 here would mean inventing placeholders for those
six, and a placeholder on a boundary contract is the defect `coverage_ready` already
demonstrated — a field declared, never assigned, and read for years as "unknown" by consumers
that would otherwise have decided something. This is not a parallel shape; it is that shape
minus the numbers, and L1.6.8 adds them.

PURITY — no clock, no model, no database, no float
---------------------------------------------------
Everything is read off the detection, the extraction and the event. `eval_time` is not a
parameter because nothing here is relative to now: a `ResolvedDate` already carries the instant
it was resolved against, and re-resolving it would make a March deadline drift.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType

from genios_engine.capture.esqe.detector import DetectedSignal
from genios_engine.capture.esqe.source_analyzer import SourceAttribution, analyze_source
from genios_engine.capture.validate.canonical import ENTITY_TYPE_FAMILY, EntityFamily
from genios_engine.capture.validate.claim_group import ClaimValue, subject_key
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (
    Commitment,
    DecisionState,
    Dependency,
    EntityMention,
    ExtractionResult,
    UnclassifiedObservation,
)
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.source_event import SourceEvent
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate
from genios_engine.contracts.visibility import Visibility

__all__ = [
    "AmountPolicy",
    "DatePolicy",
    "NormalizedSignal",
    "ThreadContext",
    "AMOUNT_POLICY",
    "ANCHOR_FAMILIES",
    "DATE_POLICY",
    "normalize_signals",
]


@dataclass(frozen=True, slots=True)
class ThreadContext:
    """The conversation this signal was qualified inside — whose turn it is, and which thread.

    `capture/structural/threads.py` reconstructs exactly these four facts (direction, turn
    index, depth, `ball_in_court`) and `capture/validate/claim_group.py` groups a claim by its
    thread, and NONE of it reached S4: `run_esqe_stage` normalized every signal with
    `thread_key=None`, so ALG-22 fell to its last rung — `event:{event_id}` — and two messages
    of one conversation produced two subjects nothing downstream could join. A signal was also
    qualified without knowing whose turn it was, which is the difference between "they are
    waiting on us" and "we are waiting on them".

    Every field is a fact stated by the envelope or refused. `direction` is `None` and
    `ball_in_court` is `"unknown"` when no identity for "us" was supplied — the same refusal
    `pipeline._envelope_direction` makes for the extractor, because with no identity every
    message looks inbound, which is how a product's own onboarding mail got modelled as a
    prospect asking for a demo.
    """

    #: ALG-22 rung 4, already in its `"thread:{id}"` form, or None when this event's parent is
    #: not a thread root. An attachment's parent is its MESSAGE: answering `thread:<message id>`
    #: there mints a private thread for a file and orphans it, which `thread_group_key` refuses
    #: in as many words.
    thread_key: str | None = None
    #: `inbound` | `outbound` | `internal`, or None when no rule could name it.
    direction: str | None = None
    #: 0-based position of THIS message in the thread — turn 0 is a first contact.
    turn_index: int = 0
    #: Messages of this thread the connector says exist. 1 for a message that starts one.
    thread_depth: int = 1
    #: `us` | `them` | `unknown` — `structural/threads.BallInCourt`'s vocabulary, carried as its
    #: string value so a trace row and a stored signal read the same word.
    ball_in_court: str = "unknown"
    #: Casefolded identities seen on this thread BEFORE this event, for ALG-15's
    #: *"a new party entering a known thread"*. `None` — the default — means the caller does not
    #: know the history, which is NOT "the thread had no participants": the detector refuses to
    #: fire RELATIONSHIP_CHANGE on it rather than declaring everyone new.
    parties: frozenset[str] | None = None


class DatePolicy(str, Enum):
    """WHICH date is *"the ``ResolvedDate`` most relevant to this type"* — a table, not a guess.

    Three answers, because there are exactly three questions a signal type asks of a date.
    """

    #: The commitment's own `due`. A `COMMITMENT_DUE` carrying the renewal date instead of the
    #: promise's deadline would expire on the wrong day and nudge on the wrong day.
    COMMITMENT_DUE = "commitment_due"
    #: Whatever date the event states — the deadline, the renewal, the close date.
    STATED = "stated"
    #: This type is not about a date at all. Doc 06's `RELATIONSHIP_CHANGE` acceptance.
    NONE = "none"


class AmountPolicy(str, Enum):
    """Whether this type carries money, and from where."""

    #: Money is part of what the type MEANS — a renewal, an obligation, an opportunity.
    STATED = "stated"
    #: Money is incidental. An anchor `Money` claim is still honoured (the predicate matched
    #: it), but the extraction is not searched: an approval request that happens to sit in a
    #: thread mentioning $84K is not a $84K approval request.
    CLAIMS_ONLY = "claims_only"


#: SignalType -> the contract types this kind of signal is ABOUT, most identifying first.
#:
#: This is the only place the meaning of a type is written down in this unit, and it is a table
#: so that "what is an ESCALATION about?" is answered by reading a row rather than by tracing
#: branches. TOTAL over the 14 members — the totality test fails on a member added to the
#: contract without a row, instead of a `KeyError` reaching a customer's sync.
#:
#: `ANOMALY` prefers the open lane on purpose: it is the row that fires when nothing else did,
#: and the observation the model could not classify is the closest thing to a subject it has.
ANCHOR_FAMILIES: Mapping[SignalType, tuple[type, ...]] = MappingProxyType({
    SignalType.COMMITMENT_MADE: (Commitment,),
    SignalType.COMMITMENT_DUE: (Commitment, ResolvedDate),
    SignalType.DEADLINE_STATED: (ResolvedDate,),
    SignalType.DECISION_PENDING: (DecisionState, Dependency),
    SignalType.DECISION_MADE: (DecisionState,),
    SignalType.APPROVAL_REQUESTED: (Dependency, DecisionState, Commitment),
    SignalType.CONTRACT_RENEWAL: (Money, ResolvedDate, EntityMention),
    SignalType.FINANCIAL_OBLIGATION: (Money, Commitment, ResolvedDate),
    SignalType.RISK_FLAGGED: (EntityMention, UnclassifiedObservation, DecisionState),
    SignalType.OPPORTUNITY_SIGNAL: (Commitment, EntityMention, Money),
    SignalType.RELATIONSHIP_CHANGE: (EntityMention,),
    SignalType.INFORMATION_CONFLICT: (Money, ResolvedDate, DecisionState, Commitment),
    SignalType.ESCALATION: (DecisionState, Dependency, Commitment),
    SignalType.ANOMALY: (UnclassifiedObservation, DecisionState, Commitment, Money),
})

#: SignalType -> which date this type carries. TOTAL over the 14 members.
DATE_POLICY: Mapping[SignalType, DatePolicy] = MappingProxyType({
    SignalType.COMMITMENT_MADE: DatePolicy.COMMITMENT_DUE,
    SignalType.COMMITMENT_DUE: DatePolicy.COMMITMENT_DUE,
    SignalType.DEADLINE_STATED: DatePolicy.STATED,
    SignalType.DECISION_PENDING: DatePolicy.STATED,
    SignalType.DECISION_MADE: DatePolicy.STATED,
    SignalType.APPROVAL_REQUESTED: DatePolicy.STATED,
    SignalType.CONTRACT_RENEWAL: DatePolicy.STATED,
    SignalType.FINANCIAL_OBLIGATION: DatePolicy.STATED,
    SignalType.RISK_FLAGGED: DatePolicy.STATED,
    SignalType.OPPORTUNITY_SIGNAL: DatePolicy.STATED,
    # Doc 06's own acceptance: a relationship change carries no date, EVEN WHEN the message
    # states one. A new party joining a renewal thread is not dated by the renewal, and
    # borrowing that date is how a relationship note acquires a deadline nobody set.
    SignalType.RELATIONSHIP_CHANGE: DatePolicy.NONE,
    SignalType.INFORMATION_CONFLICT: DatePolicy.STATED,
    SignalType.ESCALATION: DatePolicy.STATED,
    SignalType.ANOMALY: DatePolicy.STATED,
})

#: SignalType -> where money may come from. TOTAL over the 14 members.
AMOUNT_POLICY: Mapping[SignalType, AmountPolicy] = MappingProxyType({
    SignalType.CONTRACT_RENEWAL: AmountPolicy.STATED,
    SignalType.FINANCIAL_OBLIGATION: AmountPolicy.STATED,
    SignalType.OPPORTUNITY_SIGNAL: AmountPolicy.STATED,
    SignalType.RISK_FLAGGED: AmountPolicy.STATED,
    SignalType.INFORMATION_CONFLICT: AmountPolicy.STATED,
    SignalType.COMMITMENT_MADE: AmountPolicy.CLAIMS_ONLY,
    SignalType.COMMITMENT_DUE: AmountPolicy.CLAIMS_ONLY,
    SignalType.DEADLINE_STATED: AmountPolicy.CLAIMS_ONLY,
    SignalType.DECISION_PENDING: AmountPolicy.CLAIMS_ONLY,
    SignalType.DECISION_MADE: AmountPolicy.CLAIMS_ONLY,
    SignalType.APPROVAL_REQUESTED: AmountPolicy.CLAIMS_ONLY,
    SignalType.RELATIONSHIP_CHANGE: AmountPolicy.CLAIMS_ONLY,
    SignalType.ESCALATION: AmountPolicy.CLAIMS_ONLY,
    SignalType.ANOMALY: AmountPolicy.CLAIMS_ONLY,
})

#: Certainties a date may be carried on when it was not itself the anchor. A `RELATIVE` or
#: `UNRESOLVED` phrase ("pretty soon") has no window to expire against, and promoting one to a
#: signal's primary date manufactures a deadline out of vagueness. A date that IS the anchor is
#: honoured whatever its certainty — that was ALG-15's call to make, not this unit's to overrule.
_CARRYABLE_CERTAINTY: frozenset[DateCertainty] = frozenset(
    {DateCertainty.EXACT, DateCertainty.RANGE})


@dataclass(frozen=True, slots=True)
class NormalizedSignal:
    """One detected signal in the one shape — provenance intact, nothing invented.

    Frozen for the reason every derived L1 record is frozen: two reads of the same signal
    inside one qualification run must return the same thing, and a mutable record edited
    between the scorer and the publisher is how a card explains itself with numbers that no
    longer match the row it was written from.
    """

    # --- envelope: carried from the source event unchanged, so provenance survives ---

    #: The tenant boundary. Copied, never re-derived: a signal that lost its org is a leak.
    org_id: str
    #: The event this was qualified from. Many signals to one event.
    event_id: str
    #: Which connector produced the event.
    source: str
    #: What kind of object it was — message, deal, note, document.
    object_type: str
    #: WORLD time — when the thing happened, not when we ingested it.
    occurred_at: datetime
    #: Who could see the ORIGINAL. Never widened above L1. `None` only when the connector
    #: stamped none, which a caller must be able to tell apart from "visible to everyone".
    visibility: Visibility | None
    #: The full participant set as the event carried it. A tuple, so an audience derived from
    #: it cannot be widened by appending in place afterwards.
    recipients: tuple[str, ...]
    #: Company-canon class, or None for ordinary observed traffic.
    internal_kind: str | None

    # --- qualification so far (ALG-15) ---

    #: The type ALG-15's predicate produced. This unit never changes it — normalizing a shape
    #: is not re-classifying a signal, and the primary/secondary split is ALG-16's.
    signal_type: SignalType
    #: WHICH predicate fired, carried verbatim from the detection. "This is a CONTRACT_RENEWAL"
    #: and "this is a CONTRACT_RENEWAL because the amount recurs" are different explanations,
    #: and losing the second here would make the first uncheckable one unit later.
    predicate: str

    # --- doc 06's five ---

    #: ALG-22's answer for the anchor claim — what this signal is ABOUT, as a stable derived
    #: string. Never None: ALG-22's last rung is the event itself.
    subject_key: str
    #: The same subject in a human's words, quoted from the source rather than composed about
    #: it. Never None; falls back to `subject_key` when no claim carried readable text.
    subject_label: str
    #: The one organisation this signal is about, or None when zero or several were named.
    primary_entity: str | None
    #: The `ResolvedDate` most relevant to this type per `DATE_POLICY`, or None.
    primary_date: ResolvedDate | None
    #: The amount this signal is about per `AMOUNT_POLICY`, or None.
    primary_amount: Money | None

    # --- trust + attribution ---

    #: The detection's own spans, deduplicated and put in reading order; the anchor claim's
    #: receipts when the predicate collected none. C-12 requires this non-empty (V-4) and it can
    #: legitimately be empty HERE — the publisher is the seam that refuses it, because parking a
    #: spanless signal with a reason beats raising inside a sweep.
    evidence_refs: tuple[EvidenceSpan, ...]
    #: L1.6.4's answer for the EVENT: ALG-14's artifact rank plus the actor's basis points.
    #: One attribution per event, shared by every signal it produced — see `normalize_signals`.
    attribution: SourceAttribution
    #: The conversation this signal sits in. One context per event, shared by every signal it
    #: produced, on the same terms as `attribution`. `None` for a caller that supplied none —
    #: which is honest, because "we do not know whose turn it is" and "it is their turn" must
    #: not read the same downstream.
    thread: ThreadContext | None = None


#: The order claims are read out of an extraction when nothing more specific applies. Fixed, so
#: that "the first claim" means the same thing on every run: a dict iteration order or a set
#: would make the anchor — and therefore the subject key — vary between two identical replays.
_CLAIM_LANES: tuple[str, ...] = (
    "commitments", "decision_states", "dependencies", "entity_mentions",
    "amounts", "dates_mentioned", "unclassified_observations",
)


def _all_claims(extraction: ExtractionResult) -> tuple[ClaimValue, ...]:
    """Every claim in the extraction, in one fixed lane order."""
    claims: list[ClaimValue] = []
    for lane in _CLAIM_LANES:
        claims.extend(getattr(extraction, lane, ()) or ())
    return tuple(claims)


def _spans_of(claim: ClaimValue, extraction: ExtractionResult) -> tuple[EvidenceSpan, ...]:
    """The evidence a single claim rests on.

    Every claim contract carries its own `evidence` list except `Money`, which carries
    `as_written` and nothing else: ALG-10 keeps the source string, but the span stays on
    whichever claim quoted the amount. So a money claim's receipt is LOOKED UP — the extraction
    spans whose quote contains the literal that was written. That is a lookup against text the
    model actually returned, never a fabricated span, and it is what stops a `CONTRACT_RENEWAL`
    whose anchor is an amount from reaching the publisher with no receipt it demonstrably has.
    """
    evidence = getattr(claim, "evidence", None)
    if evidence:
        return tuple(evidence)
    if isinstance(claim, Money) and claim.as_written:
        return tuple(span for span in extraction.all_evidence if claim.as_written in span.quote)
    return ()


def _ordered_spans(spans: Iterable[EvidenceSpan]) -> tuple[EvidenceSpan, ...]:
    """Deduplicated, in reading order — (source_ref, start, end, quote).

    Dedup is by the four fields that identify a span, not by object identity: two claims
    extracted from one sentence routinely carry equal-but-distinct span objects, and a union
    keeping both would make `len(evidence_refs)` a count of claims rather than of receipts. The
    order makes a stored signal's evidence byte-identical across replays, so a diff of two runs
    shows a real change rather than an iteration order.
    """
    seen: dict[tuple[str, int, int, str], EvidenceSpan] = {}
    for span in spans:
        seen.setdefault(
            (span.source_ref, span.start_offset, span.end_offset, span.quote), span)
    return tuple(span for _, span in sorted(seen.items(), key=lambda item: item[0]))


def _anchor_order(signal_type: SignalType, claims: Sequence[ClaimValue]) -> tuple[ClaimValue, ...]:
    """The candidate claims, re-ordered so this type's own families come first.

    A stable sort on the preference index only: claims of an unpreferred family keep their lane
    order behind the preferred ones rather than being dropped, because they are still the
    material `primary_amount` and `primary_date` read from. Nothing is discarded here — this
    unit narrows a subject, it does not filter evidence.
    """
    preference = ANCHOR_FAMILIES[signal_type]

    def rank(claim: ClaimValue) -> int:
        for index, kind in enumerate(preference):
            if isinstance(claim, kind):
                return index
        return len(preference)

    return tuple(sorted(claims, key=rank))


def _triggered_claims(detection: DetectedSignal,
                      extraction: ExtractionResult) -> tuple[ClaimValue, ...]:
    """The claims the predicate DEMONSTRABLY fired on — matched by receipt, anchor-ordered.

    Exact when the predicate collected spans: those spans came off these claims. Empty when it
    collected none (`intent == escalate` fires on a field; a `roles[]` assertion carries no
    `EvidenceSpan` because the lane is `list[dict]` by contract), and empty is the answer that
    matters — a signal with no proven claim behind it must not be handed one, because
    `primary_date`, `primary_amount` and `primary_entity` are exactly the fields doc 06 forbids
    inventing. Those three then fall back to the EXTRACTION's own unambiguity rules, which
    refuse to choose between two candidates.
    """
    keys = {(span.source_ref, span.start_offset, span.end_offset) for span in detection.evidence}
    if not keys:
        return ()
    matched = tuple(
        claim for claim in _all_claims(extraction)
        if any((span.source_ref, span.start_offset, span.end_offset) in keys
               for span in _spans_of(claim, extraction)))
    return _anchor_order(detection.signal_type, matched)


def _anchor_claim(detection: DetectedSignal, triggered: Sequence[ClaimValue],
                  extraction: ExtractionResult) -> ClaimValue | None:
    """The ONE claim the subject is derived from — ALG-22's input and the label's source.

    A triggered claim when there is one; otherwise the extraction's own claims re-ordered by
    this type's family preference. The two halves are asymmetric on purpose, and the asymmetry
    is the design: `subject_key` and `subject_label` can never be `None`, so a spanless
    predicate must still resolve to something (and its worst case is ALG-22's event rung, which
    is a group of one rather than a wrong answer). The three nullable fields make the opposite
    trade and stay empty. A unit that used this fallback for both would let a `RELATIONSHIP_CHANGE`
    with no receipts acquire the renewal amount from the same email.
    """
    if triggered:
        return triggered[0]
    candidates = _anchor_order(detection.signal_type, _all_claims(extraction))
    return candidates[0] if candidates else None


def _first(claims: Sequence[ClaimValue], kind: type) -> ClaimValue | None:
    """The first candidate claim of a given contract type, in anchor order."""
    for claim in claims:
        if isinstance(claim, kind):
            return claim
    return None


def _stated_date(claims: Sequence[ClaimValue],
                 extraction: ExtractionResult) -> ResolvedDate | None:
    """The date the event STATES: a candidate date first, then the extraction's own.

    A `ResolvedDate` among the candidates wins outright and at any certainty — it was matched by
    the predicate's own receipts, and overruling that here would silently re-decide ALG-15.

    Falling back to the extraction, only ONE carryable candidate may survive: with two there is
    no primary date, and choosing the earlier would make a signal about March out of a message
    about March and June. None is the honest answer, and both dates remain in the extraction.
    """
    anchor = _first(claims, ResolvedDate)
    if isinstance(anchor, ResolvedDate):
        return anchor
    carryable = [date for date in extraction.dates_mentioned
                 if date.certainty in _CARRYABLE_CERTAINTY]
    return carryable[0] if len(carryable) == 1 else None


def _primary_date(signal_type: SignalType, claims: Sequence[ClaimValue],
                  extraction: ExtractionResult) -> ResolvedDate | None:
    """`DATE_POLICY` applied. One table read, then at most one fallback."""
    policy = DATE_POLICY[signal_type]
    if policy is DatePolicy.NONE:
        return None
    if policy is DatePolicy.COMMITMENT_DUE:
        commitment = _first(claims, Commitment)
        if isinstance(commitment, Commitment) and commitment.due is not None:
            return commitment.due
        # An undated promise is a real thing ("I'll get you the numbers") and has no due date to
        # carry. Fall through to whatever the event stated, so "by Friday" in the same sentence
        # is not thrown away — but never invent one.
    return _stated_date(claims, extraction)


def _primary_amount(signal_type: SignalType, claims: Sequence[ClaimValue],
                    extraction: ExtractionResult) -> Money | None:
    """`AMOUNT_POLICY` applied.

    A candidate `Money` wins. Otherwise a money-bearing type may take the extraction's amount
    ONLY when there is exactly one: two amounts in one message is the $84K email against the
    $74K attachment, which is an ALG-12 conflict and not a primary amount.
    """
    anchor = _first(claims, Money)
    if isinstance(anchor, Money):
        return anchor
    if AMOUNT_POLICY[signal_type] is AmountPolicy.CLAIMS_ONLY:
        return None
    return extraction.amounts[0] if len(extraction.amounts) == 1 else None


def _mention_name(mention: EntityMention) -> str | None:
    """The canonical name for a mention, or its surface form. Never a derived guess."""
    hint = (mention.canonical_hint or "").strip()
    if hint:
        return hint
    surface = (mention.surface_form or "").strip()
    return surface or None


def _primary_entity(signal_type: SignalType, claims: Sequence[ClaimValue],
                    extraction: ExtractionResult) -> str | None:
    """The entity this signal is about, or None.

    A triggered `EntityMention` is used whatever its family — the predicate matched it, and a
    `RELATIONSHIP_CHANGE` is legitimately about a PERSON.

    Falling back to the extraction, exactly ONE candidate must survive or the answer is None:
    two organisations in one message is an introduction email in which nothing may be attributed
    to either. WHICH mentions are candidates is the type's own leading family — a type whose
    subject IS a person (`RELATIONSHIP_CHANGE`) counts every mention, and every other type counts
    organisations only, because a person cc'd on a deal thread is a participant and not the
    subject. Both rules are ALG-22's `_org_anchor`, reused so that the subject key and the
    subject's name cannot disagree about who this signal is about.
    """
    anchor = _first(claims, EntityMention)
    if isinstance(anchor, EntityMention):
        return _mention_name(anchor)
    about_people = ANCHOR_FAMILIES[signal_type][0] is EntityMention
    names = {name for mention in extraction.entity_mentions
             if (about_people
                 or ENTITY_TYPE_FAMILY.get(
                     (mention.entity_type or "").strip().lower()) is EntityFamily.ORG)
             and (name := _mention_name(mention)) is not None}
    return sorted(names)[0] if len(names) == 1 else None


def _subject_label(claim: ClaimValue | None, fallback: str) -> str:
    """A human-readable name for the subject, in the SOURCE's words.

    Quoted, never composed about: every branch returns text the extractor read out of the
    message (an action, a decision subject, a surface form, a literal amount), because a label
    this unit wrote itself would be an assertion with no span behind it appearing on a card. The
    one composed string is the dependency's "X blocked by Y", and both halves of it are source
    text with a fixed connective between them.
    """
    text: str | None = None
    if isinstance(claim, Commitment):
        text = claim.action
    elif isinstance(claim, DecisionState):
        text = claim.subject
    elif isinstance(claim, Dependency):
        text = f"{claim.blocked} blocked by {claim.blocker}"
    elif isinstance(claim, EntityMention):
        text = _mention_name(claim)
    elif isinstance(claim, UnclassifiedObservation):
        text = claim.description
    elif isinstance(claim, (Money, ResolvedDate)):
        text = claim.as_written
    text = (text or "").strip()
    return text or fallback


def _normalize_one(detection: DetectedSignal, *, event: SourceEvent,
                   extraction: ExtractionResult, attribution: SourceAttribution,
                   thread: ThreadContext | None) -> NormalizedSignal:
    """One detection -> one fully-shaped record. Every field assigned, none invented."""
    claims = _triggered_claims(detection, extraction)
    anchor = _anchor_claim(detection, claims, extraction)
    thread_key = thread.thread_key if thread is not None else None
    key = (subject_key(anchor, extraction, event, thread_key=thread_key)
           if anchor is not None else f"event:{event.event_id}")
    spans = _ordered_spans(detection.evidence)
    if not spans and anchor is not None:
        spans = _ordered_spans(_spans_of(anchor, extraction))
    return NormalizedSignal(
        org_id=event.org_id,
        event_id=event.event_id,
        source=event.source,
        object_type=event.object_type,
        occurred_at=event.occurred_at,
        visibility=event.visibility,
        recipients=tuple(event.recipients or ()),
        internal_kind=event.internal_kind,
        signal_type=detection.signal_type,
        predicate=detection.predicate,
        subject_key=key,
        subject_label=_subject_label(anchor, key),
        primary_entity=_primary_entity(detection.signal_type, claims, extraction),
        primary_date=_primary_date(detection.signal_type, claims, extraction),
        primary_amount=_primary_amount(detection.signal_type, claims, extraction),
        evidence_refs=spans,
        attribution=attribution,
        thread=thread,
    )


def normalize_signals(signals: Iterable[DetectedSignal], *,
                      event: SourceEvent,
                      extraction: ExtractionResult,
                      attribution: SourceAttribution | None = None,
                      thread: ThreadContext | None = None,
                      thread_key: str | None = None,
                      actor_role: str | None = None,
                      mailbox_owner: str | None = None,
                      org_domains: Iterable[str] = ()) -> tuple[NormalizedSignal, ...]:
    """**L1.6.2-U1.** Put every detected signal into the one canonical shape.

    Plural rather than singular because the source analyzer's answer is a property of the
    EVENT, not of each signal: an email yielding three signals has one sender and one artifact,
    so computing an attribution per signal would rank the same message three times and invite
    the three answers to differ. It is computed once — which is also what gives L1.6.4 a
    production caller when the pipeline has none in hand — or supplied by a caller that already
    holds it, which is what `capture/pipeline.run_esqe_stage` does.

    Deterministic and pure: no clock, no model, no I/O. Two runs over the same detection,
    extraction and event produce identical records field for field, including the order of
    `evidence_refs`.

    Raises `TypeError` for anything that is not a `DetectedSignal`. A detector that handed on
    raw extraction fragments has a bug that must surface at the seam while the object is still
    in hand, rather than three units later as an `AttributeError` on `signal_type`.
    """
    # `thread_key` alone stays accepted for a caller that holds nothing else about the
    # conversation; it is the same fact, so the two can never be supplied as two answers.
    if thread is None and thread_key is not None:
        thread = ThreadContext(thread_key=thread_key)
    if attribution is None:
        attribution = analyze_source(event, actor_role=actor_role,
                                     mailbox_owner=mailbox_owner, org_domains=org_domains)
    normalized: list[NormalizedSignal] = []
    for detection in signals:
        if not isinstance(detection, DetectedSignal):
            raise TypeError(
                f"expected a DetectedSignal from ALG-15, got {type(detection).__name__} — the "
                f"normalizer shapes detections, and a raw claim reaching it means the detector "
                f"handed on the wrong object")
        normalized.append(_normalize_one(detection, event=event, extraction=extraction,
                                         attribution=attribution, thread=thread))
    return tuple(normalized)
