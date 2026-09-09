"""The one place that names what happened to a situation.

    pytest tests/contracts/test_outcomes.py -q

A failure inventory asks every case to expect exactly one outcome. That sentence could not be
written as an assertion against this codebase: the outcomes are real and spread across six
vocabularies in four contracts, `defer` is declared twice meaning two different things,
`cancelled` twice, `escalate` twice inside one file, and `retry` is nowhere at all.

`contracts/outcomes.py` does not replace any of them — each is correct for its own layer and
rewriting them would be a migration. It adds the projection that was missing.

THE TEST THAT MATTERS IS THE DRIFT GUARD. A projection that silently returns `None` for a value
somebody added last week is worse than no projection, because every test asserting an outcome
would quietly stop asserting anything. So the coverage tests below enumerate the REAL enums and
fail on the first value this module has not been taught.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.abstention import Level
from genios_engine.contracts.delivery import DeliveryLifecycle, DeliveryVerdict
from genios_engine.contracts.execution import EscalationAction, ExecutionState
from genios_engine.contracts.outcomes import (
    INSTRUCTING,
    MECHANICAL,
    PROJECTION,
    TERMINAL,
    UNEXPRESSED_BY,
    Outcome,
    expressible_by,
    project,
    unreachable,
)
from genios_engine.contracts.reasoning import DecisionOutcome

pytestmark = pytest.mark.unit

#: The real enums, beside the projection key that claims to cover them. Adding a vocabulary to
#: `PROJECTION` without adding it here would leave it unguarded, so the last test in this file
#: checks the two lists are the same length.
REAL = (
    ("abstention.Level", Level),
    ("delivery.DeliveryVerdict", DeliveryVerdict),
    ("delivery.DeliveryLifecycle", DeliveryLifecycle),
    ("execution.ExecutionState", ExecutionState),
    ("execution.EscalationAction", EscalationAction),
    ("reasoning.DecisionOutcome", DecisionOutcome),
)


# =============================================================================================
# The drift guard.
# =============================================================================================
@pytest.mark.parametrize("key,enum", REAL, ids=[k for k, _ in REAL])
def test_every_value_the_real_enum_can_produce_is_projected(key, enum):
    """The whole point. A value this module has not been taught projects to `None`, and a test
    asserting an outcome against it would pass while asserting nothing."""
    unmapped = sorted(v.value for v in enum if project(key, v.value) is None)

    assert unmapped == [], f"{key} grew values the projection has not been taught: {unmapped}"


@pytest.mark.parametrize("key,enum", REAL, ids=[k for k, _ in REAL])
def test_the_projection_claims_no_value_the_enum_does_not_have(key, enum):
    """The other direction. A projected value that no longer exists is a stale entry that will
    never fire again, and it hides the fact that the real value was renamed."""
    real = {v.value for v in enum}
    invented = sorted(set(PROJECTION[key]) - real)

    assert invented == [], f"{key} projects values the enum does not have: {invented}"


def test_no_layer_value_maps_to_two_outcomes():
    """The projection is lossy in one direction only: many layer values may share an outcome, and
    no layer value may have two. Otherwise "what happened" has no answer."""
    for key, values in PROJECTION.items():
        for value, outcome in values.items():
            assert isinstance(outcome, Outcome), f"{key}.{value} is not an Outcome"


# =============================================================================================
# The semantic distinction the projection exists to preserve.
# =============================================================================================
def test_the_two_defers_are_not_the_same_outcome():
    """THE COLLISION THIS MODULE WAS WRITTEN FOR. Delivery defers because the MOMENT is wrong;
    reasoning defers because the SITUATION is not yet decidable. Collapsing them turns "we waited
    for evidence" into "we waited for a better time", which is a different promise to the user."""
    assert project("delivery.DeliveryVerdict", "defer") is Outcome.DEFER
    assert project("reasoning.DecisionOutcome", "defer") is Outcome.HOLD


def test_a_delivery_failure_is_mechanical_and_not_a_verdict_on_the_situation():
    """LRN-07's failure, in one assertion: a tool that fell over must not be learned as a bad
    recommendation."""
    assert project("delivery.DeliveryLifecycle", "failed") is Outcome.RETRY
    assert Outcome.RETRY in MECHANICAL


def test_a_considered_non_action_is_an_observation_not_a_suppression():
    """"The formula ran and chose to do nothing" is something the reader should be able to see.
    Suppression is the system deciding they should never have been shown it."""
    assert project("reasoning.DecisionOutcome", "no_action") is Outcome.EMIT_OBSERVATION


def test_expiry_and_cancellation_are_one_ending():
    assert project("delivery.DeliveryLifecycle", "expired") is Outcome.CANCEL
    assert project("delivery.DeliveryLifecycle", "cancelled") is Outcome.CANCEL


def test_only_two_outcomes_put_an_instruction_in_front_of_a_person():
    """A surface that renders an observation the way it renders an instruction is the failure the
    abstention vocabulary was built to prevent; this is the same guarantee, stated once."""
    assert INSTRUCTING == {Outcome.EMIT_ACTION, Outcome.ESCALATE}
    assert Outcome.EMIT_OBSERVATION not in INSTRUCTING
    assert Outcome.ASK_DECISION not in INSTRUCTING


