"""ALG-15 · L1.6.1-U1 — the first gate: does this event contain a business signal, and which.

*"A miss here is unrecoverable downstream, no matter how good L4 is."* Before this unit a grep
of `capture/` for `signal_type` returned nothing, which is the whole reason L1 routed events
instead of qualifying them: nothing above could branch on WHAT HAPPENED, only on where it came
from.

DETERMINISTIC, AND THAT IS THE DESIGN CHANGE
--------------------------------------------
Globe put a model here, weight 45, reading raw prose. In v2 the detector reads the **typed,
validated extraction** — S2 already did the semantic work and S3 already graded it — so the
predicates below are a table over contract objects and not an opinion about text. That is what
makes a March event detect identically in September, and it is what lets a founder be shown
*why* a card exists in one line of receipt rather than a paragraph of rationalisation.

MORE THAN ONE SIGNAL PER EVENT IS CORRECT
-----------------------------------------
Doc 06 is explicit: an email carrying a commitment and a deadline is two signals sharing one
`trace_id`. This unit therefore returns a SET, and ALG-16 (`classifier.py`) — not this unit —
decides which of them is the primary. The two jobs are split because a detector that also
ranked would make adding a predicate a change to the ordering.

THE CAP, AND WHY IT RANKS BY PRECEDENCE
---------------------------------------
Doc 06's failure-mode note: *"Every event produces 6 signals -> `signals_per_event` p95
monitored; cap at 5 per event, keep the highest-importance 5."* Importance is ALG-17, which
runs at L1.6.7 — three components AFTER this one — so there is no importance to keep the top 5
by at the moment the cap has to be applied. The only deterministic ordering that exists here is
ALG-16's precedence constant, so the cap uses it and the overflow is RETURNED in
`DetectionOutcome.suppressed` rather than dropped: a suppressed signal that leaves no record is
indistinguishable from a predicate that never fired, which is precisely the monitoring hole the
`no_signal_rate` counter exists to close.

WHAT AN EMPTY `evidence` TUPLE ON A DETECTION MEANS
---------------------------------------------------
Universal rule 4 binds CLAIMS: an `EntityMention`, a `Commitment`, a `Conflict` each refuse to
exist without a span. Three fields on `ExtractionResult` are properties of the whole message and
carry no span of their own — `intent`, `stance` and `topics` — and a predicate that fired on one
of them has nothing honest to cite. The tuple is left EMPTY rather than filled with the nearest
unrelated span: a receipt that points at a sentence which did not produce the claim is worse
than no receipt, because it reads as verified. The message-level receipt for those detections is
the extraction's own `all_evidence`.

Pure: no clock (`eval_time` is a parameter), no float (the horizon is a `timedelta` of whole
days), no model, no database.
"""

from __future__ import annotations

from pathlib import Path

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from genios_engine.capture.esqe.classifier import precedence_rank
from genios_engine.capture.validate.conflict import is_material_field
from genios_engine.contracts.conflict import Conflict
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                ExtractionResult)
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import DateCertainty, ResolvedDate

#: Doc 06's cap. Five is not a tuning knob — it is the number of cards a human reads about one
#: email before the sixth makes the first four look like noise.
MAX_SIGNALS_PER_EVENT = 5

#: `COMMITMENT_DUE` predicate: *"a commitment whose due.latest <= eval_time + 7d"*. Whole days,
#: as a `timedelta`, so no float ever enters the comparison.
COMMITMENT_DUE_HORIZON = timedelta(days=7)

#: A date is a STATED deadline only at these two certainty bands. `RELATIVE` is excluded by
#: `contracts/units.py` in as many words — *"downstream must never treat it as a deadline"* —
#: and that exclusion is what keeps the worked example's "pretty soon" from becoming a due date.
DEADLINE_CERTAINTIES: frozenset[DateCertainty] = frozenset(
    {DateCertainty.EXACT, DateCertainty.RANGE})

#: The `DecisionState.state` values (vocabulary.DECISION_STATE) each decision predicate reads.
#: `deferred` and `abandoned` appear in neither: a decision somebody chose to postpone or drop
#: is not an open loop and is not a closed one, and firing DECISION_PENDING on it would put a
#: nudge on a thread whose participants already decided not to have it.
PENDING_DECISION_STATES: frozenset[str] = frozenset({"pending", "blocked"})
MADE_DECISION_STATE = "made"

