"""Atlas Layer 5 Unit 2.5: dependency coordination without changing the frozen plan."""
from __future__ import annotations

from genios_engine.executive.coordination import coordinate

from tests.test_executive_execution import build, make_decision


def coordinated_execution():
    decision = make_decision(steps=(
        "Gather the commercial terms.",
        "Review the latest legal constraints.",
        "Draft the final proposal from both inputs.",
    ))
    return build(decision=decision).require()


def test_parallel_work_is_released_as_one_wave_then_joined():
    execution = coordinated_execution()
    first = coordinate(execution)
    assert first.current_stage == 0
    assert first.ready_action_ids == ("a1", "a2")
    assert first.waiting_action_ids == ("a3",)
    assert first.action("a3").unmet_dependencies == ("a1", "a2")

    half = coordinate(execution, ("a1",))
    assert half.ready_action_ids == ("a2",)
    assert half.action("a3").unmet_dependencies == ("a2",)

    joined = coordinate(execution, ("a1", "a2"))
    assert joined.current_stage == 1
    assert joined.ready_action_ids == ("a3",)


def test_impossible_completion_is_visible_instead_of_normalized_away():
    execution = coordinated_execution()
    snapshot = coordinate(execution, ("a3",))
    assert snapshot.invalid_completion_ids == ("a3",)
    assert snapshot.action("a3").unmet_dependencies == ("a1", "a2")


def test_owner_actions_resolve_to_the_commitment_owner():
    execution = coordinated_execution()
    snapshot = coordinate(execution)
    assert all(action.assignee == "seat_rep" for action in snapshot.actions)
