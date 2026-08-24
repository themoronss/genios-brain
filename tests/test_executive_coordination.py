"""Layer 5 · Unit 2.5 — Execution Coordination.

Pure tests: a coordination decision is a value over (plan actions, completed set). No DB, no clock.
Proves dependency-gated completion — the guardrail that stops a step being ticked before the step
it depends on, which would record a history that never happened.
"""
from __future__ import annotations

from genios_engine.contracts.execution import ActionKind, PlannedAction
from genios_engine.executive.coordination import (
    can_complete,
    coordination_snapshot,
    dependencies_met,
)


def _action(action_id: str, ordinal: int, *, depends_on: tuple[str, ...] = ()) -> PlannedAction:
    # PREPARE is a read-only kind, so read_only defaults True without tripping the external-effect guard.
    # ordinal is 1-based (require_ordinal rejects 0).
    return PlannedAction(ordinal=ordinal, stage=ordinal, action_id=action_id,
                         label=f"step {action_id}", kind=ActionKind.PREPARE, depends_on=depends_on)


# draft -> review -> send : a classic gated chain
DRAFT = _action("draft", 1)
REVIEW = _action("review", 2, depends_on=("draft",))
SEND = _action("send", 3, depends_on=("review",))
CHAIN = (SEND, DRAFT, REVIEW)  # deliberately unordered — the unit must sort by ordinal


def test_nothing_done_only_the_root_is_ready():
    snap = coordination_snapshot(CHAIN, completed=())
    assert snap.completed == ()
    assert snap.ready == ("draft",)          # only the dependency-free step
    assert snap.waiting == ("review", "send")
    assert not snap.all_done


def test_snapshot_advances_as_dependencies_clear():
    snap = coordination_snapshot(CHAIN, completed={"draft"})
    assert snap.completed == ("draft",)
    assert snap.ready == ("review",)         # unlocked now that draft is done
    assert snap.waiting == ("send",)


def test_all_done_when_every_step_completed():
    snap = coordination_snapshot(CHAIN, completed={"draft", "review", "send"})
    assert snap.completed == ("draft", "review", "send")
    assert snap.ready == () and snap.waiting == ()
    assert snap.all_done


def test_can_complete_refuses_out_of_order():
    # send depends on review, which is not done -> completing it now is out of order
    assert can_complete("send", CHAIN, completed={"draft"}) is False
    assert can_complete("review", CHAIN, completed={"draft"}) is True   # its one dep is met


def test_can_complete_refuses_an_already_ticked_step():
    assert can_complete("draft", CHAIN, completed={"draft"}) is False


def test_unknown_action_fails_closed():
    assert can_complete("ghost", CHAIN, completed=()) is False
    assert dependencies_met("ghost", CHAIN, completed=()) is False


def test_dependencies_met_is_independent_of_already_done():
    # dependencies_met asks only about predecessors, not whether the action itself is ticked
    assert dependencies_met("review", CHAIN, completed={"draft"}) is True
    assert dependencies_met("send", CHAIN, completed={"draft"}) is False


def test_a_diamond_join_waits_for_both_arms():
    # a -> b, a -> c, then d depends on BOTH b and c
    a = _action("a", 1)
    b = _action("b", 2, depends_on=("a",))
    c = _action("c", 3, depends_on=("a",))
    d = _action("d", 4, depends_on=("b", "c"))
    plan = (a, b, c, d)
    assert coordination_snapshot(plan, completed={"a", "b"}).waiting == ("d",)     # c still open
    assert can_complete("d", plan, completed={"a", "b"}) is False
    assert can_complete("d", plan, completed={"a", "b", "c"}) is True              # both arms in
