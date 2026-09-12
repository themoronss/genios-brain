"""L1.6.9-U1 (ALG-19) · the signal LIFECYCLE state machine. *A signal is not a fact frozen at
capture.*

WHAT THIS CLOSES
----------------
Doc 06's own sentence is the whole motivation: *"a renewal signal about a contract that was
cancelled is dead, and must be marked so"* — otherwise L2 correlates a ghost and the founder is
nudged about something that resolved last week. That is Globe Rule 08 (**stale beats wrong**)
applied at L1, and until this unit there was nowhere in capture that could say it: every emitted
signal stood at `active` for ever, because nothing ever wrote a second value into the column.

`QualifiedEnterpriseSignal` already carries the three fields this owns — `state`, `supersedes`
and `expires_at` (C-12). This module writes NO parallel copy of them. What it adds is the only
thing a field cannot hold: **which writes are legal**.

A TABLE, NOT A LADDER OF ``if``
-------------------------------
Every transition in this module is a row in `TRANSITIONS`, keyed by `(state, event)` and
answered by lookup. There is no branch anywhere that decides a state, which is the point: a
cascade of conditions is legal-by-default — the case nobody wrote a leg for falls through to
whatever the last `else` happened to be — while a table is illegal-by-default, because a pair
with no row cannot be looked up at all.

The table is also EXHAUSTIVE by construction. `_build_transitions()` runs at import and raises
if `SIGNAL_STATES x LifecycleEvent` is not covered exactly, so adding a fifth state to
`contracts/signal.SIGNAL_STATES` without deciding what its four events mean breaks the import of
this module rather than silently acquiring a default. A state whose transitions nobody thought
about is precisely the state a dead signal would come back to life through.

DIRECTION OF ``supersedes`` — DECIDED HERE, AS C-12 ASKS
--------------------------------------------------------
`contracts/signal.py` flags the cross-doc disagreement and hands the decision to this unit: its
own field note says `supersedes` points at the signal being REPLACED (the new row points back),
while doc 06's ALG-19 pseudocode writes *"old.supersedes points forward"*. **This module picks
BACKWARD**, and here is the argument, in one place, so no call site has to re-derive it:

1. Doc 06 requires that a revive *"creates a new signal id and does not mutate the expired row"*.
   A forward pointer would have to be written INTO the expired row to record the revival — which
   is exactly the mutation the acceptance criterion forbids. Backward is the only direction that
   can express revival at all.
2. The new row is the one being written anyway. A backward pointer is set once, at insert, by
   the producer that already holds both ids; a forward pointer is an UPDATE of a historical row
   on every replacement, and a row that keeps being rewritten is a row whose history is not
   readable.
3. C-12's field comment already documents backward, and C-12 is the contract every stored row
   was validated against.

Doc 06's *"supersede sets both sides' pointers"* is honoured in substance: the NEW signal gets
`supersedes = old.signal_id`, and the OLD signal gets `state = "superseded"`. Both sides change;
only one of them stores an id, and it is the side that can store it without being rewritten.

NO CLOCK, NO MODEL, NO FLOAT
----------------------------
`eval_time` is a parameter of every function that needs an instant. Expiry evaluated against
`datetime.now()` cannot be replayed — a March signal would answer differently in September — and
replayability is the property the whole layer is built on. Expiry windows are integer days on
`timedelta`, authority is ALG-14's integer rank, and nothing here is ranked or scored by a model.

WHAT THIS UNIT REFUSES TO DECIDE
--------------------------------
It does not decide that a thing HAPPENED. `RESOLVE` is applied by a caller holding external
evidence (a countersigned document, a paid invoice, a decision recorded downstream); this module
owns whether that transition is legal from the state the signal is in, never whether the
evidence is good. And it does not publish: L1.6.10 owns the seam to L2.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol

from genios_engine.capture.validate.authority import Provenance, weigh_authority
from genios_engine.contracts.signal import SIGNAL_STATES, QualifiedEnterpriseSignal, SignalType
from genios_engine.contracts.validators import require_aware
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.esqe.lifecycle")

#: The four states, named once so a reader does not have to grep a frozenset for the spelling.
#: They ARE `contracts.signal.SIGNAL_STATES` — asserted below, not copied — because a second
#: vocabulary for the same column is how "dead" and "closed" get written into it.
ACTIVE = "active"
SUPERSEDED = "superseded"
EXPIRED = "expired"
RESOLVED = "resolved"

#: The table `signal_lifecycle` (migration 0093) — one row per signal's lifecycle position.
LIFECYCLE_TABLE = "signal_lifecycle"


class LifecycleEvent(str, Enum):
    """The four things that can HAPPEN to a signal. Doc 06 names exactly these.

    An event is not a state: `EXPIRE` is the observation "this signal's own clock has run out",
    and whether it is legal to act on that observation depends on where the signal already is.
    Keeping the two vocabularies separate is what makes the table two-dimensional and therefore
    checkable — one axis is where we are, the other is what happened.
    """

    #: A newer signal covers the same subject and type with at least equal authority.
    SUPERSEDE = "supersede"
    #: `expires_at` has passed, judged against a caller-supplied instant.
    EXPIRE = "expire"
    #: External evidence that the thing this signal was about actually happened.
    RESOLVE = "resolve"
    #: New evidence on an EXPIRED signal. Produces a new signal; never a write to the old row.
    REVIVE = "revive"


class RefusalReason(str, Enum):
    """WHY a transition was refused — a named reason, never a bare False.

    A boolean refusal is unexplainable at 3am: "the lifecycle rejected it" and "the lifecycle
    rejected it because the signal was already replaced by a newer one" are the difference
    between a support ticket and an answer. These names reach the exception, the log line and
    the `LifecycleOutcome` a caller inspects, so every refusal is quotable.
    """

    #: The signal has already been replaced. The replacement is where the next transition goes.
    ALREADY_SUPERSEDED = "already_superseded"
    #: The signal's clock has already run out. Doc 06's route back is REVIVE, into a NEW row.
    ALREADY_EXPIRED = "already_expired"
    #: The thing already happened and was recorded. Re-resolving would rewrite history.
    ALREADY_RESOLVED = "already_resolved"
    #: The state is one of the three terminal ones, and this event is a claim about a LIVE
    #: signal. A superseded renewal's clock is the replacement's clock, not its own.
    TERMINAL_STATE = "terminal_state"
    #: REVIVE is defined by doc 06 on an EXPIRED signal only. From anywhere else it is a request
    #: to reactivate something that did not die of a clock — which is the ghost ALG-19 prevents.
    REVIVE_REQUIRES_EXPIRED = "revive_requires_expired"


@dataclass(frozen=True, slots=True)
class TransitionRule:
    """One cell of the machine: what `(from_state, event)` means.

    Frozen and data-only. `to_state is None` IS the refusal — the two cases cannot both be
    populated, which is checked in `__post_init__`, so a row cannot be written that both allows
    and refuses. `why` is prose for humans and is carried into the exception message; it exists
    because the reason a transition is illegal is the part that stops being obvious six months
    after the table was written.
    """

    from_state: str
    event: LifecycleEvent
    to_state: str | None
    refusal: RefusalReason | None
    why: str
    #: True for the one rule where the answer is "make a NEW signal, and leave this row alone":
    #: REVIVE on an expired signal. The state does not move; a row is added elsewhere.
    creates_new_signal: bool = False

    def __post_init__(self) -> None:
        if (self.to_state is None) == (self.refusal is None):
            raise ValueError(
                f"{self.from_state}/{self.event.value}: a rule is exactly one of allowed "
                "(to_state) or refused (refusal) — never both and never neither")
        if self.to_state is not None and self.to_state not in SIGNAL_STATES:
            raise ValueError(f"{self.to_state!r} is not one of {sorted(SIGNAL_STATES)}")
        if not self.why:
            raise ValueError(f"{self.from_state}/{self.event.value}: every rule states why")

    @property
    def allowed(self) -> bool:
        """True when this cell permits the event. The only place `to_state is None` is read."""
        return self.to_state is not None


class IllegalTransition(Exception):
    """A refused transition, raised with its named reason attached.

    An exception rather than a returned False for the WRITE path: `apply` mutates a stored
    signal, and a caller that ignores a boolean has already written the illegal state. Callers
    that want to ASK rather than act use `evaluate`, which returns the rule and raises nothing.
    """

    def __init__(self, *, state: str, event: LifecycleEvent, reason: RefusalReason,
                 why: str, signal_id: str | None = None) -> None:
        self.state = state
        self.event = event
        self.reason = reason
        self.why = why
        self.signal_id = signal_id
        subject = f" signal={signal_id}" if signal_id else ""
        super().__init__(f"{event.value} refused from state {state!r}{subject}: "
                         f"{reason.value} — {why}")


class UnknownLifecycleState(Exception):
    """A state with no row in the table — the failure mode `_build_transitions` exists to make
    impossible at import, kept as a runtime guard for a state read back out of a database column
    that a migration widened without this module being told."""


def _rules() -> tuple[TransitionRule, ...]:
    """The whole algorithm, as sixteen literal rows. Read this and you have read ALG-19."""
    r = TransitionRule
    return (
        # --- active: the only state anything can leave ------------------------------------
        r(ACTIVE, LifecycleEvent.SUPERSEDE, SUPERSEDED, None,
          "a newer signal of at least equal authority covers the same subject and type"),
        r(ACTIVE, LifecycleEvent.EXPIRE, EXPIRED, None,
          "the signal's own expires_at has passed as of the caller's eval_time"),
        r(ACTIVE, LifecycleEvent.RESOLVE, RESOLVED, None,
          "external evidence that the thing this signal was about happened"),
        r(ACTIVE, LifecycleEvent.REVIVE, None, RefusalReason.REVIVE_REQUIRES_EXPIRED,
          "an active signal has nothing to revive — it never stopped being live"),
        # --- superseded: the replacement carries the subject now ---------------------------
        r(SUPERSEDED, LifecycleEvent.SUPERSEDE, None, RefusalReason.ALREADY_SUPERSEDED,
          "this signal was already replaced; supersede the replacement, not the row it "
          "replaced, or the chain forks and two rows claim to be current"),
        r(SUPERSEDED, LifecycleEvent.EXPIRE, None, RefusalReason.TERMINAL_STATE,
          "expiry is a claim about a live signal's clock, and this signal's subject is carried "
          "by its replacement — expiring it would overwrite the reason it actually stopped"),
        r(SUPERSEDED, LifecycleEvent.RESOLVE, None, RefusalReason.TERMINAL_STATE,
          "the replacement is the row that can be resolved; resolving a superseded row records "
          "the outcome against a version nothing downstream reads"),
        r(SUPERSEDED, LifecycleEvent.REVIVE, None, RefusalReason.REVIVE_REQUIRES_EXPIRED,
          "a superseded signal is not revivable — its subject already moved forward, so "
          "reviving it would resurrect an old reading of a fact that has since changed"),
        # --- expired: doc 06's one route back, and it is a NEW row --------------------------
        r(EXPIRED, LifecycleEvent.SUPERSEDE, None, RefusalReason.TERMINAL_STATE,
          "an expired signal died of its own clock and the row must keep saying so; new "
          "evidence about its subject is a REVIVE, which files a new signal"),
        r(EXPIRED, LifecycleEvent.EXPIRE, None, RefusalReason.ALREADY_EXPIRED,
          "the clock already ran out; expiring twice would move expires_at and rewrite when"),
        r(EXPIRED, LifecycleEvent.RESOLVE, None, RefusalReason.TERMINAL_STATE,
          "we stopped watching before the outcome was known — a resolution learned afterwards "
          "belongs to the revived signal, which is the row that was live when it was learned"),
        r(EXPIRED, LifecycleEvent.REVIVE, EXPIRED, None,
          "new evidence on an expired signal files a NEW signal that supersedes this one; this "
          "row stays expired, unmutated, so history stays readable",
          True),
        # --- resolved: the outcome is recorded, and nothing reopens it ----------------------
        r(RESOLVED, LifecycleEvent.SUPERSEDE, None, RefusalReason.ALREADY_RESOLVED,
          "the loop is closed; a later signal about the same subject is its own signal and "
          "does not get to erase the record that this one was answered"),
        r(RESOLVED, LifecycleEvent.EXPIRE, None, RefusalReason.ALREADY_RESOLVED,
          "a resolved signal's clock is irrelevant — it stopped being open before it ran out"),
        r(RESOLVED, LifecycleEvent.RESOLVE, None, RefusalReason.ALREADY_RESOLVED,
          "resolving twice would move the resolution and lose which evidence closed it"),
        r(RESOLVED, LifecycleEvent.REVIVE, None, RefusalReason.REVIVE_REQUIRES_EXPIRED,
          "a resolved signal may never silently reactivate; if the thing came back it is a new "
          "signal with its own evidence, not this one waking up"),
    )


def _build_transitions() -> Mapping[tuple[str, LifecycleEvent], TransitionRule]:
    """Assemble the table and REFUSE to import if it is not exactly total.

    Three checks, and each one is a defect that has actually shipped in state machines:
    a duplicated cell (two rules, and the answer depends on which was typed last), a missing
    cell (the pair nobody decided, which a lookup with a default would call legal), and a rule
    for a state the contract does not have (a fifth spelling entering by the back door).

    Raising at IMPORT is deliberate. A new member added to `SIGNAL_STATES` without four rules
    here is a state whose transitions nobody decided, and the only safe moment to find that out
    is before a single signal has been written.
    """
    table: dict[tuple[str, LifecycleEvent], TransitionRule] = {}
    for rule in _rules():
        if rule.from_state not in SIGNAL_STATES:
            raise ValueError(
                f"lifecycle rule names state {rule.from_state!r}, which is not in "
                f"contracts.signal.SIGNAL_STATES {sorted(SIGNAL_STATES)}")
        key = (rule.from_state, rule.event)
        if key in table:
            raise ValueError(f"duplicate lifecycle rule for {key[0]}/{key[1].value}")
        table[key] = rule
    missing = unruled_pairs(SIGNAL_STATES, table)
    if missing:
        raise ValueError(
            "the ALG-19 transition table is not exhaustive — no rule for "
            + ", ".join(f"{state}/{event.value}" for state, event in missing)
            + ". A state added to contracts.signal.SIGNAL_STATES needs a decision for every "
              "event, because a pair with no rule is a pair nobody thought about.")
    return MappingProxyType(table)


def unruled_pairs(states: Iterable[str],
                  table: Mapping[tuple[str, LifecycleEvent], TransitionRule] | None = None
                  ) -> tuple[tuple[str, LifecycleEvent], ...]:
    """Every `(state, event)` in `states x LifecycleEvent` that the table does not answer.

    Public and parameterised over `states` so the exhaustiveness property can be tested against
    a HYPOTHETICAL new state without editing the contract's frozenset: a test passes
    `SIGNAL_STATES | {"archived"}` and asserts the four archived pairs come back. Sorted, so the
    failure message is stable.
    """
    known = TRANSITIONS if table is None else table
    return tuple(sorted(
        ((state, event) for state in states for event in LifecycleEvent
         if (state, event) not in known),
        key=lambda pair: (pair[0], pair[1].value)))


#: THE MACHINE. Sixteen cells, total over `SIGNAL_STATES x LifecycleEvent`, read-only.
TRANSITIONS: Mapping[tuple[str, LifecycleEvent], TransitionRule] = _build_transitions()

#: The states nothing leaves. Derived FROM the table rather than listed beside it — a state that
#: acquires an outgoing rule stops being terminal here automatically, so the two cannot drift.
TERMINAL_STATES: frozenset[str] = frozenset(
    state for state in SIGNAL_STATES
    if not any(TRANSITIONS[(state, event)].allowed
               and TRANSITIONS[(state, event)].to_state != state
               for event in LifecycleEvent))


def evaluate(state: str, event: LifecycleEvent) -> TransitionRule:
    """The ONE lookup. Every decision in this module goes through it; nothing branches on state.

    Raises `UnknownLifecycleState` for a state the table does not know — which cannot happen for
    a `QualifiedEnterpriseSignal` (its own validator closes the set) and can happen for a string
    read back out of a database column, which is the case worth naming rather than defaulting.
    """
    rule = TRANSITIONS.get((state, event))
    if rule is None:
        raise UnknownLifecycleState(
            f"no ALG-19 rule for state {state!r} — known states are {sorted(SIGNAL_STATES)}")
    return rule


def can(state: str, event: LifecycleEvent) -> bool:
    """The read-only question, for a caller choosing what to do rather than doing it."""
    return evaluate(state, event).allowed


def require(state: str, event: LifecycleEvent, *, signal_id: str | None = None) -> TransitionRule:
    """`evaluate`, raising `IllegalTransition` with its named reason when the cell refuses.

    Every write path in this module and every caller that mutates a stored signal goes through
    here, which is what makes an illegal transition impossible rather than merely unlikely: the
    refusal is not a code path a caller can forget to check.
    """
    rule = evaluate(state, event)
    if not rule.allowed:
        assert rule.refusal is not None      # noqa: S101 — guaranteed by TransitionRule
        raise IllegalTransition(state=state, event=event, reason=rule.refusal, why=rule.why,
                                signal_id=signal_id)
    return rule


# =================================================================================================
# EXPIRY — computed from the signal's OWN dates, against a caller's instant
# =================================================================================================

#: Doc 06's windows, in integer days. `COMMITMENT_DUE`/`DEADLINE_STATED` and `CONTRACT_RENEWAL`
#: get 30 days past the DATE THEY NAME — a deadline stays worth acting on for a month after it
#: passes, because "you missed this" is the most valuable thing to say about it. Everything else
#: is measured from when the thing happened.
EXPIRY_WINDOW_DAYS: Mapping[str, int] = MappingProxyType({
    SignalType.COMMITMENT_DUE.value: 30,
    SignalType.DEADLINE_STATED.value: 30,
    SignalType.CONTRACT_RENEWAL.value: 30,
    SignalType.DECISION_PENDING.value: 90,
    # A leave window is short-lived; the durable record is the `person.availability` fact in
    # Layer 2, which carries its own from/to. The signal only has to live long enough to drain.
    SignalType.AVAILABILITY_CHANGE.value: 30,
})
#: Doc 06's "others -> 180d". A named constant rather than a literal in a `.get()`, because it is
#: the window most signals actually get and it must be greppable.
DEFAULT_EXPIRY_WINDOW_DAYS = 180

#: The types whose window is measured from a date the SOURCE stated, not from the event time.
DATED_TYPES: frozenset[str] = frozenset({
    SignalType.COMMITMENT_DUE.value,
    SignalType.DEADLINE_STATED.value,
    SignalType.CONTRACT_RENEWAL.value,
})


class ExpiryBasis(str, Enum):
    """WHICH date the window was measured from — stored, so "why does this expire then?" is a
    read rather than a re-derivation."""

    #: The date the source stated (a deadline, a renewal date), taken from the resolved date.
    STATED_DATE = "stated_date"
    #: The event's world time. Used for every undated type, and for a dated type whose date the
    #: resolver could not pin — which is honest: we know when we heard it and nothing more.
    OCCURRED_AT = "occurred_at"


@dataclass(frozen=True, slots=True)
class ExpiryPlan:
    """When a signal stops being worth acting on, and the arithmetic that produced it.

    Frozen and fully explained: `basis` + `basis_at` + `window_days` reproduce `expires_at`
    exactly, so a stored plan can be checked without re-reading the extraction it came from.
    """

    expires_at: datetime
    basis: ExpiryBasis
    basis_at: datetime
    window_days: int
    signal_type: str

    def explain(self) -> str:
        """One line a human can read in a support thread."""
        return (f"{self.signal_type} expires {self.window_days}d after its "
                f"{self.basis.value} ({self.basis_at.isoformat()}) -> "
                f"{self.expires_at.isoformat()}")


def expiry_window_days(signal_type: SignalType | str) -> int:
    """Doc 06's window for a type. Total: an unlisted type gets 180, never a KeyError, because
    a fifteenth signal type must not be able to crash a sweep before anyone tunes its window."""
    key = signal_type.value if isinstance(signal_type, SignalType) else str(signal_type)
    return EXPIRY_WINDOW_DAYS.get(key, DEFAULT_EXPIRY_WINDOW_DAYS)


def _stated_instant(stated_date: Any) -> datetime | None:
    """The instant a `ResolvedDate` names, for expiry purposes: its LATEST bound.

    Latest and not earliest, because the window is a grace period and an ambiguous date must not
    shorten it — expiring "sometime in Q3" at the start of Q3 kills a live signal, while
    expiring at the end of it costs at most a few extra days of a dead one being carried. That
    asymmetry is Globe Rule 08 read the only way it can be read here.

    Returns None for a date the resolver could not pin at all, which is not an error: the caller
    falls back to the event's own time and RECORDS that it did.
    """
    if stated_date is None:
        return None
    for attribute in ("latest", "earliest"):
        value = getattr(stated_date, attribute, None)
        if isinstance(value, datetime):
            return value
    return None


def plan_expiry(signal_type: SignalType | str, *, occurred_at: datetime,
                stated_date: Any = None) -> ExpiryPlan:
    """ALG-19's expiry, from the signal's own date fields and never from ingest time.

    Doc 06's acceptance line is literally *"expiry is computed from the signal's own date fields,
    not from ingest time"*, and the reason is backfill: a two-month-old thread swept today would
    otherwise be given two more months of life than the same thread swept when it arrived, so
    the same mailbox would produce different expiries depending on when it was connected.

    `stated_date` is the `ResolvedDate` L1.6.2 already put on `NormalizedSignal.primary_date`;
    passing it for an undated type is harmless and ignored, so a caller does not have to know
    the type table to call this correctly.
    """
    key = signal_type.value if isinstance(signal_type, SignalType) else str(signal_type)
    occurred = require_aware(occurred_at, "occurred_at")
    stated = _stated_instant(stated_date) if key in DATED_TYPES else None
    if stated is not None:
        basis, basis_at = ExpiryBasis.STATED_DATE, require_aware(stated, "stated_date")
    else:
        basis, basis_at = ExpiryBasis.OCCURRED_AT, occurred
    window = expiry_window_days(key)
    return ExpiryPlan(expires_at=basis_at + timedelta(days=window), basis=basis,
                      basis_at=basis_at, window_days=window, signal_type=key)


def has_expired(expires_at: datetime | None, eval_time: datetime) -> bool:
    """Has this clock run out as of `eval_time`? `None` never expires — nothing is timing it.

    The same comparison `QualifiedEnterpriseSignal.has_expired_by` makes, in the one form that
    also works on a stored lifecycle row, which is not a `QualifiedEnterpriseSignal`. Inclusive
    (`>=`) so a signal whose expiry instant IS the sweep instant expires in that sweep rather
    than surviving one more round on a boundary nobody can see.
    """
    if expires_at is None:
        return False
    return require_aware(eval_time, "eval_time") >= require_aware(expires_at, "expires_at")


# =================================================================================================
# THE RECORD — one row per signal's lifecycle position
# =================================================================================================

@dataclass(frozen=True, slots=True)
class LifecycleRecord:
    """A signal's lifecycle, standing alone from the signal itself.

    WHY A SEPARATE RECORD AND NOT JUST THE SIGNAL. Supersession is a decision about a signal
    captured LAST MONTH, and last month's `QualifiedEnterpriseSignal` is not in memory during
    today's sweep — the whole 24-field object with its embedded extraction would have to be
    rehydrated to learn one state and one rank. This row carries exactly the eight facts the
    machine needs, so the comparison is a small indexed query instead of a page of payloads.

    It holds NO parallel copies of C-12's lifecycle fields: `state`, `supersedes` and
    `expires_at` are the same three fields under the same three names, and `record_of` /
    `apply_to_signal` are the two directions of the same seam.

    Frozen — a transition returns a NEW record. A mutable lifecycle row edited in place is how a
    "before" and an "after" become the same object and an audit line explains nothing.
    """

    org_id: str
    signal_id: str
    #: ALG-22's subject (`NormalizedSignal.subject_key`). Half of the supersession key.
    subject_key: str
    #: The signal type as its wire word. The other half of the key: a renewal does not supersede
    #: a decision about the same customer, and conflating them is how a live loop disappears.
    signal_type: str
    #: ALG-14's 0..6 artifact rank. A newer signal supersedes only at >= this.
    authority_rank: int
    #: WORLD time. Ordering is by this, never by ingest order.
    occurred_at: datetime
    state: str
    supersedes: str | None
    expires_at: datetime | None
    #: The instant this row's state was last decided — the caller's `eval_time`, never a clock.
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if self.state not in SIGNAL_STATES:
            raise ValueError(f"state must be one of {sorted(SIGNAL_STATES)}, got {self.state!r}")
        if not 0 <= self.authority_rank <= 6:
            raise ValueError(f"authority_rank is ALG-14's 0..6 ladder, got {self.authority_rank}")
        if self.supersedes is not None and self.supersedes == self.signal_id:
            raise ValueError(f"a signal may not supersede itself ({self.signal_id!r})")
        if self.state == EXPIRED and self.expires_at is None:
            raise ValueError(
                "an expired record must carry the expires_at it passed — a state that names no "
                "clock cannot be explained or replayed")
        require_aware(self.occurred_at, "occurred_at")
        require_aware(self.evaluated_at, "evaluated_at")
        if self.expires_at is not None:
            require_aware(self.expires_at, "expires_at")

    @property
    def is_live(self) -> bool:
        """True only in `active` — the same read C-12 exposes, on the row form."""
        return self.state == ACTIVE

    def key(self) -> tuple[str, str]:
        """The supersession key: `(subject_key, signal_type)`, doc 06's pair verbatim."""
        return (self.subject_key, self.signal_type)


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    """One applied move: the row before, the row after, and the rule that permitted it.

    Both sides are kept because that is what an audit answer needs — "it went from active to
    superseded on this instant, by this rule, because of this signal" — and because a caller
    persisting the result must be able to write the after WITHOUT having to trust that the
    before it holds is the one the decision was made against.
    """

    before: LifecycleRecord
    after: LifecycleRecord
    rule: TransitionRule
    #: The signal that caused it, when there is one: the newer signal for a SUPERSEDE, the
    #: revival for a REVIVE. None for EXPIRE, which is caused by a clock and nothing else.
    caused_by: str | None = None

    @property
    def event(self) -> LifecycleEvent:
        return self.rule.event

    def explain(self) -> str:
        cause = f" by {self.caused_by}" if self.caused_by else ""
        return (f"{self.before.signal_id}: {self.before.state} -> {self.after.state} "
                f"({self.rule.event.value}{cause}) — {self.rule.why}")


