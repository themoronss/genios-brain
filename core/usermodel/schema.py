"""Thin per-user profile types.

Per MD g-i-9 §1: kilobytes per user, NOT a corpus. Each field is a distilled
CONCLUSION (e.g. "polite + light humour, ~120 words"), not the underlying
emails / corrections that taught us the conclusion.

Source field tracks how the conclusion arrived:
- 'seeded'  -> user wrote it day-1
- 'learned' -> distilled from corrections (with confidence)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RelationshipTag(StrEnum):
    """How the user treats a specific entity."""

    VIP = "vip"
    FORMAL = "formal"
    CASUAL = "casual"
    COLD_NEVER_AUTO = "cold_never_auto"


# ─────────────────────────────────────────────────────────────────────────────
# Profile field schemas (each thin + JSON-shippable)
# ─────────────────────────────────────────────────────────────────────────────


class Voice(BaseModel):
    """How the user communicates. Used by g-i-6 narrator for tone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tone: list[str] = Field(default_factory=list, description="e.g. ['polite', 'light humour']")
    length_pref: str = Field(default="medium", description="short | medium | long")
    openings: list[str] = Field(default_factory=list, description="preferred greetings")
    closings: list[str] = Field(default_factory=list, description="preferred sign-offs")
    never_say: list[str] = Field(default_factory=list, description="forbidden phrases")
    style_exemplars: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="MAX 5 short representative snippets (NOT an archive)",
    )


class DecisionPolicy(BaseModel):
    """What the user lets the system do without asking. Used by g-i-2 routing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    autonomous_if: list[str] = Field(
        default_factory=list,
        description="conditions for act-without-asking (e.g. 'reversible' or 'follow_up_under_7d')",
    )
    notify_first_if: list[str] = Field(
        default_factory=list, description="conditions to draft + wait for one tap"
    )
    never_auto: list[str] = Field(default_factory=list, description="hard 'always ask me' cases")


class ProcessHabits(BaseModel):
    """Cadence + workflow defaults. Used by g-i-4 prioritizer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rules: list[str] = Field(
        default_factory=list,
        description="e.g. 'follow-up reminder at 7 days, then stop'",
    )


class Priorities(BaseModel):
    """What the user values / considers wasteful. Used by g-i-4 prioritizer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lead_with: list[str] = Field(default_factory=list, description="e.g. 'traction number first'")
    deprioritize: list[str] = Field(default_factory=list)
    time_wasters: list[str] = Field(default_factory=list)


class FieldMeta(BaseModel):
    """Confidence + provenance per profile field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["seeded", "learned"]
    confidence: float = Field(ge=0.0, le=1.0)
    last_updated: datetime


# ─────────────────────────────────────────────────────────────────────────────
# The full thin profile (the "persona")
# ─────────────────────────────────────────────────────────────────────────────


class UserModel(BaseModel):
    """Thin per-user persona. Kilobytes; NOT a corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: str
    org_unit: str = Field(..., description="per-org-unit namespacing — never leaks across users")
    voice: Voice = Field(default_factory=Voice)
    decision_policy: DecisionPolicy = Field(default_factory=DecisionPolicy)
    process_habits: ProcessHabits = Field(default_factory=ProcessHabits)
    priorities: Priorities = Field(default_factory=Priorities)
    relationships: dict[str, RelationshipTag] = Field(
        default_factory=dict,
        description="entityRef -> tag. entityRef points into Company Mind (g-i-3); the JUDGMENT lives here.",
    )
    red_lines: list[str] = Field(
        default_factory=list,
        description="HARD: system MUST NEVER do these, regardless of confidence",
    )
    field_meta: dict[str, FieldMeta] = Field(
        default_factory=dict,
        description="per-field source + confidence + last_updated",
    )
    created_at: datetime
    updated_at: datetime

    def matches_redline(self, action_description: str) -> list[str]:
        """Return any redLines that match the proposed action (case-insensitive substring).

        Per MD g-i-9: redLines are hard veto — force flag-to-human regardless of confidence.
        Conservative match: if action mentions any redline keyword, the redline triggers.
        """
        if not self.red_lines or not action_description:
            return []
        action_lower = action_description.lower()
        return [r for r in self.red_lines if r.lower() in action_lower]


# Module-level helpers used by other usermodel files
ALL_FIELD_NAMES: tuple[str, ...] = (
    "voice",
    "decision_policy",
    "process_habits",
    "priorities",
    "relationships",
    "red_lines",
)


def empty_profile_for(*, user_id: str, org_unit: str, now: datetime) -> UserModel:
    """Construct a blank profile (used by seed_profile when nothing exists yet)."""
    return UserModel(
        user_id=user_id,
        org_unit=org_unit,
        created_at=now,
        updated_at=now,
    )


def _field_payload_serializable(value: Any) -> Any:
    """Helper: collapse a profile field value to a JSON-safe dict for the meta + audit pipeline."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: (v.value if hasattr(v, "value") else v) for k, v in value.items()}
    return value
