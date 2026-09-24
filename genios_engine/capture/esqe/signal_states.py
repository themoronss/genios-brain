"""L1.6.x-U1 · PER-TYPE SIGNAL STATES — and the one rule that makes them safe to publish.

ALG-19 (`esqe/lifecycle.py`) has four generic states — `active` / `superseded` / `expired` /
`resolved` — and that machine is correct: supersession keyed on `(subject_key, signal_type)`,
authority-gated, world-time ordered. **This module does not replace it and does not add a second
one** (§9). It supplies WORDS, as data, for the three types the four cannot describe.

A commitment needs to say *did the promise get kept?* and there is no generic state for that.

⛔ **E1 IS THE WHOLE STEP.**

> *"No fulfilment evidence found → `UNKNOWN`, **never `BROKEN`**, unless coverage over the window
> is high enough to make absence meaningful."*

Claude's benchmark run marked four promises **Broken** and was right, because it could read nearly
the whole sent folder. On a mailbox where we read 8% of the window, **the identical absence means
UNKNOWN** — it says something about us, not about the promise.

> **Telling a founder they broke a promise they actually kept is worse than saying nothing.**
> An absence of evidence is evidence of absence only when you can prove you looked.

That is Gemini's *"18 threads of 18 that exist"* one level down — a conclusion drawn from a
denominator nobody checked. Step 5 built the denominator; this is the first consumer that would be
actively dangerous without it.

**THE GATE GUARDS ONE DIRECTION ONLY.** `FULFILLED` needs no coverage: finding the evidence is a
POSITIVE observation and we are not reasoning from an absence. Suppressing it would be caution
applied where there is nothing to be cautious about.

PURE: no clock (`eval_time` is a parameter, so a replay of last week produces last week's answer),
no I/O, no model. §9: *"Do not let the model commit a transition."* It proposes the fulfilment
candidate; this module decides legality.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from genios_engine.contracts.signal import SIGNAL_STATES, SignalType

#: How much of the window we must have read before an ABSENCE is allowed to mean `BROKEN`.
#:
#: **DELIBERATELY VERY HIGH.** A 5000 bp gate would let a coin-flip corpus accuse people, and the
#: cost of a false `BROKEN` is not symmetric with the cost of a false `UNKNOWN`: one tells a founder
#: they failed at something they did, and the other tells them we are not sure. The `Commitment`
#: contract already prices the first — *"the second false chase is the last time that founder reads
#: a nudge from us."*
#:
#: It is a module constant today and belongs in `org_qualification_floors`' shape — a per-tenant row
#: with an owner — the moment a tenant wants to argue with it. Named, so it is findable when they do.
BROKEN_REQUIRES_COVERAGE_BP = 9000


class CommitmentState(str, Enum):
    """Did the promise get kept?

    `UNKNOWN` IS NOT A FAILURE STATE and is expected to be the commonest value on a young tenant.
    §3's prediction: *"if most land in BROKEN, the coverage gate is not wired and the step has
    produced a confident lie."*
    """

    #: The deadline has not passed, or there is no deadline yet.
    OPEN = "open"
    #: A later event satisfies it. Positive evidence; needs no coverage figure.
    FULFILLED = "fulfilled"
    #: Overdue, nothing found, **and we can show we looked**. See `BROKEN_REQUIRES_COVERAGE_BP`.
    BROKEN = "broken"
    #: Overdue and we cannot prove we looked. The honest answer, and the default.
    UNKNOWN = "unknown"


class ConditionState(str, Enum):
    """Whether a conditional promise's condition has been met.

    **LAYER 1 NEVER EVALUATES THIS AGAINST COMPANY STATE** (§9, E8). Deciding whether *"once Finance
    confirms"* has happened needs the graph, and the graph is Layer 2's. L1 says the condition
    exists and that its satisfaction is `UNKNOWN`.
    """

    UNMET = "unmet"
    MET = "met"
    UNKNOWN = "unknown"
    EXPIRED = "expired"


class AvailabilityState(str, Enum):
    """Whether a stated absence is still in force."""

    ACTIVE = "active"
    ENDED = "ended"
    UNKNOWN = "unknown"


def _values(enum: type[Enum]) -> frozenset[str]:
    return frozenset(member.value for member in enum)


#: SignalType -> the state vocabulary that type uses. **Data, not a second state machine** (§9):
#: ALG-19 reads this to know which words are legal for a type, and nothing else changes.
#:
#: TOTAL over every member, validated at import below — on the same terms as `ImportanceWeights`'
#: sum-to-10000 check. A map that could be half-filled is a map where a new type silently falls
#: back to a vocabulary that cannot describe it, which is exactly the defect this step is fixing.
STATES_FOR_TYPE: Mapping[SignalType, frozenset[str]] = MappingProxyType({
    SignalType.COMMITMENT_MADE: _values(CommitmentState),
    SignalType.COMMITMENT_DUE: _values(CommitmentState),
    SignalType.AVAILABILITY_CHANGE: _values(AvailabilityState),
})


def states_for(signal_type: SignalType) -> frozenset[str]:
    """The legal states for one type — its own vocabulary, or the generic four.

    The fallback is the POINT, not a gap: §9 says *"the four generic states are unchanged for every
    other type"*, and a type that needed its own words would be given them here rather than by a
    caller inventing a string.
    """
    return STATES_FOR_TYPE.get(signal_type, SIGNAL_STATES)


# Import-time totality check (12-U2). A member with no vocabulary at all is unreachable here
# because of the fallback, so what this guards is the OPPOSITE mistake: a per-type entry whose
# words overlap the generic four in a way that makes a state ambiguous across types.
for _type, _states in STATES_FOR_TYPE.items():           # pragma: no cover - import guard
    if not _states:
        raise RuntimeError(f"{_type.name} declares an empty state vocabulary")


@dataclass(frozen=True, slots=True)
class CommitmentFacts:
    """Everything the resolver needs about one promise, gathered by the caller.

    No lookups, no clock: `eval_time` arrives as a parameter so a replay of last week produces last
    week's answer, exactly as `finalize.py` requires of every unit downstream of capture.
    """

    #: The FAR end of the deadline range. E9: *"sometime next week"* is a RANGE and ALG-09 already
    #: stores its far end — calling a promise broken on the near end is inventing a deadline, the
    #: failure `Commitment`'s own contract warns about.
    due_latest: datetime | None
    #: The later event that satisfies it, when one was found and validated. `None` is an absence
    #: and NEVER on its own a failure — read `coverage_bp` before concluding anything from it.
    fulfilment_event_id: str | None
    #: How much of the window we could actually read, in basis points. **`None` means nobody
    #: measured**, which is not zero and is not a reason to guess.
    coverage_bp: int | None
    eval_time: datetime
    #: E5 · the promise was withdrawn. *"Never mind"* retires a promise; it does not fail one.
    was_withdrawn: bool = False

    def withdrawn(self) -> "CommitmentFacts":
        """The same promise, retired by its own author."""
        return replace(self, was_withdrawn=True)

    @property
    def is_overdue(self) -> bool:
        """Past the FAR end of the deadline. No deadline means never overdue — a promise with no
        date is an open loop, not a late one."""
        return self.due_latest is not None and self.eval_time > self.due_latest

    @property
    def days_late(self) -> int:
        """E3 · how late a fulfilment was, in whole days. **Late is not broken**, and carrying the
        delta is what lets a reader see that without re-deriving it."""
        if self.due_latest is None or self.eval_time <= self.due_latest:
            return 0
        return (self.eval_time - self.due_latest).days


def resolve_commitment_state(facts: CommitmentFacts) -> CommitmentState:
    """The state of one promise. **The machine decides; the model only proposed the link.**

    The order of these branches is the design:

    1. **fulfilled** — positive evidence, and it outranks everything. No coverage needed.
    2. **withdrawn** — E5. Retired by its author, never failed.
    3. **not overdue** — `OPEN`. Nothing to conclude yet, whatever the coverage.
    4. **overdue** — and here, and only here, the coverage gate decides between `BROKEN` and
       `UNKNOWN`. That is E1 and it is the entire point of the step.
    """
    if facts.fulfilment_event_id:
        return CommitmentState.FULFILLED
    if facts.was_withdrawn:
        return CommitmentState.UNKNOWN
    if not facts.is_overdue:
        return CommitmentState.OPEN
    # ⛔ E1. An absence means BROKEN only when we can show we looked. `None` is not a low number —
    # it is nobody having measured, and it lands on the same side as a low one.
    if facts.coverage_bp is not None and facts.coverage_bp >= BROKEN_REQUIRES_COVERAGE_BP:
        return CommitmentState.BROKEN
    return CommitmentState.UNKNOWN


def resolve_condition_state(*, satisfied: bool | None) -> ConditionState:
    """A conditional promise's condition state.

    **`satisfied` is never computed here.** Deciding whether *"once Finance confirms"* has happened
    needs the company graph, and the graph is Layer 2's (§9, E8). L1 records that the condition
    exists and that its satisfaction is `UNKNOWN`; a caller that has already been told the answer
    by the layer that owns it may pass it in.
    """
    if satisfied is None:
        return ConditionState.UNKNOWN
    return ConditionState.MET if satisfied else ConditionState.UNMET


def is_valid_fulfilment(*, promised_at: datetime, event_at: datetime) -> bool:
    """12-U4 · may this event be the thing that satisfied that promise?

    Time ordering only, here: an event dated before the promise is not its fulfilment, and that is
    a check the MACHINE makes rather than a property the model asserts. Subject and actor matching
    are the caller's — they hold the signals; this holds the rule.
    """
    return event_at > promised_at


__all__ = ["BROKEN_REQUIRES_COVERAGE_BP", "STATES_FOR_TYPE", "AvailabilityState",
           "CommitmentFacts", "CommitmentState", "ConditionState", "is_valid_fulfilment",
           "resolve_commitment_state", "resolve_condition_state", "states_for"]