def advance(record: LifecycleRecord, event: LifecycleEvent, *, eval_time: datetime,
            supersedes: str | None = None, caused_by: str | None = None) -> LifecycleTransition:
    """Apply one event to one row, through the table. Raises `IllegalTransition` when refused.

    `supersedes` is accepted for the one event that sets it — a REVIVE writes the backward
    pointer onto the NEW record, not this one, so passing it with any other event is a caller
    confusing the two directions and is refused loudly rather than written quietly.
    """
    rule = require(record.state, event, signal_id=record.signal_id)
    if supersedes is not None and event is not LifecycleEvent.SUPERSEDE:
        raise ValueError(
            f"supersedes is only written by a SUPERSEDE, not by {event.value} — see the module "
            "docstring on pointer direction")
    after = replace(record, state=rule.to_state or record.state,
                    evaluated_at=require_aware(eval_time, "eval_time"))
    return LifecycleTransition(before=record, after=after, rule=rule, caused_by=caused_by)


def record_of(signal: QualifiedEnterpriseSignal, *, subject_key: str,
              evaluated_at: datetime, executed: bool = False) -> LifecycleRecord:
    """A `QualifiedEnterpriseSignal` -> its lifecycle row, with ALG-14's rank computed here.

    `subject_key` is a parameter because C-12 does not carry one: ALG-22 derives it at L1.6.2
    from the anchor CLAIM, and re-deriving it here from the embedded extraction would be a
    second answer to a question `NormalizedSignal.subject_key` has already answered — the exact
    duplication that lets a signal be superseded under one key and queried under another.

    The rank comes from `weigh_authority` over the signal's own provenance rather than from a
    stored integer, so a re-tuned authority table re-ranks consistently instead of leaving one
    subsystem comparing old numbers with new ones.
    """
    weight = weigh_authority(Provenance(source=signal.source, object_type=signal.object_type,
                                        internal_kind=signal.internal_kind, executed=executed))
    return LifecycleRecord(
        org_id=signal.org_id, signal_id=signal.signal_id, subject_key=subject_key,
        signal_type=signal.signal_type.value, authority_rank=weight.rank,
        occurred_at=signal.occurred_at, state=signal.state, supersedes=signal.supersedes,
        expires_at=signal.expires_at, evaluated_at=require_aware(evaluated_at, "evaluated_at"))


