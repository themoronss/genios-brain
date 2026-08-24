"""What a card is CLAIMING — including the claim that it is not making one.

The engine could say two things: `prescriptive` ("do this") and `predictive` ("this may happen").
There was no third option, so with zero reviewed capabilities in the corpus, one hundred percent
of what reached a user was advice on domains the system held no accepted expertise for. It could
BLOCK a candidate — a suppression row nobody sees — but it had no way to SAY it did not know, and
those are different products.

The distinction the levels below draw is not about confidence. A low-confidence prescription is
still a prescription; the user reads it as an instruction and acts. Abstention is a different
KIND of output: it tells the user what was observed and explicitly declines to tell them what to
do, which is the only honest thing to emit when the evidence is thin, the expertise is unreviewed,
or the situation is outside coverage.
"""
from __future__ import annotations

from enum import StrEnum


class Level(StrEnum):
    """The authority a card claims, from an instruction down to a refusal."""

    #: "Do this." Requires accepted expertise and resolved evidence.
    PRESCRIPTIVE = "prescriptive"
    #: "This may happen." A warning about a trajectory, not an instruction.
    PREDICTIVE = "predictive"
    #: "Here is what is true." Surfaced because it matters, with no action attached — the
    #: correct output when the situation is real but the expertise to advise on it is not.
    OBSERVATION = "observation"
    #: "Something is missing or contradictory; a human must look." Names the exact question.
    REVIEW = "review"
    #: "Not yet." The situation is understood and the right move is to do nothing until a named
    #: trigger fires. Distinct from silence: the user can see the system chose to wait.
    WAIT = "wait"
    #: "Do not raise this again." A closed, resolved or explicitly-declined loop.
    SUPPRESS = "suppress"


#: Levels that instruct. Everything else is the system declining to instruct, and the delivery
#: surface must render the two differently — an observation shown as a command is the failure
#: this vocabulary exists to prevent.
ACTIONABLE: frozenset[str] = frozenset({Level.PRESCRIPTIVE, Level.PREDICTIVE})

#: Levels that are an explicit refusal to advise.
ABSTAINING: frozenset[str] = frozenset({Level.OBSERVATION, Level.REVIEW,
                                        Level.WAIT, Level.SUPPRESS})

VALID_LEVELS: frozenset[str] = frozenset(Level)


def is_actionable(level: str | None) -> bool:
    """Does this card claim the authority to tell someone what to do?"""
    return str(level or "") in ACTIONABLE


def downgrade_to_observation(level: str | None, *, reason: str) -> tuple[str, str]:
    """Strip a card's authority to instruct, keeping what it observed.

    Used when the expertise behind a recommendation is not accepted, or its evidence does not
    survive validation. Returns the new level and the reason, because an abstention with no
    stated cause is indistinguishable from a bug — the user needs to know whether the system
    lacks coverage, lacks evidence, or is deliberately holding.
    """
    if not is_actionable(level):
        return str(level or Level.OBSERVATION), reason
    return str(Level.OBSERVATION), reason
