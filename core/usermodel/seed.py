"""Day-1 user-authored seeding.

Per MD g-i-9 §2:
- User writes their own voice, redLines, priorities, decision policy, key
  relationships on day 1.
- Makes the model useful IMMEDIATELY (no cold-start emptiness).
- All seeded fields tagged source='seeded' with confidence=1.0.

This module is the persistence side. UI is in genios-dashboard (g-i-7 phase).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

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
from core.usermodel.store import UserModelRow

log = get_logger(__name__)


@dataclass(frozen=True)
class SeedInput:
    """User-authored content from the seeding wizard."""

    user_id: str
    org_unit: str
    voice: Voice | None = None
    decision_policy: DecisionPolicy | None = None
    process_habits: ProcessHabits | None = None
    priorities: Priorities | None = None
    relationships: dict[str, RelationshipTag] | None = None
    red_lines: list[str] | None = None


class SeedingError(Exception):
    """Seeding violated invariants (e.g. user already has a profile)."""


def seed_profile(session: Session, *, seed: SeedInput) -> UserModel:
    """Persist a day-1 profile. All fields tagged source='seeded' confidence=1.0.

    Raises SeedingError if the user already has a profile (use control.update_field
    to edit instead).
    """
    # Multi-tenant: same email can carry a separate persona per org. Scope
    # the existence check by both (user_id, org_unit) so a user creating
    # their profile in a new org doesn't get blocked by an unrelated row
    # in another org.
    existing = (
        session.query(UserModelRow)
        .filter_by(user_id=seed.user_id, org_unit=seed.org_unit)
        .one_or_none()
    )
    if existing is not None:
        raise SeedingError(
            f"User {seed.user_id} already has a profile in this org — use control.update_field to edit"
        )

    now = datetime.now(UTC)
    voice = seed.voice or Voice()
    decision_policy = seed.decision_policy or DecisionPolicy()
    process_habits = seed.process_habits or ProcessHabits()
    priorities = seed.priorities or Priorities()
    relationships = seed.relationships or {}
    red_lines = seed.red_lines or []

    field_meta: dict[str, FieldMeta] = {}
    for name in (
        "voice",
        "decision_policy",
        "process_habits",
        "priorities",
        "relationships",
        "red_lines",
    ):
        field_meta[name] = FieldMeta(source="seeded", confidence=1.0, last_updated=now)

    row = UserModelRow(
        user_id=seed.user_id,
        org_unit=seed.org_unit,
        voice_jsonb=voice.model_dump(),
        decision_policy_jsonb=decision_policy.model_dump(),
        process_habits_jsonb=process_habits.model_dump(),
        priorities_jsonb=priorities.model_dump(),
        relationships_jsonb={k: v.value for k, v in relationships.items()},
        red_lines_jsonb=list(red_lines),
        field_meta_jsonb={k: v.model_dump(mode="json") for k, v in field_meta.items()},
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()

    audit.record(
        org_id=seed.org_unit,
        actor_type="user",
        actor_id=seed.user_id,
        action="config_changed",
        target_type="user_model",
        target_id=seed.user_id,
        metadata={"op": "seed", "fields_set": list(field_meta.keys())},
    )
    log.info("user_model_seeded", user_id=seed.user_id, fields=list(field_meta.keys()))

    return UserModel(
        user_id=seed.user_id,
        org_unit=seed.org_unit,
        voice=voice,
        decision_policy=decision_policy,
        process_habits=process_habits,
        priorities=priorities,
        relationships=relationships,
        red_lines=red_lines,
        field_meta=field_meta,
        created_at=now,
        updated_at=now,
    )
