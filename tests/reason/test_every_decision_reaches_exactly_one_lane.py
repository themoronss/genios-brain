"""S3.F3.2/F3.3 · the router — deterministic, total in both directions, and no model.

    pytest tests/reason/test_every_decision_reaches_exactly_one_lane.py -q

⛔ TOTALITY IN BOTH DIRECTIONS IS THE POINT OF THIS FILE.

  forward  — every (outcome, confidence, conflict, block) maps to exactly ONE lane
  backward — every lane is REACHABLE from some input

A lane nothing can route to is dead vocabulary, and dead vocabulary gets "fixed" later by somebody
widening a condition until it is reachable — at which point the widening, not the design, decides what
a reader sees.
"""

from __future__ import annotations

import inspect
import pathlib

import pytest

from genios_engine.contracts.reasoning import OUTPUT_LANES, DecisionOutcome, OutputLane
from genios_engine.reason import output_lane as mod
from genios_engine.reason.output_lane import (DEFAULT_DECISION_FLOOR_BP, LaneChoice, reachable_lanes,
                                              route)

pytestmark = pytest.mark.unit

_FLOOR = DEFAULT_DECISION_FLOOR_BP
_ALL_INPUTS = [
    dict(outcome=o, confidence_bp=c, conflict_open=x, reader_actionable_block=b)
    for o in DecisionOutcome
    for c in (0, _FLOOR - 1, _FLOOR, 10_000)
    for x in (False, True)
    for b in (False, True)
]


# =================================================================================================
# 1 · ⛔ totality, forward
# =================================================================================================
@pytest.mark.parametrize("kwargs", _ALL_INPUTS)
def test_every_input_reaches_exactly_one_lane(kwargs):
    choice = route(**kwargs)
    assert isinstance(choice, LaneChoice)
    assert choice.lane in OUTPUT_LANES


def test_no_input_falls_through_without_a_reason():
    """⛔ A card in the wrong lane with no recorded reason is undiagnosable, and this is the single most
    consequential new branch in the layer."""
    for kwargs in _ALL_INPUTS:
        assert route(**kwargs).reason.strip()


def test_the_route_is_deterministic():
    """96 inputs, twice, identical. A route that could vary is not a route."""
    assert [route(**k) for k in _ALL_INPUTS] == [route(**k) for k in _ALL_INPUTS]


# =================================================================================================
# 2 · ⛔ totality, backward
# =================================================================================================
def test_every_lane_is_reachable():
    """⛔ THE HALF THAT IS USUALLY MISSING. A lane nothing routes to is dead vocabulary."""
    assert reachable_lanes() == set(OUTPUT_LANES)


@pytest.mark.parametrize("lane", list(OutputLane))
def test_each_lane_individually_has_at_least_one_input_that_produces_it(lane):
    assert any(route(**k).lane is lane for k in _ALL_INPUTS), f"nothing routes to {lane.value}"


# =================================================================================================
# 3 · ⛔ conflict beats everything, including confidence
# =================================================================================================
def test_an_open_conflict_outranks_a_maximum_confidence_decision():
    """⛔ THE PRECEDENCE THAT MATTERS MOST. A confident decision is the MOST dangerous thing to publish
    over an open disagreement, not the least — publishing either side while it stands erases the
    disagreement by omission, which is what `CONFLICT_OPEN` enforces one layer down."""
    choice = route(outcome=DecisionOutcome.DECISION, confidence_bp=10_000, conflict_open=True)
    assert choice.lane is OutputLane.CONFLICT
    assert "ruling settles this" in choice.reason


@pytest.mark.parametrize("outcome", list(DecisionOutcome))
def test_an_open_conflict_outranks_every_outcome(outcome):
    assert route(outcome=outcome, confidence_bp=10_000,
                 conflict_open=True).lane is OutputLane.CONFLICT


def test_conflict_is_the_only_lane_an_open_conflict_can_produce():
    lanes = {route(**{**k, "conflict_open": True}).lane for k in _ALL_INPUTS}
    assert lanes == {OutputLane.CONFLICT}


# =================================================================================================
# 4 · the confidence floor splits `decision`
# =================================================================================================
def test_a_confident_decision_is_a_decision():
    assert route(outcome=DecisionOutcome.DECISION,
                 confidence_bp=_FLOOR).lane is OutputLane.DECISION


def test_a_decision_under_the_floor_becomes_monitor_not_suppress():
    """⛔ It has a move and not the standing to assert it. Suppressing would say "over" when the thing
    is still live; asserting anyway is how a card teaches a founder to distrust the product."""
    choice = route(outcome=DecisionOutcome.DECISION, confidence_bp=_FLOOR - 1)
    assert choice.lane is OutputLane.MONITOR
    assert "under the" in choice.reason