def record_of_normalized(signal: Any, *, evaluated_at: datetime,
                         expires_at: datetime | None = None) -> LifecycleRecord:
    """A `NormalizedSignal` (L1.6.2) -> its lifecycle row, expiry planned from its own dates.

    This is the sweep's entry point: the normalized signal is where `subject_key` lives and
    where `attribution.evidence_authority_rank` (ALG-14, already computed once per event at
    L1.6.4) is available, so the row costs no re-derivation at all.
    """
    plan_at = expires_at if expires_at is not None else plan_expiry(
        signal.signal_type, occurred_at=signal.occurred_at,
        stated_date=getattr(signal, "primary_date", None)).expires_at
    rank = getattr(getattr(signal, "attribution", None), "evidence_authority_rank", 0) or 0
    return LifecycleRecord(
        org_id=signal.org_id, signal_id=signal_row_id(signal), subject_key=signal.subject_key,
        signal_type=signal.signal_type.value, authority_rank=int(rank),
        occurred_at=signal.occurred_at, state=ACTIVE, supersedes=None, expires_at=plan_at,
        evaluated_at=require_aware(evaluated_at, "evaluated_at"))


def signal_row_id(signal: Any) -> str:
    """The stable id for a normalized signal, content-addressed exactly as L1.6.8 addresses it.

    `qualification.signal_ref` already defines this form — `event_id : signal_type : subject_key`
    hashed — and it is reused rather than re-invented so a drop row and a lifecycle row name the
    SAME signal. A replayed sweep therefore updates its own lifecycle row instead of filing a
    second copy of the same signal under a fresh uuid.
    """
    from genios_engine.capture.esqe.qualification import signal_ref
    return signal_ref(signal)


