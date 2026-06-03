"""
Phase 1, Item #4: validated output schema for proactive insight generation.

The narrative LLM returns memory_view + genios_view. Previously the parser
swallowed any malformed output and substituted a generic "Review this contact"
fallback. This module enforces:

  - presence of both fields
  - reasonable length bounds (so we don't ship 50-line monologues OR empty
    strings)
  - at least one recommendation verb in genios_view (matches the deck claim
    that GeniOS recommends concrete action, not just observations)
"""
from __future__ import annotations

from pydantic import BaseModel, field_validator


# Soft set — any of these counts. Keep generous; the validator is a guard
# against pure observation (no action), not a stylistic gate.
_ACTION_VERBS = (
    "call", "email", "schedule", "reach", "follow", "contact", "send",
    "draft", "ask", "ping", "check", "review", "dm", "message", "meet",
    "respond", "reply", "loop", "introduce", "intro", "share",
)


class InsightOutput(BaseModel):
    memory_view: str
    genios_view: str

    @field_validator("memory_view")
    @classmethod
    def memory_view_short(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("memory_view empty")
        if len(v) > 240:
            raise ValueError(f"memory_view too long: {len(v)} > 240 chars")
        return v

    @field_validator("genios_view")
    @classmethod
    def genios_view_has_action(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("genios_view empty")
        if len(v) > 600:
            raise ValueError(f"genios_view too long: {len(v)} > 600 chars")
        lowered = v.lower()
        if not any(verb in lowered for verb in _ACTION_VERBS):
            raise ValueError("genios_view missing action verb (recommend a specific next step)")
        return v