#: `Dependency.dependency_type` (vocabulary.DEPENDENCY_TYPE) that means a human must say yes.
APPROVAL_DEPENDENCY = "approval"

#: Tokens that make a free-text topic a RENEWAL topic. `topics` is free text by design, so the
#: predicate cannot be an equality test against one authored string — "Contract Renewal",
#: "contract_renewal" and "renewal" are the same topic and a case-sensitive `in` would find one
#: of the three. Tokenised and casefolded, which is the smallest normalisation that closes that
#: gap without pretending topics are a closed set.
RENEWAL_TOKENS: frozenset[str] = frozenset({"renewal", "renewals", "renew", "renewing"})

#: Tokens that make a topic a RISK topic, for the second half of the RISK_FLAGGED predicate.
RISK_TOKENS: frozenset[str] = frozenset({
    "risk", "risks", "risky", "churn", "outage", "breach", "incident", "litigation", "lawsuit",
    "penalty", "termination", "slippage", "delay", "delays", "overdue", "escalation", "blocker",
})

#: Tokens that make an amount RECURRING, for the second half of the CONTRACT_RENEWAL predicate
#: (*"a Money AND a recurrence"*). Read off the topics and off `Money.as_written`, because those
#: are the only two places the source's own wording survives — `Money.minor_units` cannot say
#: whether 84,000 is a one-off or a yearly fee.
RECURRENCE_TOKENS: frozenset[str] = frozenset({
    "annual", "annually", "yearly", "monthly", "quarterly", "recurring", "subscription",
    "retainer", "arr", "mrr", "pa", "pm",
})

_WORD = re.compile(r"[^0-9a-z]+")


@dataclass(frozen=True)
class DetectionInput:
    """Everything ALG-15 is allowed to read, as one typed object.

    A dataclass rather than eight positional parameters because four of the fields are optional
    context that only some callers can supply, and a call site that passes them by position is
    one reordering away from testing a thread-parties set against an authority rank.

    The two authority ranks and `thread_parties` are the inputs the predicate table names but
    the extraction cannot carry — *"a new party entering a KNOWN thread"* and *"authority
    increase in the recipient set"* are both statements about what came BEFORE this event.
    Callers that do not have that history pass nothing, and the half of the predicate that
    needed it simply does not fire. It is never guessed: inferring an escalation from a single
    message's recipient list is how a cc: to a VP becomes a false alarm.
    """

    #: The validated S2/S3 output. The only mandatory input.
    extraction: ExtractionResult
    #: The instant relative deadlines are judged against. Required, never defaulted from a
    #: clock — `COMMITMENT_DUE` is a statement about a moment, and a replay that read `now()`
    #: would re-detect last March's commitment as due today.
    eval_time: datetime
    #: ALG-12's output for this event, if the conflict lane is wired.
    conflicts: tuple[Conflict, ...] = ()
    #: Casefolded identifiers (emails or names) already seen on this thread BEFORE this event.
    #: `None` = the caller does not know the thread's history, which is not the same as "the
    #: thread had no participants" and must not fire RELATIONSHIP_CHANGE on everyone.
    thread_parties: frozenset[str] | None = None
    #: ALG-14-style ranks for the recipient set: what it was, and what it is now. Both required
    #: for the authority half of ESCALATION; one alone says nothing about a change.
    prior_recipient_authority_rank: int | None = None
    recipient_authority_rank: int | None = None

    def __post_init__(self) -> None:
        if self.eval_time.tzinfo is None:
            raise ValueError("eval_time must be tz-aware — a naive instant compared against a "
                             "tz-aware ResolvedDate is a TypeError at best and a wrong answer "
                             "in the timezone that made it comparable")


@dataclass(frozen=True)
class DetectedSignal:
    """One fired predicate: the kind it produced, the rule that produced it, its receipts.

    `predicate` is carried because "this is a CONTRACT_RENEWAL" and "this is a CONTRACT_RENEWAL
    because the amount recurs" are different explanations, and the second is the one a human can
    check. It is a stable identifier, not prose, so a monitor can count firings per rule and see
    a predicate go silent.
    """

    signal_type: SignalType
    predicate: str
    evidence: tuple[EvidenceSpan, ...] = ()


