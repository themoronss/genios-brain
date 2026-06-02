"""Tests for apply.py — persona injection into g-i-2, g-i-4, g-i-6."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.usermodel.apply import (
    apply_to_decision,
    apply_to_narrator,
    apply_to_prioritizer,
)
from core.usermodel.schema import (
    DecisionPolicy,
    Priorities,
    ProcessHabits,
    RelationshipTag,
    UserModel,
    Voice,
)


def _now() -> datetime:
    return datetime(2026, 6, 1, tzinfo=UTC)


def _make_persona(
    *,
    red_lines: list[str] | None = None,
    never_auto: list[str] | None = None,
    tone: list[str] | None = None,
    lead_with: list[str] | None = None,
    deprioritize: list[str] | None = None,
    time_wasters: list[str] | None = None,
    relationships: dict[str, RelationshipTag] | None = None,
) -> UserModel:
    return UserModel(
        user_id="u",
        org_unit="sales",
        voice=Voice(tone=tone or []),
        decision_policy=DecisionPolicy(never_auto=never_auto or []),
        process_habits=ProcessHabits(),
        priorities=Priorities(
            lead_with=lead_with or [],
            deprioritize=deprioritize or [],
            time_wasters=time_wasters or [],
        ),
        relationships=relationships or {},
        red_lines=red_lines or [],
        field_meta={},
        created_at=_now(),
        updated_at=_now(),
    )


# ── g-i-2: redline veto ───────────────────────────────────────────────────


@pytest.mark.unit
def test_redline_forces_flag_regardless_of_confidence() -> None:
    """Per MD g-i-9: redLines are HARD GATE — override confidence."""
    persona = _make_persona(red_lines=["weekend email", "cold outreach"])
    out = apply_to_decision(
        persona, proposed_action="Send weekend email to Acme CEO", reversible=True
    )
    assert out.force_flag is True
    assert "weekend email" in out.redline_matches


@pytest.mark.unit
def test_never_auto_also_triggers_flag() -> None:
    """decision_policy.never_auto items behave like soft redlines."""
    persona = _make_persona(never_auto=["bulk_email"])
    out = apply_to_decision(
        persona, proposed_action="Schedule bulk_email blast for tomorrow", reversible=True
    )
    assert out.force_flag is True


@pytest.mark.unit
def test_no_redline_no_force_flag() -> None:
    persona = _make_persona(red_lines=["weekends"])
    out = apply_to_decision(
        persona, proposed_action="Send follow-up Tuesday morning", reversible=True
    )
    assert out.force_flag is False
    assert out.redline_matches == []


@pytest.mark.unit
def test_none_persona_yields_empty_hints() -> None:
    """Backward compat — caller passes None when user has no profile."""
    out = apply_to_decision(None, proposed_action="anything", reversible=True)
    assert out.force_flag is False
    assert out.redline_matches == []


# ── g-i-4: prioritizer boosts ─────────────────────────────────────────────


@pytest.mark.unit
def test_priority_boosts_for_lead_with_and_time_wasters() -> None:
    persona = _make_persona(
        lead_with=["traction", "revenue"],
        deprioritize=["status_updates"],
        time_wasters=["FYI_only_emails"],
    )
    boosts = apply_to_prioritizer(persona)
    assert boosts["traction"] == 0.3
    assert boosts["revenue"] == 0.3
    assert boosts["status_updates"] == -0.2
    assert boosts["fyi_only_emails"] == -0.5  # lowercased


@pytest.mark.unit
def test_prioritizer_none_persona_empty() -> None:
    assert apply_to_prioritizer(None) == {}


# ── g-i-6: narrator hints ─────────────────────────────────────────────────


@pytest.mark.unit
def test_narrator_hints_carry_voice_and_relationships() -> None:
    persona = _make_persona(
        tone=["polite", "warm"],
        lead_with=["traction"],
        relationships={
            "acme_ceo": RelationshipTag.VIP,
            "cold_lead": RelationshipTag.COLD_NEVER_AUTO,
        },
    )
    hints = apply_to_narrator(persona)
    assert hints["tone"] == ["polite", "warm"]
    assert hints["relationships"]["acme_ceo"] == "vip"
    assert hints["relationships"]["cold_lead"] == "cold_never_auto"
    assert "traction" in hints["lead_with"]


@pytest.mark.unit
def test_narrator_none_persona_empty() -> None:
    assert apply_to_narrator(None) == {}
