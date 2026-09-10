"""DM-03 — a question only one person can answer must reach that person.

    pytest tests/contracts/test_ask_decision_reaches_somebody.py -q

THE CATALOGUE'S CASE, verbatim: *"The audit gap matters, the owner is unavailable, and no
applicable backup rule establishes a substitute. Expected: request one precise decision from the
authorized manager."* An audit of this branch found that outcome had **no delivery route at all**:

    Outcome.ASK_DECISION — reachable and renderable as words only. No DeliveryVerdict,
    DeliveryLifecycle, ExecutionState or EscalationAction can carry it; `outcomes.INSTRUCTING`
    excludes it, so a question only a person with authority may answer never interrupts, never
    routes to that person, and waits in the queue exactly as long as a card saying nothing
    needed doing.

WHY IT WAS EXCLUDED, and why that reasoning was half right. `deliver/pipeline` gated the push on
`abstention.is_actionable`, which is True only for `prescriptive` and `predictive`. That gate was
written for a real failure — on one tenant 18 of 24 surfaced cards were abstentions while 28
prescriptive ones sat queued behind them. But it treats two different things as one:

    "we cannot tell, look at this"          — an abstention. Must not interrupt.
    "only you can decide, here is the ask"  — not an abstention. It IS the advice.

`outcomes.INTERRUPTS` draws that line, and `interrupts()` is now what the push gate reads.
`INSTRUCTING` is left alone: ASK_DECISION still does not instruct, and the two questions were
never the same one.

AND ONLY WHEN IT IS ADDRESSED. Every push already requires `draft["assignee"]`, so a review card
with nobody to ask still waits — a question addressed to no one is not a decision request, it is
the "a human must look" abstention the flood guard exists to keep off the surface.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.abstention import ABSTAINING, Level, is_actionable
from genios_engine.contracts.outcomes import (
    INSTRUCTING,
    INTERRUPTS,
    Outcome,
    interrupts,
    project,
)

pytestmark = pytest.mark.unit


# =============================================================================================
# The route that did not exist.
# =============================================================================================
def test_a_decision_request_may_interrupt():
    assert interrupts(Outcome.ASK_DECISION)
    assert Outcome.ASK_DECISION in INTERRUPTS


def test_a_review_card_projects_onto_it():
    """The seam. `abstention.Level.REVIEW` is what `card_builder` writes for a card that needs a
    human, and this is the projection the push gate now reads."""
    assert project("abstention.Level", Level.REVIEW) is Outcome.ASK_DECISION


def test_the_old_gate_would_still_refuse_it():
    """The regression this file exists to prevent. If somebody restores `is_actionable` as the
    push gate, ASK_DECISION goes dark again and no other test would notice."""
    assert not is_actionable(Level.REVIEW)
    assert Level.REVIEW in ABSTAINING


# =============================================================================================
# What must still NOT interrupt.
# =============================================================================================
def test_an_observation_still_waits_to_be_read():
    """18 of one tenant's 24 surfaced cards were these, with 28 prescriptive ones queued behind.
    The distinction is interruption, not visibility — observations stay queued and are read."""
    assert not interrupts(Outcome.EMIT_OBSERVATION)
    assert project("abstention.Level", Level.OBSERVATION) is Outcome.EMIT_OBSERVATION


@pytest.mark.parametrize("level", [Level.WAIT, Level.SUPPRESS])
def test_the_other_two_abstentions_never_interrupt(level):
    assert not interrupts(project("abstention.Level", level))


def test_an_unmapped_level_never_interrupts():
    """A layer may grow a value before the projection learns it. The honest answer is 'unmapped',
    and an unmapped outcome must fail closed rather than take somebody's attention."""
    assert project("abstention.Level", "some_new_level") is None
    assert not interrupts(None)


# =============================================================================================
# Interrupting and instructing are different questions.
# =============================================================================================
def test_asking_is_not_instructing():
    """`INSTRUCTING` is "the system is telling somebody what to do". A decision request is the
    opposite — it says the system may not decide. Folding them would either silence the question
    or make it an order."""
    assert Outcome.ASK_DECISION not in INSTRUCTING
    assert Outcome.ASK_DECISION in INTERRUPTS


def test_everything_that_instructs_also_interrupts():
    """An instruction nobody is shown is not an instruction."""
    assert INSTRUCTING <= INTERRUPTS


def test_the_two_prescriptive_levels_still_interrupt():
    for level in (Level.PRESCRIPTIVE, Level.PREDICTIVE):
        assert interrupts(project("abstention.Level", level)), level


def test_no_terminal_outcome_interrupts():
    """SUPPRESS and CANCEL end the situation. Interrupting somebody about a closed thing is the
    definition of noise."""
    from genios_engine.contracts.outcomes import TERMINAL

    assert not (TERMINAL & INTERRUPTS)


def test_every_abstention_level_projects_to_something():
    """A level with no projection would fall to `None` and silently never interrupt — which is
    the correct failure mode, but it must not be how a real level ends up handled."""
    for level in Level:
        assert project("abstention.Level", level) is not None, level


# =============================================================================================
# The gate the delivery pipeline actually reads.
# =============================================================================================
def test_the_pipeline_imports_the_vocabulary_rather_than_re_deciding():
    """`contracts/outcomes` shipped with eleven outcomes, forty-two tests and ZERO importers in
    genios_engine/ — the branch's signature defect, in the module written to name outcomes. This
    asserts the seam that fixed it, and `tests/test_nothing_is_written_and_never_read.py` keeps
    it from going dark again."""
    import inspect

    from genios_engine.deliver import pipeline

    source = inspect.getsource(pipeline)
    assert "from genios_engine.contracts.outcomes import" in source
    assert "if not interrupts(outcome):" in source