@dataclass(frozen=True)
class DetectionOutcome:
    """What ALG-15 concluded about one event."""

    #: Kept, precedence-ordered, at most `MAX_SIGNALS_PER_EVENT`.
    signals: tuple[DetectedSignal, ...] = ()
    #: Fired but over the cap. Recorded so `signals_per_event` overflow is visible instead of
    #: being silently identical to a predicate that never matched.
    suppressed: tuple[DetectedSignal, ...] = ()
    #: Convenience for the `no_signal_rate` counter doc 06 asks to monitor.
    fired: int = 0

    @property
    def types(self) -> tuple[SignalType, ...]:
        return tuple(signal.signal_type for signal in self.signals)

    @property
    def is_signal(self) -> bool:
        return bool(self.signals)


# ---------------------------------------------------------------------------------------------
# reading helpers — small, named, and each used by more than one predicate
# ---------------------------------------------------------------------------------------------

def _tokens(values: Iterable[str]) -> frozenset[str]:
    """Casefolded alphanumeric tokens across a list of free text. `"Contract Renewal"` and
    `"contract_renewal"` produce the same tokens, which is the whole point."""
    found: set[str] = set()
    for value in values:
        for token in _WORD.split(value.casefold()):
            if token:
                found.add(token)
    return frozenset(found)


def _spans(claims: Iterable[object]) -> tuple[EvidenceSpan, ...]:
    """Every span the given claims carry, in order, deduplicated. `EvidenceSpan` is frozen and
    hashable, so two claims extracted from one sentence share one receipt."""
    seen: dict[EvidenceSpan, None] = {}
    for claim in claims:
        for span in getattr(claim, "evidence", ()) or ():
            seen.setdefault(span, None)
    return tuple(seen)


def _unconditional(commitments: Sequence[Commitment]) -> list[Commitment]:
    """Promises that are actually promises.

    DIVERGENCE FROM DOC 06's LITERAL PREDICATE, and the worked example is what forces it. The
    table reads `COMMITMENT_MADE | len(commitments) > 0`, but doc 04's acceptance fixture
    contains exactly one commitment — conditional, *"I still need Finance to confirm"* — and
    requires the emitted set to be EXACTLY {CONTRACT_RENEWAL, DECISION_PENDING,
    APPROVAL_REQUESTED}. Under the literal reading COMMITMENT_MADE is a fourth member and the
    fixture cannot pass.

    The contract already says which reading is right. `Commitment`'s own docstring: *"'I'll send
    the contract once legal confirms' is not a promise with a date, and a system that stores it
    as one produces a false overdue — it chases a founder about a deliverable that was never
    due, and the second false chase is the last time that founder reads a nudge from us."* A
    conditional commitment is tracked as an open loop by the decision it waits on, which in the
    fixture is exactly the DECISION_PENDING that does fire.
    """
    return [c for c in commitments if not c.is_conditional]


def _due_within(commitments: Sequence[Commitment], eval_time: datetime,
                horizon: timedelta) -> list[Commitment]:
    """Commitments whose stated window CLOSES inside the horizon.

    `due is None` means no date was stated and explicitly does NOT mean "due now" — the contract
    forbids that reading. `latest is None` happens only at `UNRESOLVED` certainty, where there is
    no window to compare, and an unresolved date is not a deadline.
    """
    cutoff = eval_time + horizon
    return [c for c in commitments
            if c.due is not None and c.due.latest is not None and c.due.latest <= cutoff]


def _unattached_dates(extraction: ExtractionResult) -> list[ResolvedDate]:
    """Stated dates that are nobody's promise — *"a ResolvedDate with certainty in {EXACT,
    RANGE} and no commitment attached"*. Attachment is identity against the commitments' `due`
    values, so the same date reached through a commitment is that commitment's deadline and not
    a second, free-floating one."""
    attached = [c.due for c in extraction.commitments if c.due is not None]
    return [d for d in extraction.dates_mentioned
            if d.certainty in DEADLINE_CERTAINTIES and not any(d == a for a in attached)]


def _decisions_in(states: Sequence[DecisionState], wanted: frozenset[str]) -> list[DecisionState]:
    return [s for s in states if s.state in wanted]


def _approval_dependencies(dependencies: Sequence[Dependency]) -> list[Dependency]:
    return [d for d in dependencies if d.dependency_type == APPROVAL_DEPENDENCY]


def _named_entities(extraction: ExtractionResult) -> list:
    """Entities a human could be told about. `document` and `product` are excluded: "a named
    entity" beside a negative stance is meant to identify WHO the risk is with, and a risk
    attributed to a PDF is a risk nobody can act on."""
    return [m for m in extraction.entity_mentions
            if m.entity_type in ("person", "organization", "vendor", "project")]