def apply_to_signal(signal: QualifiedEnterpriseSignal, event: LifecycleEvent, *,
                    eval_time: datetime, supersedes: str | None = None,
                    expires_at: datetime | None = None) -> QualifiedEnterpriseSignal:
    """Move a live `QualifiedEnterpriseSignal` through the machine, in place.

    The object is mutated rather than copied on purpose: C-12 is `validate_assignment=True`
    precisely so a lifecycle write re-runs its validators, and `model_copy(update=...)` — the
    obvious alternative — SKIPS them, which would let this module write a state the contract
    refuses. The class docstring says so in as many words.

    `expires_at` may be supplied with an EXPIRE for a signal that never had one planned; the
    contract refuses `expired` with no clock, so the clock is written first and the state second.
    Returns the same object, so a caller can chain or ignore the return value safely.
    """
    rule = require(signal.state, event, signal_id=signal.signal_id)
    if event is LifecycleEvent.REVIVE:
        raise IllegalTransition(
            state=signal.state, event=event, reason=RefusalReason.REVIVE_REQUIRES_EXPIRED,
            why="a revive never writes to the old signal — call `revive` with the replacement, "
                "which is the row that carries the backward pointer",
            signal_id=signal.signal_id)
    if expires_at is not None:
        signal.expires_at = require_aware(expires_at, "expires_at")
    if event is LifecycleEvent.EXPIRE and signal.expires_at is None:
        raise ValueError(
            f"cannot expire {signal.signal_id}: it carries no expires_at, and ALG-19 expires on "
            "that clock — plan one with `plan_expiry` and pass it")
    if event is LifecycleEvent.EXPIRE and not signal.has_expired_by(eval_time):
        raise ValueError(
            f"cannot expire {signal.signal_id}: expires_at {signal.expires_at.isoformat()} is "
            f"after eval_time {require_aware(eval_time, 'eval_time').isoformat()}")
    if event is LifecycleEvent.SUPERSEDE and supersedes is not None:
        raise ValueError(
            "supersedes belongs on the NEW signal, which points back at this one — see the "
            "module docstring on pointer direction")
    signal.state = rule.to_state or signal.state
    return signal


