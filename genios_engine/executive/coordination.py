"""Layer 5 · Unit 2.5 — deterministic execution coordination.

Planning freezes the dependency graph; coordination answers which actions can move *now*.
It never invents a step, changes priority, or guesses around an unmet dependency. The output is
a projection over the immutable ``ExecutionObject`` plus recorded completions, so it can be
recomputed for APIs, validation and audit without adding a second mutable plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from genios_engine.contracts.execution import AudienceClass, ExecutionObject


COORDINATION_VERSION = "coordination.v1"


@dataclass(frozen=True, slots=True)
class CoordinatedAction:
    action_id: str
    ordinal: int
    stage: int
    audience: AudienceClass
    assignee: str | None
    status: str
    unmet_dependencies: tuple[str, ...]

    def to_semantic_dict(self) -> dict:
        return {"action_id": self.action_id, "ordinal": self.ordinal,
                "stage": self.stage, "audience": self.audience.value,
                "assignee": self.assignee, "status": self.status,
                "unmet_dependencies": self.unmet_dependencies}


@dataclass(frozen=True, slots=True)
class CoordinationSnapshot:
    execution_id: str
    actions: tuple[CoordinatedAction, ...]
    completed_action_ids: tuple[str, ...]
    ready_action_ids: tuple[str, ...]
    waiting_action_ids: tuple[str, ...]
    invalid_completion_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return len(self.completed_action_ids) == len(self.actions)

    @property
    def current_stage(self) -> int:
        ready = [item.stage for item in self.actions if item.status == "ready"]
        waiting = [item.stage for item in self.actions if item.status == "waiting"]
        terminal_stage = max((item.stage for item in self.actions), default=-1) + 1
        return min(ready or waiting or [terminal_stage])

    def action(self, action_id: str) -> CoordinatedAction | None:
        return next((item for item in self.actions if item.action_id == action_id), None)

    def to_semantic_dict(self) -> dict:
        return {"schema_version": COORDINATION_VERSION,
                "execution_id": self.execution_id,
                "current_stage": self.current_stage, "complete": self.complete,
                "completed_action_ids": self.completed_action_ids,
                "ready_action_ids": self.ready_action_ids,
                "waiting_action_ids": self.waiting_action_ids,
                "invalid_completion_ids": self.invalid_completion_ids,
                "actions": tuple(item.to_semantic_dict() for item in self.actions)}


def coordinate(execution: ExecutionObject,
               completed_action_ids: Iterable[str] = ()) -> CoordinationSnapshot:
    """Project dependency state and refuse to pretend an impossible completion is valid."""
    known = {action.action_id for action in execution.actions}
    completed = {str(action_id) for action_id in completed_action_ids if str(action_id) in known}
    invalid: list[str] = []
    actions: list[CoordinatedAction] = []

    for action in execution.actions:
        unmet = tuple(dep for dep in action.depends_on if dep not in completed)
        if action.action_id in completed:
            status = "completed"
            if unmet:
                invalid.append(action.action_id)
        else:
            status = "ready" if not unmet else "waiting"
        # Concrete routing is mutable and therefore excluded from the execution identity. The
        # commitment owner is the default executor for owner-scoped steps; widened audiences
        # are resolved at the moment their stage/rung is activated.
        assignee = (execution.communication.assignee
                    if action.audience is AudienceClass.OWNER else None)
        actions.append(CoordinatedAction(
            action_id=action.action_id, ordinal=action.ordinal, stage=action.stage,
            audience=action.audience, assignee=assignee, status=status,
            unmet_dependencies=unmet))

    return CoordinationSnapshot(
        execution_id=execution.execution_id, actions=tuple(actions),
        completed_action_ids=tuple(item.action_id for item in actions
                                   if item.status == "completed"),
        ready_action_ids=tuple(item.action_id for item in actions if item.status == "ready"),
        waiting_action_ids=tuple(item.action_id for item in actions if item.status == "waiting"),
        invalid_completion_ids=tuple(invalid))


__all__ = ["COORDINATION_VERSION", "CoordinatedAction", "CoordinationSnapshot", "coordinate"]
