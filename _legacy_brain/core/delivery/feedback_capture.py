"""Feedback capture — 👍/👎/edit → structured Correction → g-i-3 learning.

Per MD g-i-7:
    Feedback = MOAT fuel. Every 👍/👎/edit must become a structured Correction
    that g-i-3 can learn from. Silent dismissal wastes the strongest signal.

Flow:
1. capture_feedback() persists FeedbackActionRow (raw signal)
2. If action ∈ {thumbs_down, edit}, ALSO build a CorrectionRow + link back
3. distill.py (g-i-9) consumes corrections to refine per-user persona
4. learning.py (g-i-3) consumes corrections for Bayesian edge updates
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from core.delivery.store import FeedbackActionRow
from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.worldmodel.store import CorrectionRow

log = get_logger(__name__)


class FeedbackAction(StrEnum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    EDIT = "edit"
    SNOOZE = "snooze"
    NEVER_SHOW = "never_show"


@dataclass(frozen=True)
class FeedbackToCorrection:
    """Outcome of capture_feedback()."""

    feedback_id: str
    correction_id: (
        str | None
    )  # None if action is thumbs_up/snooze/never_show (no correction needed)
    routed_to_g_i_3: bool
    reason: str


def capture_feedback(
    session: Session,
    *,
    org_id: str,
    user_id: str,
    decision_id: str | None,
    insight_id: str | None,
    action: FeedbackAction,
    edit_diff: dict[str, Any] | None = None,
    engine_decision_loader: Callable[[str], dict[str, Any]] | None = None,
) -> FeedbackToCorrection:
    """Persist feedback. For thumbs_down / edit, also create a CorrectionRow.

    Args:
        decision_id: REQUIRED for actions that link back to a Decision (down, edit).
                     None for insight-only feedback (never_show on a signature).
        engine_decision_loader: optional callable to fetch original Decision payload
                                 (so the correction.engine_decision field is populated).
                                 Caller wires this from core.decision_store.
    """
    if action in (FeedbackAction.THUMBS_DOWN, FeedbackAction.EDIT) and decision_id is None:
        raise ValueError(f"action={action} requires decision_id (got None)")

    fb = FeedbackActionRow(
        org_id=org_id,
        user_id=user_id,
        decision_id=decision_id,
        insight_id=insight_id,
        action=action.value,
        edit_diff_jsonb=edit_diff,
    )
    session.add(fb)
    session.flush()

    audit.record(
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        action="override_captured"
        if action in (FeedbackAction.THUMBS_DOWN, FeedbackAction.EDIT)
        else "data_accessed",
        target_type="decision" if decision_id else "insight",
        target_id=decision_id or insight_id or "unknown",
        metadata={"feedback_action": action.value, "feedback_id": fb.id},
    )

    # Only thumbs_down + edit produce a Correction
    if action not in (FeedbackAction.THUMBS_DOWN, FeedbackAction.EDIT) or decision_id is None:
        log.info(
            "feedback_recorded_no_correction",
            org_id=org_id,
            user_id=user_id,
            action=action.value,
            feedback_id=fb.id,
        )
        return FeedbackToCorrection(
            feedback_id=fb.id,
            correction_id=None,
            routed_to_g_i_3=False,
            reason=f"action={action.value} does not produce a correction",
        )

    # Build CorrectionRow
    engine_decision = (
        engine_decision_loader(decision_id) if engine_decision_loader else {"_unresolved": True}
    )
    human_decision = edit_diff or {"thumbs_down": True}
    diff = _compute_diff(engine_decision, human_decision)

    # g-i-3 edge outcomes: learning.derive_outcomes() reads FLAT lists off
    # correction.diff ("edges_confirmed" / "edges_contradicted"), but
    # _compute_diff wraps every field as {"engine", "human"} — so edge lists
    # passed in edit_diff would never reach the Bayesian update. Carry them
    # through verbatim (flat) and record them in edge_ids. Without this the
    # learning loop cannot move a single graph-edge weight (Gate 2 blocker).
    edges_confirmed = _flat_str_list((edit_diff or {}).get("edges_confirmed"))
    edges_contradicted = _flat_str_list((edit_diff or {}).get("edges_contradicted"))
    if edges_confirmed:
        diff["edges_confirmed"] = edges_confirmed
    if edges_contradicted:
        diff["edges_contradicted"] = edges_contradicted

    correction = CorrectionRow(
        org_id=org_id,
        decision_id=decision_id,
        input_context={},  # caller may enrich via separate call
        engine_decision=engine_decision,
        human_decision=human_decision,
        diff=diff,
        rule_ids=[],
        edge_ids=edges_confirmed + edges_contradicted,
        timestamp=datetime.now(UTC),
        actor=user_id,
    )
    session.add(correction)
    session.flush()

    # Link the feedback row to the correction
    fb.correction_id = correction.id

    log.info(
        "feedback_routed_to_correction",
        feedback_id=fb.id,
        correction_id=correction.id,
        decision_id=decision_id,
    )
    return FeedbackToCorrection(
        feedback_id=fb.id,
        correction_id=correction.id,
        routed_to_g_i_3=True,
        reason=f"action={action.value} produced correction; g-i-3 learning.apply_correction picks up",
    )


def _compute_diff(engine: dict[str, Any], human: dict[str, Any]) -> dict[str, Any]:
    """Field-by-field diff. Same shape as core.reflection.human_flag._compute_diff."""
    diff: dict[str, Any] = {}
    for k in set(engine) | set(human):
        e = engine.get(k)
        h = human.get(k)
        if e != h:
            diff[k] = {"engine": e, "human": h}
    return diff


def _flat_str_list(v: Any) -> list[str]:
    """Coerce a value to a flat list[str]. Mirrors learning._str_list so the
    edge-outcome contract matches on both the write (here) and read sides."""
    if isinstance(v, list):
        return [str(x) for x in v]
    return []