def revive(expired: QualifiedEnterpriseSignal | LifecycleRecord,
           replacement: QualifiedEnterpriseSignal) -> QualifiedEnterpriseSignal:
    """Doc 06's REVIVE: new evidence on an expired signal becomes a NEW signal pointing back.

    The expired row is not touched — not its state, not its `expires_at`, not its `supersedes`.
    That is the acceptance criterion verbatim (*"revive creates a new signal id and does not
    mutate the expired row"*), and it is why the pointer direction had to be backward.

    Returns the replacement, with `supersedes` set.
    """
    state = expired.state
    old_id = expired.signal_id
    require(state, LifecycleEvent.REVIVE, signal_id=old_id)
    if replacement.signal_id == old_id:
        raise ValueError(
            f"a revival must be a NEW signal id — {old_id!r} was reused, which would rewrite the "
            "expired row rather than succeed it")
    replacement.supersedes = old_id
    return replacement


# =================================================================================================
# SUPERSESSION — the rule, and the chain it builds
# =================================================================================================

def supersedes_predecessor(newer: LifecycleRecord, older: LifecycleRecord) -> bool:
    """Doc 06's rule, in one place: *same `(subject_key, signal_type)` and
    `authority_rank >= the old one`.*

    The `>=` is the half that matters and the half that is easy to get wrong as `>`: two emails
    of the same class about the same renewal are equal rank, and the newer one must win, or the
    first message about a subject is the only one that is ever live. The refusal is the other
    direction — a newer Slack aside (rank 1) does NOT supersede a signed contract (rank 6),
    which is the exact inversion ALG-14's ladder exists to prevent.

    Ordering by `occurred_at` is WORLD time, and the `signal_id` tie-break makes two events that
    landed on the same instant order identically on every replay rather than by dict order.
    """
    if newer.key() != older.key() or newer.org_id != older.org_id:
        return False
    if newer.signal_id == older.signal_id:
        return False
    if (newer.occurred_at, newer.signal_id) <= (older.occurred_at, older.signal_id):
        return False
    return newer.authority_rank >= older.authority_rank


