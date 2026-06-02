"""User-facing view / update / delete API.

Per MD g-i-9 §4 (non-negotiable):
- User can view, edit, and delete the entire profile — full transparency. No hidden persona.
- Uncertainty surfaced: low-confidence / inferred fields marked so user can correct.
- NEVER used cross-user or cross-company. Profile is the user's, full stop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.usermodel.schema import (
    DecisionPolicy,
    FieldMeta,
    Priorities,
    ProcessHabits,
    RelationshipTag,
    UserModel,
    Voice,
)
from core.usermodel.store import UserModelEditRow, UserModelProposalRow, UserModelRow

log = get_logger(__name__)


class ProfileNotFound(Exception):
    """The requested user has no profile (run seed_profile first)."""


# ─────────────────────────────────────────────────────────────────────────────
# View
# ─────────────────────────────────────────────────────────────────────────────


def view_profile(session: Session, *, user_id: str) -> UserModel:
    """Return the full profile for the user. Reads only — no writes."""
    row = session.query(UserModelRow).filter_by(user_id=user_id).one_or_none()
    if row is None:
        raise ProfileNotFound(f"No profile for user {user_id}")
    return _row_to_model(row)


# ─────────────────────────────────────────────────────────────────────────────
# Update (user-driven edit)
# ─────────────────────────────────────────────────────────────────────────────


def update_field(
    session: Session,
    *,
    user_id: str,
    field: str,
    new_value: Any,
    actor: str | None = None,
) -> UserModel:
    """Replace a profile field. Sets source='seeded' confidence=1.0 (user authored)."""
    row = session.query(UserModelRow).filter_by(user_id=user_id).one_or_none()
    if row is None:
        raise ProfileNotFound(f"No profile for user {user_id}")

    actor = actor or user_id
    now = datetime.now(UTC)

    payload = _serialize_field_value(field, new_value)
    column_name = _field_to_column(field)
    setattr(row, column_name, payload)

    meta = dict(row.field_meta_jsonb or {})
    meta[field] = FieldMeta(source="seeded", confidence=1.0, last_updated=now).model_dump(
        mode="json"
    )
    row.field_meta_jsonb = meta
    row.updated_at = now

    audit.record(
        org_id=row.org_unit,
        actor_type="user",
        actor_id=actor,
        action="config_changed",
        target_type="user_model_field",
        target_id=f"{user_id}:{field}",
        metadata={"op": "update", "by_user": actor == user_id},
    )
    log.info("user_model_field_updated", user_id=user_id, field=field, actor=actor)
    return _row_to_model(row)


# ─────────────────────────────────────────────────────────────────────────────
# Delete (full wipe — per MD non-negotiable)
# ─────────────────────────────────────────────────────────────────────────────


def delete_profile(session: Session, *, user_id: str, actor: str | None = None) -> bool:
    """Full wipe: profile + raw edit window + pending proposals all deleted.

    Per MD: user can delete EVERYTHING. Cascading delete across the 3 tables.
    Returns True if anything was deleted, False if no profile existed.
    """
    row = session.query(UserModelRow).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return False

    org_unit = row.org_unit
    actor = actor or user_id

    session.query(UserModelEditRow).filter_by(user_id=user_id).delete()
    session.query(UserModelProposalRow).filter_by(user_id=user_id).delete()
    session.delete(row)
    session.flush()

    audit.record(
        org_id=org_unit,
        actor_type="user",
        actor_id=actor,
        action="config_changed",
        target_type="user_model",
        target_id=user_id,
        metadata={"op": "delete_full_wipe"},
    )
    log.info("user_model_deleted", user_id=user_id, actor=actor)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


def _row_to_model(row: UserModelRow) -> UserModel:
    field_meta = {k: FieldMeta.model_validate(v) for k, v in (row.field_meta_jsonb or {}).items()}
    return UserModel(
        user_id=row.user_id,
        org_unit=row.org_unit,
        voice=Voice.model_validate(row.voice_jsonb or {}),
        decision_policy=DecisionPolicy.model_validate(row.decision_policy_jsonb or {}),
        process_habits=ProcessHabits.model_validate(row.process_habits_jsonb or {}),
        priorities=Priorities.model_validate(row.priorities_jsonb or {}),
        relationships={k: RelationshipTag(v) for k, v in (row.relationships_jsonb or {}).items()},
        red_lines=list(row.red_lines_jsonb or []),
        field_meta=field_meta,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _field_to_column(field: str) -> str:
    """Map public field name to DB column name."""
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


def _serialize_field_value(field: str, value: Any) -> Any:
    """Convert a typed Pydantic / dict / list value to JSON-storable shape."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if field == "relationships" and isinstance(value, dict):
        return {k: (v.value if hasattr(v, "value") else v) for k, v in value.items()}
    if field == "red_lines":
        return list(value)
    return value
