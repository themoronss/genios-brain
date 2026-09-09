"""THE ONE PLACE THAT NAMES WHAT HAPPENED TO A SITUATION.

**Why this module exists.** A failure inventory asks every test case to expect exactly one
outcome — emitted, held, suppressed, deferred, escalated, cancelled, abstained, refused for want
of authority. That sentence cannot be written as an assertion against this codebase, because the
outcomes are real and they are spread across six vocabularies in four contracts:

    contracts/abstention.py   Level               prescriptive predictive observation review
                                                  wait suppress
    contracts/delivery.py     DeliveryVerdict     send defer suppress
    contracts/delivery.py     DeliveryLifecycle       queued deferred delivered viewed ignored
                                                  accepted executed failed suppressed cancelled
                                                  expired
    contracts/reasoning.py    DecisionOutcome     decision no_action defer insufficient_context
                                                  blocked failed
    contracts/execution.py    (two enums)         escalate … cancelled
    contracts/authority.py    NO_AUTHORITY_RULE   a bare string constant

`defer` is declared twice and means two different things; `cancelled` is declared twice and means
roughly one; `escalate` is declared twice inside a single file. **And `retry` is nowhere** — the
outbox has a retry ladder for transport failures, but no layer can ever SAY "this was a transient
failure, the intelligence stands". A test asserting `RETRY` has nothing to assert against.

**This module does not replace any of them.** Each existing enum is correct for its own layer and
rewriting them would be a migration, not a clarification. What was missing is the projection: a
canonical name for what happened, and the mapping from every layer's own word onto it. That makes
two things possible that were not — a test can state its expected outcome once, and a gap can be
NAMED rather than discovered per test.

**The projection is deliberately lossy in one direction only.** Many layer values map onto one
outcome (`suppressed`, `expired` and a `SUPPRESS` level are all `SUPPRESS`), and no layer value
maps onto two. Where a layer cannot express an outcome at all, `UNEXPRESSED_BY` says so, and that
set is the honest answer to "is the system ready for this inventory".
"""

from __future__ import annotations

from enum import StrEnum


class Outcome(StrEnum):
    """What happened to one situation, in the vocabulary a test case states."""

    #: Evidence supports a specific recommended action. `abstention.Level.PRESCRIPTIVE`, and
    #: `PREDICTIVE` — a warning about a trajectory still tells the reader to act on it.
    EMIT_ACTION = "emit_action"
    #: The situation matters and the evidence will not carry a prescription.
    EMIT_OBSERVATION = "emit_observation"
    #: A human with authority must decide. Distinct from `EMIT_OBSERVATION`: the system is not
    #: merely declining to advise, it is naming a question only a person may answer.
    ASK_DECISION = "ask_decision"
    #: A potential situation, waiting on named evidence that has not arrived. Distinct from
    #: `DEFER`: this is "not yet TRUE", not "not yet the right moment".
    HOLD = "hold"
    #: Noise, irrelevant, or below the importance floor. A deliberate refusal, not a silence.
    SUPPRESS = "suppress"
    #: The intelligence is valid and complete and this is the wrong instant to interrupt.
    DEFER = "defer"
    #: A connector, model or tool failed transiently. The intelligence is unaffected.
    RETRY = "retry"
    #: A recovery window is closing, or the responsible party did not act.
    ESCALATE = "escalate"
    #: Resolved, expired, superseded or invalidated. The situation is over.
    CANCEL = "cancel"
    #: The system cannot safely determine the answer and says so.
    ABSTAIN = "abstain"
    #: The recommendation may be sound; the system has no authority to execute it.
    NO_AUTHORITY = "no_authority"


#: Outcomes that put an instruction in front of a person. Everything else is the system declining,
#: waiting, refusing or reporting a mechanical failure — and a surface that renders the two the
#: same way is the failure this whole vocabulary exists to make testable.
INSTRUCTING: frozenset[Outcome] = frozenset({Outcome.EMIT_ACTION, Outcome.ESCALATE})

#: Outcomes that end the situation. Nothing further is expected for this instance.
TERMINAL: frozenset[Outcome] = frozenset({Outcome.SUPPRESS, Outcome.CANCEL})

#: Outcomes that are about the MACHINERY rather than the situation. A test that expects one of
#: these is asserting about infrastructure, and a system that reports them as if the intelligence
#: were wrong has made the mistake `LRN-07` names.
MECHANICAL: frozenset[Outcome] = frozenset({Outcome.RETRY, Outcome.NO_AUTHORITY})