def test_terminal_outcomes_end_the_situation():
    assert TERMINAL == {Outcome.SUPPRESS, Outcome.CANCEL}


# =============================================================================================
# The gap map — the measured answer to "is the system ready for this inventory".
# =============================================================================================
def test_every_outcome_is_reachable_from_at_least_one_layer():
    """True only because `execution` is projected. Before it was, `ESCALATE` was reachable from
    nothing this module knew — the value existed, in a contract nothing downstream reads."""
    assert unreachable() == ()


def test_the_gap_map_is_computed_from_the_projection():
    """`UNEXPRESSED_BY` is a claim about the code, so it is DERIVED from the code. The first draft
    was hand-written and this test caught three errors in it inside a minute."""
    for outcome, claimed in UNEXPRESSED_BY.items():
        cannot = {name for name, values in PROJECTION.items() if outcome not in values.values()}

        assert set(claimed) == cannot


def test_every_real_gap_is_named_and_no_invented_one_is():
    real_gaps = {o for o in Outcome if set(PROJECTION) - set(expressible_by(o))}

    assert set(UNEXPRESSED_BY) == real_gaps


# ---------------------------------------------------------------------------------------------
# The four findings. Each is a value that EXISTS in some contract and cannot be said by the layer
# that needs to say it — which is why the inventory's cases for them have nothing to assert
# against today. These tests are written to FAIL when that is fixed, so the fix cannot land
# silently.
# ---------------------------------------------------------------------------------------------
def test_delivery_cannot_tell_an_observation_from_an_instruction():
    """THE BIGGEST ONE. `DeliveryVerdict` is send / defer / suppress. There is no verdict for
    "deliver this, but it is an observation and must not read as a command" — which is precisely
    the failure `contracts/abstention.py` was written to prevent, one layer earlier."""
    assert "delivery.DeliveryVerdict" in UNEXPRESSED_BY[Outcome.EMIT_OBSERVATION]
    assert "delivery.DeliveryLifecycle" in UNEXPRESSED_BY[Outcome.EMIT_OBSERVATION]


def test_only_a_card_level_can_ask_for_a_decision():
    """`ASK_DECISION` exists once, as `abstention.Level.REVIEW`. Neither reasoning, delivery nor
    execution can say it, so "only the founder may answer this" cannot be routed as such."""
    assert expressible_by(Outcome.ASK_DECISION) == ("abstention.Level",)


def test_only_execution_can_escalate():
    """`ESCALATE` is `execution.EscalationAction` and nothing a card or delivery surface reads.
    An escalation therefore renders as an ordinary instruction."""
    assert expressible_by(Outcome.ESCALATE) == ("execution.EscalationAction",)
    assert "abstention.Level" in UNEXPRESSED_BY[Outcome.ESCALATE]
    assert "delivery.DeliveryVerdict" in UNEXPRESSED_BY[Outcome.ESCALATE]


def test_only_reasoning_can_abstain():
    """A card has no way to say "I cannot safely determine this" — `insufficient_context` is a
    reasoning outcome and stops there."""
    assert expressible_by(Outcome.ABSTAIN) == ("reasoning.DecisionOutcome",)


def test_retry_is_reachable_only_from_a_failure():
    """No layer has a verdict meaning "the connector was down, the intelligence stands". It is
    inferred from a transport or reasoning FAILURE, which is why SRC-01 and EXE-01 cannot be
    asserted today without conflating a broken tool with a bad recommendation."""
    assert set(expressible_by(Outcome.RETRY)) == {"delivery.DeliveryLifecycle",
                                                  "reasoning.DecisionOutcome"}


def test_reasoning_cannot_say_the_moment_is_wrong():
    """DEFER is a delivery-only concept. Reasoning's own `defer` means the situation is not yet
    decidable, which this projection maps to HOLD — so "correct intelligence, wrong instant" can
    only ever be decided at the delivery seam."""
    assert "reasoning.DecisionOutcome" in UNEXPRESSED_BY[Outcome.DEFER]
    assert "abstention.Level" in UNEXPRESSED_BY[Outcome.DEFER]


def test_an_unknown_value_projects_to_none_rather_than_a_guess():
    """`None` is not an error. A layer may grow a value before this module learns it, and the
    honest report is "unmapped", never the nearest neighbour."""
    assert project("abstention.Level", "not_a_level") is None
    assert project("no.such.vocabulary", "prescriptive") is None
    assert project("abstention.Level", "") is None


def test_projection_is_case_and_whitespace_tolerant():
    assert project("abstention.Level", "  PRESCRIPTIVE  ") is Outcome.EMIT_ACTION


def test_every_projected_vocabulary_is_guarded_by_this_file():
    """A vocabulary added to `PROJECTION` without being added to `REAL` above would be unguarded,
    and its drift would be invisible."""
    assert set(PROJECTION) == {key for key, _ in REAL}
