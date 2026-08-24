"""Layer 5 · Unit 2.5 — Execution Coordination.

Recomputes, deterministically, which of a commitment's actions are *done*, *ready* (every
dependency satisfied, so legal to complete now) or *waiting* (a predecessor has not happened
yet). It answers the one question the completion path must ask before it ticks a step:

    are this action's dependencies all satisfied?

Completing a step whose predecessor never happened records a history that never occurred. The
plan said *"draft the note, then send it"*; ticking *send* while *draft* is still open makes the
audit trail claim an approval that was skipped — and Layer 6 then learns from an outcome that did
not take place. The Execution Object already *describes* dependencies (``PlannedAction.depends_on``);
this unit is what makes them *binding* at runtime.

Pure core: it reads the plan the planner froze and the set of steps the world has finished, and
computes. No model, no clock, no SQL. The snapshot is a value, so the same actions + the same
completed set always yield the same classification — a coordination decision is replayable.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from genios_engine.contracts.execution import PlannedAction


@dataclass(frozen=True, slots=True)
class CoordinationSnapshot:
    """A deterministic view of where a commitment's actions stand, ordinal-ordered.

    ``ready`` is the only set the completion path may tick. ``waiting`` is the guardrail: an
    action lands here precisely when completing it would be out of order.
    """

    completed: tuple[str, ...]
    ready: tuple[str, ...]
    waiting: tuple[str, ...]

    def is_ready(self, action_id: str) -> bool:
        return action_id in self.ready

    def is_waiting(self, action_id: str) -> bool:
        return action_id in self.waiting

    @property
    def all_done(self) -> bool:
        return not self.ready and not self.waiting


def _by_id(actions: Iterable[PlannedAction]) -> dict[str, PlannedAction]:
    return {a.action_id: a for a in actions}


def dependencies_met(action_id: str, actions: Iterable[PlannedAction],
                     completed: Collection[str]) -> bool:
    """Every declared dependency of ``action_id`` is in ``completed``.

    An unknown action id fails closed — you cannot complete a step that is not in the plan.
    """
    action = _by_id(actions).get(action_id)
    if action is None:
        return False
    done = set(completed)
    return all(dep in done for dep in action.depends_on)


def can_complete(action_id: str, actions: Iterable[PlannedAction],
                 completed: Collection[str]) -> bool:
    """The completion gate: the action exists, is not already ticked, and its deps are all done."""
    if action_id in set(completed):
        return False
    return dependencies_met(action_id, actions, completed)


def coordination_snapshot(actions: Iterable[PlannedAction],
                          completed: Collection[str]) -> CoordinationSnapshot:
    """Classify every action as completed / ready / waiting, in ordinal order."""
    done = set(completed)
    completed_ids: list[str] = []
    ready: list[str] = []
    waiting: list[str] = []
    for action in sorted(actions, key=lambda a: a.ordinal):
        if action.action_id in done:
            completed_ids.append(action.action_id)
        elif all(dep in done for dep in action.depends_on):
            ready.append(action.action_id)
        else:
            waiting.append(action.action_id)
    return CoordinationSnapshot(tuple(completed_ids), tuple(ready), tuple(waiting))


__all__ = ["CoordinationSnapshot", "can_complete", "coordination_snapshot", "dependencies_met"]