def _chronological(records: Iterable[LifecycleRecord]) -> tuple[LifecycleRecord, ...]:
    return tuple(sorted(records, key=lambda r: (r.occurred_at, r.signal_id)))


def resolve_chain(records: Sequence[LifecycleRecord],
                  start: LifecycleRecord | str | None = None) -> LifecycleRecord:
    """Walk a supersession chain A -> B -> C forwards and return the row that is current.

    Pointers are BACKWARD (see the module docstring), so "forward" means finding the record
    whose `supersedes` names the one in hand, repeatedly. A chain with no successor is already
    current; a cycle raises rather than looping, because a cycle in this graph means two rows
    each claim to replace the other and no answer to "what is current" exists.

    `start` may be a record or a `signal_id`; omitted, the walk begins at the OLDEST record,
    which is the useful default for "given everything I know about this subject, what stands".
    """
    if not records:
        raise ValueError("resolve_chain needs at least one record")
    by_id = {record.signal_id: record for record in records}
    successors: dict[str, LifecycleRecord] = {}
    for record in _chronological(records):
        if record.supersedes is not None:
            if record.supersedes in successors:
                raise ValueError(
                    f"two signals both supersede {record.supersedes!r} "
                    f"({successors[record.supersedes].signal_id}, {record.signal_id}) — the "
                    "chain forked and no single row is current")
            successors[record.supersedes] = record
    if start is None:
        current = _chronological(records)[0]
    elif isinstance(start, str):
        if start not in by_id:
            raise KeyError(f"{start!r} is not among the records given")
        current = by_id[start]
    else:
        current = start
    seen = {current.signal_id}
    while True:
        nxt = successors.get(current.signal_id)
        if nxt is None:
            return current
        if nxt.signal_id in seen:
            raise ValueError(f"supersession cycle through {nxt.signal_id!r}")
        seen.add(nxt.signal_id)
        current = nxt


# =================================================================================================
# THE SWEEP — expiry and supersession over one sync's signals, against what is already stored
# =================================================================================================

@dataclass(frozen=True, slots=True)
class LifecycleOutcome:
    """What one sweep did to one tenant's lifecycle. Empty is a legitimate answer."""

    org_id: str
    eval_time: datetime | None
    #: Every state move this sweep made to a row that already existed or arrived in it.
    transitions: tuple[LifecycleTransition, ...] = ()
    #: The rows as they now stand — new signals plus every row a transition moved. This is what
    #: the store writes; nothing else in this outcome is persisted.
    records: tuple[LifecycleRecord, ...] = ()

    @property
    def superseded(self) -> tuple[LifecycleTransition, ...]:
        return tuple(t for t in self.transitions if t.event is LifecycleEvent.SUPERSEDE)

    @property
    def expired(self) -> tuple[LifecycleTransition, ...]:
        return tuple(t for t in self.transitions if t.event is LifecycleEvent.EXPIRE)