#: ── THE PROJECTION ───────────────────────────────────────────────────────────────────────────
#: Every value each layer can produce, mapped onto the canonical outcome. Keyed by the enum's
#: qualified name so a reader can see at a glance which layer is being projected, and so two
#: layers using the same word — `defer`, `cancelled`, `suppress` — cannot collide.
PROJECTION: dict[str, dict[str, Outcome]] = {
    "abstention.Level": {
        "prescriptive": Outcome.EMIT_ACTION,
        "predictive": Outcome.EMIT_ACTION,
        "observation": Outcome.EMIT_OBSERVATION,
        "review": Outcome.ASK_DECISION,
        "wait": Outcome.HOLD,
        "suppress": Outcome.SUPPRESS,
    },
    "delivery.DeliveryVerdict": {
        "send": Outcome.EMIT_ACTION,
        # THE ONE THAT WAS AMBIGUOUS. Delivery's `defer` is "not now" about the MOMENT, which is
        # the inventory's DEFER. Reasoning's identically-spelled value is not — see below.
        "defer": Outcome.DEFER,
        "suppress": Outcome.SUPPRESS,
    },
    "delivery.DeliveryLifecycle": {
        "queued": Outcome.EMIT_ACTION,
        "deferred": Outcome.DEFER,
        "delivered": Outcome.EMIT_ACTION,
        "viewed": Outcome.EMIT_ACTION,
        "ignored": Outcome.EMIT_ACTION,
        "accepted": Outcome.EMIT_ACTION,
        "executed": Outcome.EMIT_ACTION,
        # A transport failure, not a judgement about the situation.
        "failed": Outcome.RETRY,
        "suppressed": Outcome.SUPPRESS,
        "cancelled": Outcome.CANCEL,
        "expired": Outcome.CANCEL,
    },
    "execution.ExecutionState": {
        "created": Outcome.EMIT_ACTION,
        "pending": Outcome.EMIT_ACTION,
        "running": Outcome.EMIT_ACTION,
        # "acted on, waiting for the world to respond" is not the system waiting for evidence —
        # the action HAPPENED. It stays an emission until the world answers.
        "waiting": Outcome.EMIT_ACTION,
        # A dependency or an explicit human block. The recommendation stands; we may not proceed.
        "blocked": Outcome.NO_AUTHORITY,
        "completed": Outcome.EMIT_ACTION,
        "cancelled": Outcome.CANCEL,
        "expired": Outcome.CANCEL,
        "archived": Outcome.CANCEL,
    },
    "execution.EscalationAction": {
        "notify": Outcome.EMIT_ACTION,
        "remind": Outcome.EMIT_ACTION,
        "escalate": Outcome.ESCALATE,
        "critical": Outcome.ESCALATE,
    },
    "reasoning.DecisionOutcome": {
        "decision": Outcome.EMIT_ACTION,
        # NOT `SUPPRESS`. "The formula ran and chose to do nothing" is a considered non-action the
        # reader should be able to see, which is what an observation is for.
        "no_action": Outcome.EMIT_OBSERVATION,
        # NOT the inventory's DEFER. Reasoning defers because the SITUATION is not yet decidable —
        # that is HOLD. Delivery defers because the MOMENT is wrong. Two words, one spelling, and
        # collapsing them is how "we waited for evidence" becomes "we waited for a better time".
        "defer": Outcome.HOLD,
        "insufficient_context": Outcome.ABSTAIN,
        "blocked": Outcome.NO_AUTHORITY,
        "failed": Outcome.RETRY,
    },
}

#: ── THE GAPS ─────────────────────────────────────────────────────────────────────────────────
#: For each outcome, the vocabularies that CANNOT produce it. **Computed, never hand-written.**
#:
#: The first draft of this map was written by hand and its own test caught three errors in it
#: inside a minute — which is the argument for computing it: a gap list that drifts is worse than
#: none, because it is read as a statement about the code.
#:
#: WHAT IT SHOWS, and it is the measured answer to "is the system ready for the inventory":
#: `ESCALATE` is produced by `execution.EscalationAction` and by NOTHING a card or a delivery
#: surface reads, so an escalation renders as an ordinary instruction. `RETRY` is reachable only
#: from a FAILURE state — no layer has a verdict meaning "the connector was down, the intelligence
#: stands". `ASK_DECISION` exists only as an abstention `Level`; neither delivery nor reasoning can
#: say it, so a decision the founder must make cannot be routed as one.
UNEXPRESSED_BY: dict["Outcome", tuple[str, ...]] = {}


def _compute_gaps() -> None:
    for outcome in Outcome:
        cannot = tuple(sorted(name for name, values in PROJECTION.items()
                              if outcome not in values.values()))
        if cannot:
            UNEXPRESSED_BY[outcome] = cannot


def project(vocabulary: str, value: str) -> Outcome | None:
    """One layer's own word → the canonical outcome. `None` when the value is unknown.

    `None` is not an error and must not be treated as one by a caller: a layer may legitimately
    grow a value before this projection learns it, and the honest report is "unmapped", never a
    guess at the nearest neighbour.
    """
    return PROJECTION.get(vocabulary, {}).get(str(value or "").strip().lower())


def expressible_by(outcome: Outcome) -> tuple[str, ...]:
    """The vocabularies that CAN produce this outcome, in declaration order."""
    return tuple(name for name, values in PROJECTION.items() if outcome in values.values())


def unreachable() -> tuple[Outcome, ...]:
    """Outcomes no vocabulary in the projection can produce at all.

    Empty once `execution` is projected. It was NOT empty before that: `ESCALATE` was reachable
    from no vocabulary this module knew, which is exactly the shape of the defect the map exists
    to expose — the value existed, in a contract nothing downstream reads.
    """
    return tuple(o for o in Outcome if not expressible_by(o))


_compute_gaps()


__all__ = [
    "INSTRUCTING",
    "MECHANICAL",
    "PROJECTION",
    "TERMINAL",
    "UNEXPRESSED_BY",
    "Outcome",
    "expressible_by",
    "project",
    "unreachable",
]
