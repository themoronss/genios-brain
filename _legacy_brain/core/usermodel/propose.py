"""Propose-confirm for BIG inferred shifts.

Per MD g-i-9 §2:
    propose-confirm for big shifts: a large inferred change ("user seems much more
    formal lately") is *proposed* to the user, not silently applied — same discipline
    as everywhere else. Prevents the profile drifting wrong on noise.

A "big shift" is one where the inferred new value differs from the current
conclusion beyond a (per-field) threshold. Small/incremental updates go through
distill.py; only large diffs come here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.usermodel.schema import FieldMeta
from core.usermodel.store import UserModelProposalRow, UserModelRow

log = get_logger(__name__)


@dataclass(frozen=True)
class BigShiftProposal:
    """A pending proposal — shown to user, awaiting their decision."""

    id: str
    user_id: str
    field: str
    current_value: Any
    proposed_value: Any
    signal_count: int
    status: str
    rationale: str | None
    created_at: datetime


class ProposalError(Exception):
    """Proposal lookup / state transition error."""


def propose_shift(
    session: Session,
    *,
    user_id: str,
    field: str,
    proposed_value: Any,
    signal_count: int,
    rationale: str | None = None,
) -> BigShiftProposal:
    """Persist a proposal for the user to review. Does NOT auto-apply.

    Caller (distill or external signal aggregator) decides when a shift is "big enough"
    to warrant explicit confirm vs the silent-distill path.
    """
    user_row = session.query(UserModelRow).filter_by(user_id=user_id).one_or_none()
    if user_row is None:
        raise ProposalError(f"No profile for user {user_id}")

    current = _read_current(user_row, field)
    row = UserModelProposalRow(
        user_id=user_id,
        field=field,
        current_value_jsonb=_to_jsonable(current),
        proposed_value_jsonb=_to_jsonable(proposed_value),
        signal_count=signal_count,
        status="pending",
        rationale=rationale,
    )
    session.add(row)
    session.flush()

    audit.record(
        org_id=user_row.org_unit,
        actor_type="system",
        actor_id="propose_shift",
        action="config_changed",
        target_type="user_model_proposal",
        target_id=row.id,
        metadata={
            "user_id": user_id,
            "field": field,
            "signal_count": signal_count,
        },
    )
    log.info(
        "user_model_shift_proposed",
        user_id=user_id,
        field=field,
        proposal_id=row.id,
        signal_count=signal_count,
    )
    return _row_to_proposal(row)


def confirm_proposal(session: Session, *, proposal_id: str, actor: str) -> BigShiftProposal:
    """User approves -> apply proposed_value to the profile + mark approved."""
    row = _load_pending(session, proposal_id)
    user_row = session.query(UserModelRow).filter_by(user_id=row.user_id).one_or_none()
    if user_row is None:
        raise ProposalError(f"Proposal {proposal_id} references missing user profile")

    # Apply the proposed value
    column = _field_to_column(row.field)
    setattr(user_row, column, row.proposed_value_jsonb)
    meta = dict(user_row.field_meta_jsonb or {})
    meta[row.field] = FieldMeta(
        source="learned", confidence=1.0, last_updated=datetime.now(UTC)
    ).model_dump(mode="json")
    user_row.field_meta_jsonb = meta
    user_row.updated_at = datetime.now(UTC)

    row.status = "approved"
    row.decided_at = datetime.now(UTC)
    row.decided_by = actor

    audit.record(
        org_id=user_row.org_unit,
        actor_type="user",
        actor_id=actor,
        action="config_changed",
        target_type="user_model_proposal",
        target_id=row.id,
        metadata={"op": "approved", "field": row.field},
    )
    log.info("user_model_proposal_approved", proposal_id=proposal_id, field=row.field)
    return _row_to_proposal(row)


def reject_proposal(session: Session, *, proposal_id: str, actor: str) -> BigShiftProposal:
    """User rejects -> profile unchanged + mark rejected."""
    row = _load_pending(session, proposal_id)
    row.status = "rejected"
    row.decided_at = datetime.now(UTC)
    row.decided_by = actor

    user_row = session.query(UserModelRow).filter_by(user_id=row.user_id).one_or_none()
    if user_row is not None:
        audit.record(
            org_id=user_row.org_unit,
            actor_type="user",
            actor_id=actor,
            action="config_changed",
            target_type="user_model_proposal",
            target_id=row.id,
            metadata={"op": "rejected", "field": row.field},
        )
    log.info("user_model_proposal_rejected", proposal_id=proposal_id, field=row.field)
    return _row_to_proposal(row)


# ─── helpers ────────────────────────────────────────────────────────────────


def _load_pending(session: Session, proposal_id: str) -> UserModelProposalRow:
    row = session.get(UserModelProposalRow, proposal_id)
    if row is None:
        raise ProposalError(f"Proposal {proposal_id} not found")
    if row.status != "pending":
        raise ProposalError(f"Proposal {proposal_id} already {row.status}")
    return row


def _read_current(user_row: UserModelRow, field: str) -> Any:
    column = _field_to_column(field)
    return getattr(user_row, column)


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [(v.value if hasattr(v, "value") else v) for v in value]
    if isinstance(value, dict):
        return {k: (v.value if hasattr(v, "value") else v) for k, v in value.items()}
    return value


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


def _row_to_proposal(row: UserModelProposalRow) -> BigShiftProposal:
    return BigShiftProposal(
        id=row.id,
        user_id=row.user_id,
        field=row.field,
        current_value=row.current_value_jsonb,
        proposed_value=row.proposed_value_jsonb,
        signal_count=row.signal_count,
        status=row.status,
        rationale=row.rationale,
        created_at=row.created_at,
    )


# Re-exported for callers
__all__ = [
    "BigShiftProposal",
    "ProposalError",
    "confirm_proposal",
    "propose_shift",
    "reject_proposal",
]
# Used by select() helper above
_ = select
