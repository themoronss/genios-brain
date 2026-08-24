"""Correction-driven persona refinement (the "Learn" half of seed + learn).

Per MD g-i-9 §2:
    on user edit/override:
        diff = (what GeniOS produced) vs (what user changed it to)
        infer the preference delta (e.g. shortened + removed formality -> tone lighter/shorter)
        update the relevant UserModel field's conclusion
        DISCARD the raw diff after distillation (keep bounded rolling window for re-distill)
        volume-gate: a single edit nudges; a consistent pattern changes the field (>= N edits)

This module:
1. record_edit()    persists one raw edit into the bounded window
2. distill_field()  scans the window for that field, applies volume gate, returns updated value

This is the "small nudge" path. For BIG inferred shifts (large diffs that warrant
user confirmation), the propose.py module handles propose-confirm.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.config import USER_MODEL_VOLUME_GATE_N, USER_MODEL_WINDOW_K
from core.foundations.telemetry import get_logger
from core.usermodel.schema import FieldMeta
from core.usermodel.store import UserModelEditRow, UserModelRow

log = get_logger(__name__)


@dataclass(frozen=True)
class DistillResult:
    """Outcome of distill_field()."""

    field: str
    user_id: str
    updated: bool
    new_value: Any
    n_edits_considered: int
    n_consistent: int
    discarded_count: int
    reason: str


def record_edit(
    session: Session,
    *,
    user_id: str,
    field: str,
    edit_diff: dict[str, Any],
    source_correction_id: str | None = None,
) -> UserModelEditRow:
    """Persist one raw edit into the bounded rolling window.

    Caller (typically g-i-7 feedback_capture) supplies the diff. The window
    is bounded per-field: when we exceed K, oldest entries are dropped after
    the next distill pass (not eagerly — distill returns the discard count).
    """
    row = UserModelEditRow(
        user_id=user_id,
        field=field,
        edit_diff_jsonb=edit_diff,
        source_correction_id=source_correction_id,
        applied=False,
    )
    session.add(row)
    session.flush()
    log.info(
        "user_model_edit_recorded",
        user_id=user_id,
        field=field,
        edit_id=row.id,
        source_correction_id=source_correction_id,
    )
    return row


def distill_field(
    session: Session,
    *,
    user_id: str,
    field: str,
    summarizer: EditSummarizer | None = None,
    window_k: int = USER_MODEL_WINDOW_K,
    volume_gate_n: int = USER_MODEL_VOLUME_GATE_N,
) -> DistillResult:
    """Scan the user's edit window for `field`; if N consistent edits, update the conclusion.

    Args:
        summarizer: optional callable that takes the consistent edits and returns the
                    new value for the field. If None, uses a default policy:
                    "last edit's new_value wins" (good enough for v1 fields that
                    are simple lists/strings).
        window_k: how many edits to retain in the rolling window
        volume_gate_n: minimum consistent edits before the conclusion is updated
    """
    row = session.query(UserModelRow).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return DistillResult(
            field=field,
            user_id=user_id,
            updated=False,
            new_value=None,
            n_edits_considered=0,
            n_consistent=0,
            discarded_count=0,
            reason="no profile for user",
        )

    edits = (
        session.execute(
            select(UserModelEditRow)
            .where(UserModelEditRow.user_id == user_id)
            .where(UserModelEditRow.field == field)
            .order_by(UserModelEditRow.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Bounded window — drop anything past K (after distill considers them)
    in_window = edits[:window_k]
    over_limit = edits[window_k:]
    discarded = 0
    for old in over_limit:
        session.delete(old)
        discarded += 1

    # Volume gate
    consistent = _count_consistent(in_window, summarizer)
    if consistent < volume_gate_n:
        return DistillResult(
            field=field,
            user_id=user_id,
            updated=False,
            new_value=None,
            n_edits_considered=len(in_window),
            n_consistent=consistent,
            discarded_count=discarded,
            reason=(
                f"only {consistent} consistent edits (need >= {volume_gate_n}) — "
                f"keeping prior conclusion"
            ),
        )

    # Build the new value using the summarizer (or default "last wins")
    if summarizer is None:
        last_edit = in_window[0]
        new_value = last_edit.edit_diff_jsonb.get("new_value")
    else:
        new_value = summarizer(in_window)

    # Persist new value + bump meta + mark edits as applied
    column = _field_to_column(field)
    setattr(row, column, new_value)
    meta = dict(row.field_meta_jsonb or {})
    confidence = min(1.0, 0.5 + 0.1 * consistent)  # more edits -> higher confidence
    meta[field] = FieldMeta(
        source="learned",
        confidence=round(confidence, 2),
        last_updated=datetime.now(UTC),
    ).model_dump(mode="json")
    row.field_meta_jsonb = meta
    row.updated_at = datetime.now(UTC)
    for e in in_window:
        e.applied = True
    session.flush()

    audit.record(
        org_id=row.org_unit,
        actor_type="system",
        actor_id="distill",
        action="config_changed",
        target_type="user_model_field",
        target_id=f"{user_id}:{field}",
        metadata={
            "op": "distilled",
            "consistent_edits": consistent,
            "new_confidence": confidence,
            "discarded_old_edits": discarded,
        },
    )
    log.info(
        "user_model_field_distilled",
        user_id=user_id,
        field=field,
        consistent=consistent,
        confidence=confidence,
        discarded=discarded,
    )

    return DistillResult(
        field=field,
        user_id=user_id,
        updated=True,
        new_value=new_value,
        n_edits_considered=len(in_window),
        n_consistent=consistent,
        discarded_count=discarded,
        reason=f"distilled from {consistent} consistent edits (confidence {confidence:.2f})",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


# Caller-supplied protocol for non-trivial field aggregation (e.g. voice.tone merging).
class EditSummarizer:
    def __call__(self, edits: Sequence[UserModelEditRow]) -> Any: ...


def _count_consistent(edits: Sequence[UserModelEditRow], summarizer: object | None) -> int:
    """Count edits whose new_value matches the most recent. Default policy.

    A more sophisticated summarizer could cluster by semantic similarity;
    v1 uses raw-equality on the JSON-serializable diff value.
    """
    if not edits:
        return 0
    latest_value = edits[0].edit_diff_jsonb.get("new_value")
    count = sum(1 for e in edits if e.edit_diff_jsonb.get("new_value") == latest_value)
    return count


def _field_to_column(field: str) -> str:
    mapping = {
        "voice": "voice_jsonb",
        "decision_policy": "decision_policy_jsonb",
        "process_habits": "process_habits_jsonb",
        "priorities": "priorities_jsonb",
        "relationships": "relationships_jsonb",
        "red_lines": "red_lines_jsonb",
    }
    if field not in mapping:
        raise ValueError(f"Unknown profile field: {field}")
    return mapping[field]