def apply_expiries(records: Sequence[LifecycleRecord], *, eval_time: datetime
                   ) -> tuple[tuple[LifecycleTransition, ...], tuple[LifecycleRecord, ...]]:
    """EXPIRE every active row whose own clock has run out as of `eval_time`.

    Runs BEFORE supersession, and the order is load-bearing: a signal that died of its clock
    last month must keep saying so, rather than being relabelled `superseded` by whatever
    happened to arrive today. Doc 06 gives expiry its own state for exactly that reason.
    """
    transitions: list[LifecycleTransition] = []
    out: list[LifecycleRecord] = []
    for record in _chronological(records):
        if record.is_live and has_expired(record.expires_at, eval_time):
            move = advance(record, LifecycleEvent.EXPIRE, eval_time=eval_time)
            transitions.append(move)
            out.append(move.after)
        else:
            out.append(record)
    return tuple(transitions), tuple(out)


def apply_supersessions(records: Sequence[LifecycleRecord], *, eval_time: datetime
                        ) -> tuple[tuple[LifecycleTransition, ...], tuple[LifecycleRecord, ...]]:
    """Within each `(subject_key, signal_type)`, let newer signals replace older ones.

    One pass in world-time order per key, carrying the row that currently STANDS. A newer signal
    of at least equal authority supersedes what stands and becomes what stands; a newer signal
    of LOWER authority supersedes nothing, stays active on its own account, and leaves the
    higher-authority row standing — a Slack aside does not retire a signed contract, and it also
    does not disappear, because it is still a thing somebody said.

    Only `active` rows can stand: an expired or resolved row is not a supersession target (the
    table refuses those events), so the walk skips them and the next live row takes over.
    """
    by_key: dict[tuple[str, str, str], list[LifecycleRecord]] = {}
    for record in records:
        by_key.setdefault((record.org_id, *record.key()), []).append(record)

    transitions: list[LifecycleTransition] = []
    current: dict[str, LifecycleRecord] = {r.signal_id: r for r in records}
    for group in by_key.values():
        standing: LifecycleRecord | None = None
        for record in _chronological(group):
            live = current[record.signal_id]
            if not live.is_live:
                continue
            if standing is None:
                standing = live
                continue
            if not supersedes_predecessor(live, standing):
                continue
            move = advance(standing, LifecycleEvent.SUPERSEDE, eval_time=eval_time,
                           caused_by=live.signal_id)
            transitions.append(move)
            current[standing.signal_id] = move.after
            # The pointer is written ONCE, at the moment a signal first replaces something. A
            # stored row that already carries one is left alone: it was written when that
            # supersession happened, and rewriting it now would move a historical link to
            # whatever this sweep happened to walk past.
            pointer = live.supersedes if live.supersedes is not None else standing.signal_id
            standing = replace(live, supersedes=pointer)
            current[live.signal_id] = standing
    ordered = tuple(current[r.signal_id] for r in _chronological(records))
    return tuple(transitions), ordered


class LifecycleStore(Protocol):
    """The persistence seam. Two writes and two reads, and no lifecycle logic behind any of them
    — a store that decided a state would be a second state machine nobody could see."""

    def put(self, rows: Sequence[LifecycleRecord]) -> int: ...

    def open_for(self, org_id: str,
                 keys: Sequence[tuple[str, str]]) -> list[LifecycleRecord]: ...

    def list(self, org_id: str, subject_key: str | None = None) -> list[LifecycleRecord]: ...

    def get(self, org_id: str, signal_id: str) -> LifecycleRecord | None: ...