def _new_parties(extraction: ExtractionResult, known: frozenset[str] | None) -> list:
    """Named people/orgs on this event that the thread had not seen before."""
    if known is None:
        return []
    folded = {value.casefold() for value in known}
    return [m for m in _named_entities(extraction) if m.surface_form.casefold() not in folded]


def _has_satisfied_condition(extraction: ExtractionResult) -> bool:
    """*"A satisfied condition"* — the OPPORTUNITY_SIGNAL predicate's first half.

    Read as: something in this message was waiting on a condition (a conditional commitment, or
    a dependency), and this same message records the decision that settles it. That pairing is
    the only form of "satisfied" the extraction can express — there is no `condition_met` flag
    anywhere in the contracts — and it is deterministic: two objects present, no text matching.
    """
    if not _decisions_in(extraction.decision_states, frozenset({MADE_DECISION_STATE})):
        return False
    return bool([c for c in extraction.commitments if c.is_conditional]
                or extraction.dependencies)


def _material_conflicts(conflicts: Sequence[Conflict]) -> list[Conflict]:
    """*"len(conflicts) > 0 on a material field"* — materiality is ALG-12's own table
    (`capture/validate/conflict.py::is_material_field`), reused rather than re-listed. A second
    list of material fields here would disagree with the detector's on the first row somebody
    added to one of them."""
    return [c for c in conflicts if is_material_field(c.field)]


# ---------------------------------------------------------------------------------------------
# ALG-15 · the predicate table
# ---------------------------------------------------------------------------------------------

