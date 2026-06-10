"""Inject the persona into other modules.

Per MD g-i-9 §3:
    g-i-2 reasoning:   decision_policy + process_habits + red_lines shape routing
                        (act vs ask) and which actions are even allowed.
    g-i-6 generation:  voice + priorities + relationships shape HOW a draft/brief reads
                        (tone, length, lead-with, formality per recipient).
    g-i-4 proactive:   priorities shape what is worth pushing to THIS user.

Every output passes through these adapters so it reads as *the user's*, not generic.
red_lines are a HARD gate (like g-i-2 hard constraints).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.foundations.telemetry import get_logger
from core.usermodel.schema import UserModel

log = get_logger(__name__)


@dataclass(frozen=True)
class AppliedPersona:
    """Bundle of persona-derived hints for a downstream module."""

    user_id: str
    force_flag: bool  # True if a redline matched and route MUST be FLAG
    redline_matches: list[str]
    decision_hints: dict[str, Any]
    narrator_hints: dict[str, Any]
    priority_boosts: dict[str, float]  # priority deltas keyed by topic / entity


# ─────────────────────────────────────────────────────────────────────────────
# g-i-2 — routing + allowed actions + redline veto
# ─────────────────────────────────────────────────────────────────────────────


def apply_to_decision(
    persona: UserModel | None,
    *,
    proposed_action: str,
    reversible: bool,
) -> AppliedPersona:
    """Return persona-derived hints for the g-i-2 decision pipeline.

    Hard veto: if any red_line matches the proposed action, force_flag=True regardless
    of confidence. This is the HARD GATE per MD.
    """
    if persona is None:
        return AppliedPersona(
            user_id="",
            force_flag=False,
            redline_matches=[],
            decision_hints={},
            narrator_hints={},
            priority_boosts={},
        )

    matches = persona.matches_redline(proposed_action)
    force_flag = bool(matches)

    decision_hints: dict[str, Any] = {
        "autonomous_if": list(persona.decision_policy.autonomous_if),
        "notify_first_if": list(persona.decision_policy.notify_first_if),
        "never_auto": list(persona.decision_policy.never_auto),
        "reversible_action": reversible,
    }
    # 'never_auto' conditions auto-promote to flag (same shape as redLines)
    for cond in persona.decision_policy.never_auto:
        if cond.lower() in proposed_action.lower():
            force_flag = True
            matches.append(f"never_auto:{cond}")

    if force_flag:
        log.info(
            "persona_force_flag",
            user_id=persona.user_id,
            matches=matches,
            action_preview=proposed_action[:64],
        )

    return AppliedPersona(
        user_id=persona.user_id,
        force_flag=force_flag,
        redline_matches=matches,
        decision_hints=decision_hints,
        narrator_hints={},
        priority_boosts={},
    )


# ─────────────────────────────────────────────────────────────────────────────
# g-i-4 — priorities for relevance scoring
# ─────────────────────────────────────────────────────────────────────────────


def apply_to_prioritizer(persona: UserModel | None) -> dict[str, float]:
    """Return per-topic priority boosts (additive deltas) the prioritizer can fold in.

    lead_with topics get + boost; deprioritize topics get - boost; time_wasters get strong -.
    Caller (g-i-4 prioritize) applies these multiplicatively on top of the base relevance score.
    """
    if persona is None:
        return {}
    boosts: dict[str, float] = {}
    for topic in persona.priorities.lead_with:
        boosts[topic.lower()] = 0.3
    for topic in persona.priorities.deprioritize:
        boosts[topic.lower()] = -0.2
    for topic in persona.priorities.time_wasters:
        boosts[topic.lower()] = -0.5
    return boosts


# ─────────────────────────────────────────────────────────────────────────────
# g-i-6 — tone + length + lead-with for narrator
# ─────────────────────────────────────────────────────────────────────────────


def apply_to_narrator(persona: UserModel | None) -> dict[str, Any]:
    """Return hints the g-i-6 narrator prepends to its system prompt.

    Includes voice + relationship-tagged contacts so the narrator can adapt tone
    per recipient (vip = warmer; cold_never_auto = block any auto-drafting).
    """
    if persona is None:
        return {}
    return {
        "tone": list(persona.voice.tone),
        "length_pref": persona.voice.length_pref,
        "openings": list(persona.voice.openings),
        "closings": list(persona.voice.closings),
        "never_say": list(persona.voice.never_say),
        "style_exemplars": list(persona.voice.style_exemplars),
        "lead_with": list(persona.priorities.lead_with),
        "relationships": {k: v.value for k, v in persona.relationships.items()},
    }