class InMemoryLifecycleStore:
    """The dev/test store. A dict keyed exactly as the table is (`org_id`, `signal_id`), so a
    replayed sweep upserts here for the same reason it upserts in Postgres."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], LifecycleRecord] = {}

    def put(self, rows: Sequence[LifecycleRecord]) -> int:
        for row in rows:
            self._rows[(row.org_id, row.signal_id)] = row
        return len(rows)

    def open_for(self, org_id: str, keys: Sequence[tuple[str, str]]) -> list[LifecycleRecord]:
        wanted = set(keys)
        return [row for row in self._rows.values()
                if row.org_id == org_id and row.is_live and row.key() in wanted]

    def list(self, org_id: str, subject_key: str | None = None) -> list[LifecycleRecord]:
        rows = [row for row in self._rows.values()
                if row.org_id == org_id
                and (subject_key is None or row.subject_key == subject_key)]
        return sorted(rows, key=lambda r: (r.occurred_at, r.signal_id))

    def get(self, org_id: str, signal_id: str) -> LifecycleRecord | None:
        return self._rows.get((org_id, signal_id))


_COLUMNS = ("org_id, signal_id, subject_key, signal_type, authority_rank, occurred_at, "
            "state, supersedes, expires_at, evaluated_at")


class PostgresLifecycleStore:
    """`signal_lifecycle` (migration 0093), on `PostgresDropLedger`'s terms.

    `put` upserts on `(org_id, signal_id)`: a replayed sweep must re-state a signal's lifecycle,
    not append a second opinion about it. It logs and returns 0 on a database error rather than
    raising into the ingestion path — losing a lifecycle write costs a stale signal one more
    sweep of life, and raising costs the tenant their mail.
    """

    def __init__(self, database_url: str) -> None:
        from genios_engine.platform.db import get_engine
        self._engine = get_engine(database_url)

    def put(self, rows: Sequence[LifecycleRecord]) -> int:
        from sqlalchemy import text
        if not rows:
            return 0
        try:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(text(
                        f"insert into {LIFECYCLE_TABLE} ({_COLUMNS}) values "
                        "(:o, :sig, :sub, :st, :rank, :occ, :state, :sup, :exp, :at) "
                        "on conflict (org_id, signal_id) do update set "
                        "state=excluded.state, supersedes=excluded.supersedes, "
                        "expires_at=excluded.expires_at, evaluated_at=excluded.evaluated_at, "
                        "authority_rank=excluded.authority_rank"),
                        {"o": row.org_id, "sig": row.signal_id, "sub": row.subject_key,
                         "st": row.signal_type, "rank": row.authority_rank,
                         "occ": row.occurred_at, "state": row.state, "sup": row.supersedes,
                         "exp": row.expires_at, "at": row.evaluated_at})
        except Exception as exc:      # noqa: BLE001 — a lifecycle write never kills a sweep
            _log.warning("could not write %d lifecycle row(s) for org=%s: %s",
                         len(rows), rows[0].org_id, exc)
            return 0
        return len(rows)

    def open_for(self, org_id: str, keys: Sequence[tuple[str, str]]) -> list[LifecycleRecord]:
        from sqlalchemy import text
        if not keys:
            return []
        subjects = sorted({key[0] for key in keys})
        types = sorted({key[1] for key in keys})
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_COLUMNS} from {LIFECYCLE_TABLE} where org_id=:o and state='active' "
                "and subject_key = any(:subs) and signal_type = any(:types) "
                "order by occurred_at, signal_id"),
                {"o": org_id, "subs": subjects, "types": types}).all()
        wanted = set(keys)
        return [r for r in (_to_record(row) for row in rows) if r.key() in wanted]

    def list(self, org_id: str, subject_key: str | None = None) -> list[LifecycleRecord]:
        from sqlalchemy import text
        clause = " and subject_key=:sub" if subject_key else ""
        params: dict[str, Any] = {"o": org_id}
        if subject_key:
            params["sub"] = subject_key
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                f"select {_COLUMNS} from {LIFECYCLE_TABLE} where org_id=:o{clause} "
                "order by occurred_at, signal_id"), params).all()
        return [_to_record(row) for row in rows]

    def get(self, org_id: str, signal_id: str) -> LifecycleRecord | None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(text(
                f"select {_COLUMNS} from {LIFECYCLE_TABLE} "
                "where org_id=:o and signal_id=:sig"),
                {"o": org_id, "sig": signal_id}).first()
        return _to_record(row) if row is not None else None


def _to_record(row: Any) -> LifecycleRecord:
    return LifecycleRecord(
        org_id=row.org_id, signal_id=row.signal_id, subject_key=row.subject_key,
        signal_type=row.signal_type, authority_rank=int(row.authority_rank),
        occurred_at=row.occurred_at, state=row.state, supersedes=row.supersedes,
        expires_at=row.expires_at, evaluated_at=row.evaluated_at)


def lifecycle_records_for(summary: Any, *, eval_time: datetime) -> tuple[LifecycleRecord, ...]:
    """Every normalized signal this sweep produced, as an ACTIVE lifecycle row with its expiry
    already planned from its own dates.

    One try/except per SIGNAL rather than one around the loop, on `scored_signals_for`'s terms:
    a signal whose dates cannot be read costs itself a lifecycle row, never the other forty-nine
    theirs.
    """
    rows: list[LifecycleRecord] = []
    for result in getattr(summary, "results", ()) or ():
        esqe = getattr(result, "esqe", None)
        for signal in (getattr(esqe, "normalized", ()) if esqe is not None else ()):
            try:
                rows.append(record_of_normalized(signal, evaluated_at=eval_time))
            except Exception:      # noqa: BLE001
                _log.warning("could not build a lifecycle row for a %s signal",
                             getattr(signal, "signal_type", "?"), exc_info=True)
    return tuple(rows)


def sweep_lifecycle(summary: Any, *, org_id: str, store: LifecycleStore | None = None,
                    eval_time: datetime | None = None) -> LifecycleOutcome:
    """THE SEAM. One sweep's signals, aged and superseded against what this tenant already holds.

    A function over the SUMMARY, on `qualify_sweep`'s and `persist_sweep_conflicts`'s terms: it
    is called from `api/routes._run_ledger`, the one hook every `run_sync` caller in the HTTP
    layer already passes, so "the lifecycle ran" does not depend on which of the six sync call
    sites remembered to ask for it.

    The instant is the sweep's own frozen one (`qualification.sweep_eval_time` — ALG-12's
    `detected_at`, else the latest world time in the batch), REUSED rather than re-derived so a
    drop row, a conflict row and a lifecycle row all agree about when the sweep happened.

    Never raises. A sweep whose lifecycle cannot be computed keeps its mail and reports nothing.
    """
    from genios_engine.capture.esqe.qualification import sweep_eval_time
    try:
        instant = eval_time if eval_time is not None else sweep_eval_time(summary)
        if instant is None:
            return LifecycleOutcome(org_id=org_id, eval_time=None)
        incoming = lifecycle_records_for(summary, eval_time=instant)
        if not incoming:
            return LifecycleOutcome(org_id=org_id, eval_time=instant)
        existing: list[LifecycleRecord] = []
        if store is not None:
            fresh = {row.signal_id for row in incoming}
            existing = [row for row in store.open_for(org_id, [r.key() for r in incoming])
                        if row.signal_id not in fresh]
        expired_moves, aged = apply_expiries((*existing, *incoming), eval_time=instant)
        super_moves, final = apply_supersessions(aged, eval_time=instant)
        outcome = LifecycleOutcome(org_id=org_id, eval_time=instant,
                                   transitions=(*expired_moves, *super_moves), records=final)
    except Exception:      # noqa: BLE001 — downstream of capture, never above it
        _log.warning("lifecycle failed for org=%s", org_id, exc_info=True)
        return LifecycleOutcome(org_id=org_id, eval_time=None)
    if store is not None:
        store.put(outcome.records)
    return outcome


def outcome_digest(outcome: LifecycleOutcome) -> str:
    """A stable fingerprint of what a sweep decided — the replay check, in one call.

    Two runs of the same sweep at the same `eval_time` must produce byte-identical lifecycles;
    this is what a test (and an operator comparing two environments) compares instead of
    eyeballing a list of records.
    """
    payload = [
        {"signal_id": r.signal_id, "state": r.state, "supersedes": r.supersedes,
         "expires_at": r.expires_at.isoformat() if r.expires_at else None}
        for r in sorted(outcome.records, key=lambda r: r.signal_id)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


__all__ = [
    "ACTIVE", "DATED_TYPES", "DEFAULT_EXPIRY_WINDOW_DAYS", "EXPIRED", "EXPIRY_WINDOW_DAYS",
    "LIFECYCLE_TABLE", "RESOLVED", "SUPERSEDED", "TERMINAL_STATES", "TRANSITIONS",
    "ExpiryBasis", "ExpiryPlan", "IllegalTransition", "InMemoryLifecycleStore",
    "LifecycleEvent", "LifecycleOutcome", "LifecycleRecord", "LifecycleStore",
    "LifecycleTransition", "PostgresLifecycleStore", "RefusalReason", "TransitionRule",
    "UnknownLifecycleState",
    "advance", "apply_expiries", "apply_supersessions", "apply_to_signal", "can", "evaluate",
    "expiry_window_days", "has_expired", "lifecycle_records_for", "outcome_digest",
    "plan_expiry", "record_of", "record_of_normalized", "require", "resolve_chain", "revive",
    "signal_row_id", "supersedes_predecessor", "sweep_lifecycle", "unruled_pairs",
]