def test_the_floor_is_inclusive_and_the_reason_names_both_numbers():
    below = route(outcome=DecisionOutcome.DECISION, confidence_bp=_FLOOR - 1)
    at = route(outcome=DecisionOutcome.DECISION, confidence_bp=_FLOOR)
    assert below.lane is OutputLane.MONITOR and at.lane is OutputLane.DECISION
    assert str(_FLOOR) in below.reason and str(_FLOOR - 1) in below.reason


def test_confidence_splits_only_the_decision_outcome():
    """Every other outcome routes on what happened, not on how sure we were about it."""
    for outcome in DecisionOutcome:
        if outcome is DecisionOutcome.DECISION:
            continue
        lanes = {route(outcome=outcome, confidence_bp=c).lane for c in (0, _FLOOR, 10_000)}
        assert len(lanes) == 1, f"{outcome.value} routes differently on confidence alone"


def test_the_floor_is_integer_basis_points():
    assert isinstance(_FLOOR, int) and 0 < _FLOOR < 10_000


# =================================================================================================
# 5 · what each outcome means for the reader
# =================================================================================================
@pytest.mark.parametrize(("outcome", "lane"), [
    (DecisionOutcome.DECISION, OutputLane.DECISION),
    (DecisionOutcome.INSUFFICIENT_CONTEXT, OutputLane.INVESTIGATION),
    (DecisionOutcome.DEFER, OutputLane.MONITOR),
    (DecisionOutcome.NO_ACTION, OutputLane.SUPPRESS),
    (DecisionOutcome.FAILED, OutputLane.SUPPRESS),
    (DecisionOutcome.BLOCKED, OutputLane.SUPPRESS),
])
def test_the_default_route_for_each_outcome(outcome, lane):
    assert route(outcome=outcome, confidence_bp=10_000).lane is lane


def test_defer_and_no_action_route_differently():
    """⛔ "Deliberately waiting" and "deliberately nothing" are different promises, and the difference
    between them is the whole reason both MONITOR and SUPPRESS exist."""
    assert route(outcome=DecisionOutcome.DEFER, confidence_bp=10_000).lane is OutputLane.MONITOR
    assert route(outcome=DecisionOutcome.NO_ACTION,
                 confidence_bp=10_000).lane is OutputLane.SUPPRESS


def test_a_failure_is_ours_and_not_shown_but_it_is_recorded():
    """A crash is not a business question. Suppressing is right; suppressing WITHOUT A TRACE is the
    defect — and the lane itself is the trace."""
    choice = route(outcome=DecisionOutcome.FAILED, confidence_bp=10_000)
    assert choice.lane is OutputLane.SUPPRESS
    assert "ours to fix" in choice.reason


def test_a_block_the_reader_can_clear_becomes_an_investigation():
    """The one case where `blocked` is the reader's rather than ours."""
    assert route(outcome=DecisionOutcome.BLOCKED, confidence_bp=10_000,
                 reader_actionable_block=True).lane is OutputLane.INVESTIGATION
    assert route(outcome=DecisionOutcome.BLOCKED, confidence_bp=10_000,
                 reader_actionable_block=False).lane is OutputLane.SUPPRESS


def test_the_actionable_block_flag_changes_nothing_else():
    """A flag that leaked into other outcomes would make the route depend on an input those outcomes
    never considered."""
    for outcome in DecisionOutcome:
        if outcome is DecisionOutcome.BLOCKED:
            continue
        a = route(outcome=outcome, confidence_bp=10_000, reader_actionable_block=False)
        b = route(outcome=outcome, confidence_bp=10_000, reader_actionable_block=True)
        assert a == b