def _detect_all(request: DetectionInput) -> list[DetectedSignal]:
    """Every predicate, evaluated independently. Order here is doc 06's table order; the
    precedence order that matters is ALG-16's and is applied afterwards."""
    ex = request.extraction
    out: list[DetectedSignal] = []
    topic_tokens = _tokens(ex.topics)
    money_tokens = _tokens(m.as_written for m in ex.amounts)

    # COMMITMENT_MADE — an unconditional promise. See `_unconditional` for the divergence.
    promises = _unconditional(ex.commitments)
    if promises:
        out.append(DetectedSignal(SignalType.COMMITMENT_MADE, "unconditional_commitment",
                                  _spans(promises)))

    # COMMITMENT_DUE — a promise whose window closes within 7 days of eval_time.
    due = _due_within(ex.commitments, request.eval_time, COMMITMENT_DUE_HORIZON)
    if due:
        out.append(DetectedSignal(SignalType.COMMITMENT_DUE, "commitment_due_within_horizon",
                                  _spans(due) + _spans(c.due for c in due)))

    # DEADLINE_STATED — a stated date nobody promised against.
    unattached = _unattached_dates(ex)
    if unattached:
        out.append(DetectedSignal(SignalType.DEADLINE_STATED, "stated_date_without_commitment",
                                  _spans(unattached)))

    # DECISION_PENDING / DECISION_MADE — the open loop and the thing that closes it.
    pending = _decisions_in(ex.decision_states, PENDING_DECISION_STATES)
    if pending:
        out.append(DetectedSignal(SignalType.DECISION_PENDING, "decision_state_open",
                                  _spans(pending)))
    made = _decisions_in(ex.decision_states, frozenset({MADE_DECISION_STATE}))
    if made:
        out.append(DetectedSignal(SignalType.DECISION_MADE, "decision_state_made", _spans(made)))

    # APPROVAL_REQUESTED — `intent == approve` OR a dependency of type approval.
    approvals = _approval_dependencies(ex.dependencies)
    if approvals:
        out.append(DetectedSignal(SignalType.APPROVAL_REQUESTED, "approval_dependency",
                                  _spans(approvals)))
    elif ex.intent == "approve":
        out.append(DetectedSignal(SignalType.APPROVAL_REQUESTED, "intent_approve"))

    # CONTRACT_RENEWAL — a renewal topic, OR money that recurs.
    if topic_tokens & RENEWAL_MATCH:
        out.append(DetectedSignal(SignalType.CONTRACT_RENEWAL, "renewal_topic"))
    elif ex.amounts and (topic_tokens | money_tokens) & RECURRENCE_TOKENS:
        out.append(DetectedSignal(SignalType.CONTRACT_RENEWAL, "recurring_amount"))

    # FINANCIAL_OBLIGATION — money AND (a due date OR an actual commitment to it).
    #
    # DIVERGENCE, same fixture, same reason as COMMITMENT_MADE: the literal predicate is
    # `a Money AND (a due date OR intent == commit)`, and the worked example carries $84K with
    # `intent == commit`, which would make it a fourth signal. `intent == commit` describes the
    # speech act of the MESSAGE; what makes money an obligation is that somebody actually took
    # it on, so the commit half additionally requires an unconditional commitment to exist. A
    # conditional "we can probably move forward" is a negotiation, not a payable.
    if ex.amounts:
        dated = [c for c in ex.commitments if c.due is not None]
        if dated or unattached:
            out.append(DetectedSignal(SignalType.FINANCIAL_OBLIGATION, "amount_with_due_date",
                                      _spans(dated) or _spans(unattached)))
        elif ex.intent == "commit" and promises:
            out.append(DetectedSignal(SignalType.FINANCIAL_OBLIGATION, "amount_committed",
                                      _spans(promises)))

    # RISK_FLAGGED — a negative stance about somebody named, OR an explicit risk topic.
    named = _named_entities(ex)
    if ex.stance == "negative" and named:
        out.append(DetectedSignal(SignalType.RISK_FLAGGED, "negative_stance_named_party",
                                  _spans(named)))
    elif topic_tokens & RISK_MATCH:
        out.append(DetectedSignal(SignalType.RISK_FLAGGED, "risk_topic"))

    # OPPORTUNITY_SIGNAL — a satisfied condition, OR a positive stance with a next step.
    if _has_satisfied_condition(ex):
        out.append(DetectedSignal(SignalType.OPPORTUNITY_SIGNAL, "condition_satisfied",
                                  _spans(made)))
    elif ex.stance == "positive" and ex.implied_actions:
        out.append(DetectedSignal(SignalType.OPPORTUNITY_SIGNAL, "positive_stance_next_step"))

    # RELATIONSHIP_CHANGE — a roles[] assertion, OR a new party on a thread we already know.
    #
    # `roles` is the lane whose closed keys are `party`/`role`/`evidence_text`; an entry in it is
    # this message asserting who somebody is. It carries no EvidenceSpan (the lane is
    # `list[dict]` by contract), hence no receipt on that detection.
    newcomers = _new_parties(ex, request.thread_parties)
    if newcomers:
        out.append(DetectedSignal(SignalType.RELATIONSHIP_CHANGE, "new_party_on_known_thread",
                                  _spans(newcomers)))
    elif ex.roles:
        out.append(DetectedSignal(SignalType.RELATIONSHIP_CHANGE, "role_asserted"))

    # AVAILABILITY_CHANGE — somebody states a window in which they cannot act (the `availability`
    # lane: leave / OOO / sick / travel / busy, start and end as quoted words). Like `roles`, the
    # lane is `list[dict]` by contract and carries no EvidenceSpan of its own, so the detection
    # carries no receipt; Layer 2 re-grounds every claim against the message before writing it.
    if ex.availability:
        out.append(DetectedSignal(SignalType.AVAILABILITY_CHANGE, "availability_stated"))

    # INFORMATION_CONFLICT — ALG-12 found a disagreement on a field that matters.
    material = _material_conflicts(request.conflicts)
    if material:
        claims = [claim for conflict in material for claim in conflict.claims]
        out.append(DetectedSignal(SignalType.INFORMATION_CONFLICT, "material_conflict",
                                  _spans(claims)))

    # ESCALATION — the speech act, OR the recipient set gaining authority since the last event.
    if ex.intent == "escalate":
        out.append(DetectedSignal(SignalType.ESCALATION, "intent_escalate"))
    elif (request.recipient_authority_rank is not None
            and request.prior_recipient_authority_rank is not None
            and request.recipient_authority_rank > request.prior_recipient_authority_rank):
        out.append(DetectedSignal(SignalType.ESCALATION, "recipient_authority_increase"))

    # ANOMALY — the catch-all, and ONLY when nothing above fired: *"none of the above but the
    # event is non-routine"*. Non-routine is read structurally, off the claim lists: an amount,
    # a dependency, a decision in a state no predicate names (`deferred`, `abandoned`), a
    # commitment nothing else claimed, or an unanswered question. It deliberately does NOT read
    # `unclassified_observations` — the open lane may be read by no rule, and a detector that
    # fired on a label the model invented would be a rule whose behaviour changes with the
    # model's phrasing.
    if not out and (ex.amounts or ex.dependencies or ex.decision_states or ex.commitments
                    or ex.questions):
        out.append(DetectedSignal(SignalType.ANOMALY, "non_routine_structure"))

    return out


