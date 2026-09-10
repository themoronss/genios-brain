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

#: Outcomes that justify INTERRUPTING a person, as opposed to waiting to be read.
#:
#: `INSTRUCTING` above is a different question — it asks whether the system is telling somebody
#: what to do. `ASK_DECISION` is not instructing and it must still interrupt: a question only a
#: person with authority can answer is not an abstention from advising, it IS the advice, and a
#: question that waits in a queue is a question nobody answers.
#:
#: THE CASE THIS EXISTS FOR is the catalogue's DM-03, "no backup authority exists": *"Request one
#: precise decision from the authorized manager."* Before this set, `deliver/pipeline` gated the
#: push on `abstention.is_actionable`, which is False for `review` — so the one card whose entire
#: purpose is to reach a named human never reached one.
#:
#: `EMIT_OBSERVATION` is deliberately absent, and that half is not a defect. An observation card
#: says "here is something true, nobody needs to act" and 18 of one tenant's 24 surfaced cards
#: were those, with 28 prescriptive ones queued behind them. Abstaining cards stay queued and are
#: read when the user opens the app; the distinction is interruption, not visibility.
INTERRUPTS: frozenset[Outcome] = frozenset({
    Outcome.EMIT_ACTION, Outcome.ASK_DECISION, Outcome.ESCALATE})


def interrupts(outcome: "Outcome | None") -> bool:
    """May this outcome take somebody's attention now? Unknown never interrupts."""
    return outcome in INTERRUPTS


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
#:
#: WHAT IT DOES NOT SHOW, and an earlier draft of this file claimed it did. "Delivery cannot tell
#: an observation from an instruction" is too strong: `deliver/pipeline.py` checks
#: `abstention.is_actionable` before it pushes, so an abstaining card genuinely does not interrupt.
#: The `DeliveryVerdict` cannot carry the distinction, but a separate guard does. The real defect
#: is narrower and worse — see `resolve`.
UNEXPRESSED_BY: dict["Outcome", tuple[str, ...]] = {}


def _compute_gaps() -> None:
    for outcome in Outcome:
        cannot = tuple(sorted(name for name, values in PROJECTION.items()
                              if outcome not in values.values()))
        if cannot:
            UNEXPRESSED_BY[outcome] = cannot


#: ── PRECEDENCE ───────────────────────────────────────────────────────────────────────────────
#: THE DEFECT `resolve` EXISTS FOR. What happened to one situation is decided in several places in
#: several vocabularies, and nothing folds them into one answer. `deliver/pipeline.py` consults
#: `abstention.is_actionable` to decide whether to interrupt; `deliver/gate.py` independently
#: produces a `DeliveryVerdict`; `reason` has already recorded a `DecisionOutcome`; the lifecycle
#: row carries its own state. A card can therefore be `SEND` by verdict, not-pushed by abstention
#: and `no_action` by reasoning at the same instant, and "what happened to this situation" has
#: three answers — which is exactly why the inventory's "expect exactly one outcome" could not be
#: written.
#:
#: The order below is by HOW MUCH EACH OVERRIDES, not by which layer runs last. A cancelled
#: situation is cancelled whatever the card said. A suppressed one was deliberately refused. A
#: transport failure means nothing has happened yet and no judgement about the situation should be
#: read from it. Only when nothing overrides does the card's own claim decide.
RANK: tuple[Outcome, ...] = (
    Outcome.CANCEL,          # the situation is over; nothing else about it matters
    Outcome.SUPPRESS,        # deliberately refused
    Outcome.RETRY,           # the machinery failed; there is no verdict on the situation yet
    Outcome.NO_AUTHORITY,    # we may not proceed, whatever we would have advised
    Outcome.DEFER,           # valid and complete; wrong instant
    Outcome.ESCALATE,        # being handed up
    Outcome.ASK_DECISION,    # a person must answer
    Outcome.ABSTAIN,         # we cannot safely determine it
    Outcome.HOLD,            # not yet true
    Outcome.EMIT_OBSERVATION,  # true, and we will not prescribe
    Outcome.EMIT_ACTION,     # everything agreed
)


def implied(**signals: str | None) -> dict[str, Outcome]:
    """Every outcome the given layer values imply, keyed by vocabulary.

    Call as `implied(**{"abstention.Level": "observation", ...})`. Unknown or absent values are
    dropped rather than guessed — see `project`.
    """
    out: dict[str, Outcome] = {}
    for vocabulary, value in signals.items():
        if value is None:
            continue
        outcome = project(vocabulary, value)
        if outcome is not None:
            out[vocabulary] = outcome
    return out


def resolve(**signals: str | None) -> Outcome | None:
    """The single canonical outcome for one situation. `None` when nothing was said at all.

    This is the function that makes "expect exactly one outcome" writable. It does not change any
    layer's behaviour; it states, in one place and by a documented precedence, what the layers
    together mean.
    """
    seen = set(implied(**signals).values())
    if not seen:
        return None
    for outcome in RANK:
        if outcome in seen:
            return outcome
    return None                                            # pragma: no cover - RANK is total


def disagreements(**signals: str | None) -> tuple[Outcome, ...]:
    """The outcomes the layers imply that the resolution DISCARDED, in rank order.

    Empty means every layer agreed. Non-empty is not automatically a bug — a cancelled situation
    whose card said `prescriptive` is a perfectly ordinary race — but it is the set a test asserts
    on when the inventory asks "which layer first got this wrong".
    """
    seen = set(implied(**signals).values())
    winner = resolve(**signals)
    return tuple(o for o in RANK if o in seen and o is not winner)


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