# =================================================================================================
# 6 · ⛔ a lane is a route, so no model produces it
# =================================================================================================
def test_the_router_imports_no_model_no_clock_and_no_database():
    """⛔ `00-ARCHITECTURE.md` §4: *"If the output is a number, a route or a permission, no model
    produces it."* A lane IS a route.

    Checked on the IMPORTS via `ast`, not by grepping the text. The first version of this test grepped
    for "model" and matched the module's own docstring explaining that no model runs here — a test that
    failed because the code documented the very property it was asserting."""
    import ast

    tree = ast.parse(pathlib.Path(inspect.getfile(mod)).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for forbidden in ("datetime", "random", "sqlalchemy", "anthropic", "time"):
        assert not any(name == forbidden or name.startswith(forbidden + ".")
                       for name in imported), f"{forbidden} does not belong in a pure router"
    for forbidden in ("llm", "client", "store", "db"):
        assert not any(forbidden in name.split(".")[-1] for name in imported), forbidden


def test_the_router_calls_nothing_that_could_vary_between_runs():
    """The complement of the import check: no call to a clock or a generator, however reached."""
    import ast

    tree = ast.parse(pathlib.Path(inspect.getfile(mod)).read_text())
    called = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    for forbidden in ("now", "utcnow", "random", "uuid4", "time"):
        assert not any(forbidden in name for name in called), f"{forbidden} in {called}"


def test_the_inputs_are_supplied_not_inferred_from_prose():
    """`conflict_open` and `reader_actionable_block` are facts about the SITUATION. Inferring them from
    `uncertainty` strings would make the route depend on wording that changes whenever somebody
    improves a sentence."""
    params = inspect.signature(route).parameters
    assert "conflict_open" in params and "reader_actionable_block" in params
    assert "uncertainty" not in params


def test_a_lane_choice_with_no_reason_cannot_be_constructed():
    with pytest.raises(ValueError, match="undiagnosable"):
        LaneChoice(OutputLane.DECISION, "   ")


def test_a_lane_choice_is_frozen():
    choice = route(outcome=DecisionOutcome.DECISION, confidence_bp=10_000)
    with pytest.raises(Exception):
        choice.lane = OutputLane.SUPPRESS


# =================================================================================================
# 7 · it reaches the decision object
# =================================================================================================
def test_the_lane_is_kept_OUT_of_the_decision_hash():
    """⛔ THE CORRECTION THAT COST FOUR REPLAY TESTS. I first folded the lane into
    `to_semantic_dict`, reasoning that "a decision routed differently is a different decision". That
    is wrong, and the reason is that `route()` is a PURE FUNCTION of fields already in the hash —
    `outcome`, `confidence_bp`, and the conflict markers inside `uncertainty`.

    So the lane adds ZERO information to the content address while changing the identity of every
    decision that carries one. Four tests caught it:

        test_the_run_replays_byte_for_byte
        test_the_compiled_lane_could_not_be_replayed_before_this_wave
        test_a_selected_bundle_still_verifies_every_persisted_hash
        test_replay_bundle_verifies_every_persisted_semantic_hash_before_execution

    ⛔ A DERIVED VALUE HAS NO BUSINESS IN A CONTENT HASH. `reasoning_bundle` in the same class makes the
    identical argument in its own words: *"the narrative cannot be part of the thing it narrates."*"""
    from genios_engine.contracts import reasoning

    source = inspect.getsource(reasoning.ReasoningDecision.to_semantic_dict)
    assert 'body["output_lane"]' not in source
    assert "DELIBERATELY NOT IN THE HASH" in source


def test_the_lane_is_reconstructable_from_what_the_hash_does_carry():
    """The property that makes the exclusion safe: every input `route()` reads is in the dict already,
    so a lane can be recomputed from a stored decision without storing it."""
    from genios_engine.contracts import reasoning

    source = inspect.getsource(reasoning.ReasoningDecision.to_semantic_dict)
    for carried in ('"outcome"', '"confidence_bp"', '"uncertainty"'):
        assert carried in source


def test_a_routed_and_an_unrouted_decision_with_the_same_content_hash_the_same():
    """⛔ THE PROPERTY, ASSERTED ON REAL OBJECTS rather than on the source. Adding a lane must not move
    `decision_hash`, or every bundle written before the router stops verifying."""
    from datetime import datetime, timedelta, timezone

    from genios_engine.contracts.reasoning import OutputLane, ReasoningDecision

    common = dict(
        outcome=DecisionOutcome.NO_ACTION, capability_id="c", capability_version="1",
        context_snapshot_id="cs", candidates=(), selected_candidate_id=None,
        confidence_bp=5000, uncertainty=(), do_nothing_consequence="nothing happens",
        expires_at=datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(hours=1))
    unrouted = ReasoningDecision(**common)
    routed = ReasoningDecision(**common, output_lane=OutputLane.SUPPRESS,
                               lane_reason="deliberately nothing to do")
    assert routed.semantic_hash == unrouted.semantic_hash


def test_the_lane_choice_serialises_for_the_projections():
    choice = route(outcome=DecisionOutcome.DEFER, confidence_bp=10_000)
    assert choice.to_semantic_dict() == {"lane": "monitor", "lane_reason": choice.reason}