#: Where authored token tables live. `shipped.yaml` is the transcription of the three literals
#: above; any other file beside it adds to them. See the README in that directory.
TOKENS_DIR = Path(__file__).resolve().parent.joinpath("tokens")


def load_token_predicates(directory: "Path | None" = None) -> dict[str, frozenset[str]]:
    """`{predicate_id: tokens}` from `tokens/*.yaml`, in filename order.

    WHAT THIS FIXES. The three frozensets above decided whether a message raised a signal at
    all, and they are English sales-and-legal words. A clinic writing *"three no-shows this week
    and the ultrasound room is down for calibration"* matches none of them: `_detect_all`
    returns `[]`, `classify_signals` returns None, `importance` is an empty tuple, and the trace
    records `signal_type=None, signals=0`. The message was read, extracted, judged
    business-relevant, and produced NO SIGNAL — silently, because no Python predicate knew the
    customer's own vocabulary.

    ONLY THE WORDS MOVE. The claim-shaped predicates — Commitment, ResolvedDate, Money, Conflict
    — read typed contract objects and are genuinely universal: a promise is a promise in every
    business. They stay in code and must not be authorable.

    A ROW MAY NOT MINT A SIGNAL TYPE. `SignalType` is a REJECT boundary, the key of the
    precedence order and of the type weight, and its own docstring states the governance for
    adding one — a schema version bump plus corpus review. A row naming a type that does not
    exist is skipped. This lane widens the WORDS that reach an existing kind.

    FAILS SOFT per file: one unreadable table must not blind detection for every other tenant.
    """
    import yaml

    root = directory or TOKENS_DIR
    out: dict[str, set[str]] = {}
    try:
        if not root.is_dir():
            return {}
        known = {member.name for member in SignalType}
        for path in sorted(root.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                for row in (data.get("predicates") or []):
                    signal_type = str((row or {}).get("signal_type") or "").strip()
                    predicate_id = str(row.get("predicate_id") or "").strip()
                    if signal_type not in known or not predicate_id:
                        continue
                    tokens = {str(t).strip().lower() for t in (row.get("tokens") or [])
                              if str(t).strip()}
                    if tokens:
                        out.setdefault(predicate_id, set()).update(tokens)
            except Exception:      # noqa: BLE001 — one bad table must not blind the others
                continue
    except Exception:      # noqa: BLE001 — a directory that cannot be read is a deploy problem
        return {}
    return {key: frozenset(values) for key, values in out.items()}


#: Read once at import: the files ship with the engine and cannot change under a running
#: process. Each shipped literal stays as the fallback for a file that will not parse.
_AUTHORED_TOKENS = load_token_predicates()

RENEWAL_MATCH: frozenset[str] = _AUTHORED_TOKENS.get("renewal_topic") or RENEWAL_TOKENS
RISK_MATCH: frozenset[str] = _AUTHORED_TOKENS.get("risk_topic") or RISK_TOKENS


def detect_signals(request: DetectionInput) -> DetectionOutcome:
    """L1.6.1-U1 · the predicate table over one validated extraction.

    Returns every kind that fired, precedence-ordered, capped at `MAX_SIGNALS_PER_EVENT` with
    the overflow reported rather than discarded. An event with no fired predicate returns an
    empty outcome — not a manufactured ANOMALY, which is a predicate like any other.
    """
    fired = _detect_all(request)
    ranked = sorted(fired, key=lambda s: precedence_rank(s.signal_type))
    return DetectionOutcome(signals=tuple(ranked[:MAX_SIGNALS_PER_EVENT]),
                            suppressed=tuple(ranked[MAX_SIGNALS_PER_EVENT:]),
                            fired=len(ranked))


__all__ = [
    "APPROVAL_DEPENDENCY",
    "COMMITMENT_DUE_HORIZON",
    "DEADLINE_CERTAINTIES",
    "DetectedSignal",
    "DetectionInput",
    "DetectionOutcome",
    "MAX_SIGNALS_PER_EVENT",
    "PENDING_DECISION_STATES",
    "RECURRENCE_TOKENS",
    "RENEWAL_TOKENS",
    "RISK_TOKENS",
    "detect_signals",
]
