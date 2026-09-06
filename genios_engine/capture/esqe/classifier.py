"""ALG-16 · L1.6.3-U1 — which of the fired predicates is the PRIMARY kind of this event.

One event legitimately produces several signals (doc 06, L1.6.1-U1: *"an email containing a
commitment and a deadline is two signals sharing one trace_id"*). Something still has to say
which one the card is ABOUT, because a reader is shown one headline and a downstream rule
branches on one `signal_type`. This module answers that, and it answers it with a **constant
order, not a score**.

WHY A CONSTANT AND NOT A SCORE
------------------------------
A score would make the primary type a function of numbers computed elsewhere — importance
weights, confidences, recency — so the same extraction could classify differently in March and
in September because a weight was retuned in between. The plan's own words: *"Precedence is a
constant, not a score, so it is reproducible."* Two runs over the same detected set return the
same primary and the same ordered secondaries, and that is asserted rather than assumed.

WHY THE TOP THREE ARE THE TOP THREE
-----------------------------------
Doc 06 states the rationale and `contracts/signal.py` repeats it: an INFORMATION_CONFLICT means
we may be about to tell a founder something false with a receipt that looks legitimate; an
ESCALATION is time-bound by nature; an APPROVAL_REQUESTED is blocking a human right now. All
three outrank every merely descriptive kind, which is why CONTRACT_RENEWAL — the single most
valuable kind commercially — still sits fourth.

WHY THE ORDER LIVES HERE AND NOT ON THE ENUM
--------------------------------------------
`contracts/signal.py` says so explicitly: the ALG-16 precedence and the ALG-17 weights are
deliberately NOT mirrored into the contract, because a second copy of an ordering is a second
place for it to be wrong. This module is the one copy, and `PRECEDENCE_COMPLETE` below fails
the import the moment a fifteenth member is added to the taxonomy without being placed in it —
an unplaced type would otherwise sort as "unknown" and silently outrank or under-rank
everything, which is exactly the class of drift the closed set exists to prevent.

Pure: no clock, no float, no database, no model.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from genios_engine.contracts.signal import SignalType

#: ALG-16's order, highest precedence first, verbatim from doc 06 L1.6.3-U1.
PRECEDENCE: tuple[SignalType, ...] = (
    SignalType.INFORMATION_CONFLICT,
    SignalType.ESCALATION,
    SignalType.APPROVAL_REQUESTED,
    SignalType.CONTRACT_RENEWAL,
    SignalType.COMMITMENT_DUE,
    SignalType.DECISION_PENDING,
    SignalType.FINANCIAL_OBLIGATION,
    SignalType.DEADLINE_STATED,
    SignalType.RISK_FLAGGED,
    SignalType.COMMITMENT_MADE,
    SignalType.DECISION_MADE,
    SignalType.OPPORTUNITY_SIGNAL,
    SignalType.RELATIONSHIP_CHANGE,
    SignalType.ANOMALY,
)

#: Import-time totality check. A taxonomy member with no precedence position is not a smaller
#: bug than a wrong position — it is an unrankable signal, and the failure would surface as a
#: `KeyError` inside a capture at 3am instead of here, on the line that added the member.
_MISSING = set(SignalType) - set(PRECEDENCE)
_DUPLICATED = len(PRECEDENCE) != len(set(PRECEDENCE))
if _MISSING or _DUPLICATED:                                            # pragma: no cover
    raise RuntimeError("ALG-16 precedence must list every SignalType exactly once; "
                       f"missing={sorted(t.value for t in _MISSING)} duplicated={_DUPLICATED}")

_RANK: dict[SignalType, int] = {kind: index for index, kind in enumerate(PRECEDENCE)}


@dataclass(frozen=True)
class SignalClassification:
    """One primary kind plus every other kind this event also is, in precedence order.

    Frozen and ordered: the secondaries are not a set, because the card renders them in this
    order and a set would hand two runs two different renderings of the same event.
    """

    #: The kind the event IS, for the headline and for any rule that branches on one type.
    primary: SignalType
    #: Everything else that fired, precedence-ordered, primary excluded. Never contains
    #: `primary`, never contains a duplicate.
    secondary_types: tuple[SignalType, ...]

    @property
    def all_types(self) -> tuple[SignalType, ...]:
        """Primary first, then the secondaries — the full precedence-ordered set."""
        return (self.primary, *self.secondary_types)


def precedence_rank(signal_type: SignalType) -> int:
    """0 for the highest-precedence kind. Exported so the detector's 5-per-event cap keeps the
    same order it will later be classified by, instead of inventing a second ranking."""
    return _RANK[signal_type]


def classify_signals(signal_types: Iterable[SignalType]) -> SignalClassification | None:
    """L1.6.3-U1 · pick the primary and record the rest. `None` when nothing was detected.

    `None` rather than a default kind: an event with no fired predicate is not an ANOMALY by
    fallback — ANOMALY is a predicate the detector either fired or did not — and manufacturing
    a type here would put a signal on the seam that no predicate ever claimed.

    Duplicates collapse: the detector may fire two predicates for the same kind (two commitments
    both due inside the horizon), and that is one kind, not two.
    """
    ordered = sorted({kind for kind in signal_types}, key=precedence_rank)
    if not ordered:
        return None
    return SignalClassification(primary=ordered[0], secondary_types=tuple(ordered[1:]))


__all__ = ["PRECEDENCE", "SignalClassification", "classify_signals", "precedence_rank"]
