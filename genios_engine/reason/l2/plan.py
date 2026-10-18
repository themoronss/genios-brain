"""GeniOS-008 L2 R5 · the Plan Compiler — how much to think, never what to conclude.

Spec §8: depth is "proposed operational policy", versioned and auditable. It is chosen here from MEASURED
inputs only — the tools' numbers, the bundle's unresolved list, the snapshot's cap, the file's situations,
the importance L1 scored — and from the model's own earlier request for more depth, with its reason.
Every input that moved the depth is written into `why`, and `why` goes into the receipt. Nothing here
reads meaning: that is the model's.

  shallow   one subject, nothing pressing, nothing unresolved                Groups 1-2   1 call
  standard  a file's work, a due date near, something unresolved            Groups 1-5   1-2 calls
  deep      past due on important work, contradiction, the model asked      Groups 1-6   up to 3 calls

(`none` — the change gate — is decided before a plan is compiled: nothing material moved, no run.)

The groups are Plane R's, as the expert prompt compiles them (`reason/expert/prompt`): 1 what is true,
2 the frame, 3 expected vs actual + patterns, 4 unknowns + scenarios + appraisal, 5 options and their
trade-offs, 6 the decision need and who holds it. Every group's FIELDS are always asked — a result is
one shape — but a skipped group is asked briefly and recorded as skipped with why.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts.reasoning_result import DEPTH_DEEP, DEPTH_SHALLOW, DEPTH_STANDARD

PLAN_VERSION = "l2-plan.v1"

#: Plane R's groups, in order, named without digits: the prompt carries their names, and a prompt writes no
#: number of its own (`reason/expert/prompt`).
GROUPS: tuple[str, ...] = ("what is true", "the frame", "expected against actual and patterns",
                           "unknowns, scenarios and appraisal", "the options", "the decision and who holds it")
_GROUPS_AT = {DEPTH_SHALLOW: 2, DEPTH_STANDARD: 5, DEPTH_DEEP: 6}
#: Model calls a depth may spend: the judgment, the evidence re-entry, the repair of a failed check.
CALLS_AT = {DEPTH_SHALLOW: 1, DEPTH_STANDARD: 2, DEPTH_DEEP: 3}

#: L1's importance at or above which the work counts as important — L1's own scale, read, not re-scored.
IMPORTANT_BP = 7_000
#: A due date this close counts as near.
NEAR_HOURS = 48


@dataclass(frozen=True, slots=True)
class L2Plan:
    depth: str
    why: tuple[str, ...]
    groups_run: tuple[str, ...]
    groups_skipped: Mapping[str, str]
    max_calls: int
    version: str = PLAN_VERSION


def compile_plan(*, tools: Mapping[str, Any], file_id: str | None, unresolved: Sequence[str],
                 truncated: bool, situations: int, importance_bp: int | None,
                 conflicts: int = 0, asked_deeper: str | None = None) -> L2Plan:
    """The plan for one run. Pure: the same measured inputs, the same plan."""
    why: list[str] = []
    due = tools.get("nearest_due") or {}
    hours = due.get("hours") if isinstance(due, Mapping) else None
    important = importance_bp is not None and importance_bp >= IMPORTANT_BP
    deep = False
    if conflicts:
        why.append(f"{conflicts} open conflict(s) in what arrived")
        deep = True
    if hours is not None and hours < 0 and important:
        why.append(f"past due by {-hours} hours on work L1 scored {importance_bp} bp")
        deep = True
    if asked_deeper:
        why.append(f"the last run asked for more depth: {asked_deeper}")
        deep = True
    standard = False
    if file_id:
        why.append("a file's work in motion")
        standard = True
    if hours is not None and 0 <= hours <= NEAR_HOURS:
        why.append(f"a due date {hours} hours away")
        standard = True
    if hours is not None and hours < 0 and not important:
        why.append(f"past due by {-hours} hours")
        standard = True
    if unresolved:
        why.append(f"{len(unresolved)} thing(s) L1 could not settle")
        standard = True
    if truncated:
        why.append("the context snapshot was capped")
        standard = True
    if situations > 1:
        why.append(f"{situations} situations on this work")
        standard = True
    depth = DEPTH_DEEP if deep else DEPTH_STANDARD if standard else DEPTH_SHALLOW
    if not why:
        why.append("one subject, nothing pressing, nothing unresolved")
    n = _GROUPS_AT[depth]
    skipped = {g: f"not needed at {depth} depth: asked briefly" for g in GROUPS[n:]}
    return L2Plan(depth=depth, why=tuple(why), groups_run=GROUPS[:n], groups_skipped=skipped,
                  max_calls=CALLS_AT[depth])


__all__ = ["CALLS_AT", "GROUPS", "IMPORTANT_BP", "L2Plan", "NEAR_HOURS", "PLAN_VERSION", "compile_plan"]
