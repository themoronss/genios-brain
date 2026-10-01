"""S3.F3.1 · the five output lanes — and the two things they must never be confused with.

    pytest tests/contracts/test_the_output_lanes_are_not_the_outcomes.py -q

⛔ TWO COLLISIONS, BOTH MEASURED BEFORE THIS WAS WRITTEN.

  1. `DecisionOutcome` has six members and `ReasoningDecision`'s docstring defends them: *"A projection
     that only carries `decision` loses five sixths of the vocabulary."* The lanes are on a DIFFERENT
     AXIS — a `decision` outcome routes to DECISION or MONITOR depending on confidence.
  2. `reason/uncited_lanes.py` already means something else by "lane" — whether a PACK lane can cite an
     authored expert — and its docstring records what that conflation cost: *"Layer 2 lost five
     readings to exactly that ambiguity."*
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.reasoning import (OUTPUT_LANES, DecisionOutcome, OutputLane,
                                               ReasoningDecision)

pytestmark = pytest.mark.unit


# =================================================================================================
# 1 · ⛔ the lanes are not the outcomes
# =================================================================================================
def test_the_two_vocabularies_are_different_sizes_and_different_things():
    assert len(OUTPUT_LANES) == 5
    assert len(list(DecisionOutcome)) == 6


def test_only_one_word_is_shared_and_it_means_two_things():
    """`decision` appears in both, and that is exactly why they cannot be one field: the outcome
    `decision` may route to the MONITOR lane."""
    shared = {lane.value for lane in OUTPUT_LANES} & {o.value for o in DecisionOutcome}
    assert shared == {"decision"}


def test_no_lane_was_named_after_an_outcome_that_is_not_a_lane():
    """⛔ If `no_action`, `defer`, `insufficient_context`, `blocked` or `failed` appeared as a lane, the
    two axes would have been merged and five sixths of the outcome vocabulary lost."""
    lanes = {lane.value for lane in OUTPUT_LANES}
    for outcome in ("no_action", "defer", "insufficient_context", "blocked", "failed"):
        assert outcome not in lanes


def test_the_decision_still_carries_both_fields_separately():
    fields = ReasoningDecision.__dataclass_fields__
    assert "outcome" in fields
    assert "output_lane" in fields
    assert fields["output_lane"].type != fields["outcome"].type


# =================================================================================================
# 2 · ⛔ the vocabulary is closed
# =================================================================================================
def test_the_enum_and_the_tuple_agree():
    """Two lists that must agree forever will eventually disagree. This is the test that notices."""
    assert set(OUTPUT_LANES) == set(OutputLane)


def test_every_lane_is_a_plain_string_value():
    for lane in OUTPUT_LANES:
        assert isinstance(lane.value, str) and lane.value == lane.value.lower()


def test_the_five_are_exactly_these():
    assert [lane.value for lane in OUTPUT_LANES] == [
        "decision", "investigation", "conflict", "monitor", "suppress"]


# =================================================================================================
# 3 · ⛔ never a bare `lane`
# =================================================================================================
def test_the_type_is_named_output_lane_not_lane():
    """⛔ `reason/uncited_lanes.py` already means something else by "lane", and that conflation already
    cost five readings. A bare `Lane` beside it would be read as the same concept."""
    assert OutputLane.__name__ == "OutputLane"
    from genios_engine.contracts import reasoning

    assert not hasattr(reasoning, "Lane")
    assert not hasattr(reasoning, "LANES")


def test_the_decision_field_is_named_output_lane():
    assert "output_lane" in ReasoningDecision.__dataclass_fields__
    assert "lane" not in ReasoningDecision.__dataclass_fields__


def test_the_pack_lane_concept_is_untouched():
    """`uncited_lanes` keeps its own meaning; nothing here renamed or absorbed it."""
    from genios_engine.reason import uncited_lanes

    assert uncited_lanes.__doc__ and "pack" in uncited_lanes.__doc__.lower()


# =================================================================================================
# 4 · each member says what the READER does
# =================================================================================================
def _lane_class_source() -> str:
    """The `OutputLane` class body ONLY.

    ⛔ Scoped deliberately: `DecisionOutcome.DECISION = "decision"` appears EARLIER in the module, so a
    whole-module `.index()` finds the wrong class and this test passed against the wrong text on its
    first run. The collision these tests are about bit the test for them."""
    import inspect

    return inspect.getsource(OutputLane)


@pytest.mark.parametrize("lane", list(OutputLane))
def test_every_lane_is_documented(lane):
    """The only thing distinguishing these five from the six outcomes is what the reader is expected to
    DO, so an undocumented member is a member nobody can route to correctly."""
    source = _lane_class_source()
    at = source.index(f'{lane.name} = "{lane.value}"')
    assert "#:" in source[max(0, at - 700):at], f"{lane.name} has no field comment"


def test_monitor_and_suppress_are_documented_as_different_promises():
    """⛔ "Still live" and "over" are different things to tell a reader, and a card that confused them
    would either nag forever or go quiet with no explanation."""
    source = _lane_class_source()
    at = source.index('MONITOR = "monitor"')
    assert "Distinct from SUPPRESS" in source[max(0, at - 500):at]


def test_suppress_is_documented_as_recorded_silence_not_absence():
    """Suppression that left no trace is the defect this programme has found in six other places."""
    source = _lane_class_source()
    at = source.index('SUPPRESS = "suppress"')
    assert "declared silence" in source[max(0, at - 600):at]


def test_the_lane_docstring_names_the_axis_it_is_not():
    """An undocumented distinction gets merged by the next person who notices two enums overlapping."""
    assert "DecisionOutcome" in (OutputLane.__doc__ or "")
    assert "uncited_lanes" in (OutputLane.__doc__ or "")
