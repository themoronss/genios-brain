"""End-to-end user-model lifecycle: seed -> view -> update -> distill -> propose-confirm -> delete."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.usermodel import (
    DecisionPolicy,
    Priorities,
    RelationshipTag,
    Voice,
    confirm_proposal,
    delete_profile,
    distill_field,
    propose_shift,
    record_edit,
    reject_proposal,
    seed_profile,
    update_field,
    view_profile,
)
from core.usermodel.control import ProfileNotFound
from core.usermodel.propose import ProposalError
from core.usermodel.seed import SeedingError, SeedInput


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


# ── seed ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_seed_creates_thin_profile_with_all_fields_meta(session: Session) -> None:
    """Day-1 seed: all fields tagged source='seeded' confidence=1.0."""
    model = seed_profile(
        session,
        seed=SeedInput(
            user_id="u_alice",
            org_unit="sales",
            voice=Voice(tone=["polite", "warm"], length_pref="short"),
            decision_policy=DecisionPolicy(
                autonomous_if=["reversible"],
                never_auto=["bulk_email", "cold_outreach_at_night"],
            ),
            priorities=Priorities(lead_with=["traction"], deprioritize=["pure_polite_email"]),
            relationships={"acme_ceo": RelationshipTag.VIP},
            red_lines=["never email prospects on weekends", "never cold_email without consent"],
        ),
    )
    session.commit()

    assert model.user_id == "u_alice"
    assert "polite" in model.voice.tone
    assert "acme_ceo" in model.relationships
    assert model.relationships["acme_ceo"] == RelationshipTag.VIP
    # All 6 fields have seeded meta
    for field in (
        "voice",
        "decision_policy",
        "process_habits",
        "priorities",
        "relationships",
        "red_lines",
    ):
        assert model.field_meta[field].source == "seeded"
        assert model.field_meta[field].confidence == 1.0


@pytest.mark.unit
def test_seed_rejects_duplicate(session: Session) -> None:
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    with pytest.raises(SeedingError):
        seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))


# ── view + update ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_view_returns_profile(session: Session) -> None:
    seed_profile(
        session,
        seed=SeedInput(user_id="u", org_unit="sales", voice=Voice(tone=["formal"])),
    )
    session.commit()
    m = view_profile(session, user_id="u")
    assert m.voice.tone == ["formal"]


@pytest.mark.unit
def test_view_missing_raises(session: Session) -> None:
    with pytest.raises(ProfileNotFound):
        view_profile(session, user_id="nobody")


@pytest.mark.unit
def test_update_field_marks_seeded_full_confidence(session: Session) -> None:
    """User-driven edit overrides any learned conclusion with seeded+1.0."""
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    new = Voice(tone=["casual"], length_pref="long")
    m = update_field(session, user_id="u", field="voice", new_value=new)
    session.commit()
    assert m.voice.tone == ["casual"]
    assert m.field_meta["voice"].source == "seeded"
    assert m.field_meta["voice"].confidence == 1.0


# ── distill (learn from edits) ────────────────────────────────────────────


@pytest.mark.unit
def test_distill_below_volume_gate_no_update(session: Session) -> None:
    """3 consistent edits but gate is 5 -> no conclusion update."""
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    for _ in range(3):
        record_edit(
            session,
            user_id="u",
            field="voice",
            edit_diff={"old_value": "long", "new_value": "short"},
        )
    session.commit()

    result = distill_field(session, user_id="u", field="voice", volume_gate_n=5)
    assert result.updated is False
    assert result.n_consistent == 3


@pytest.mark.unit
def test_distill_above_volume_gate_updates_with_learned_meta(session: Session) -> None:
    """5+ consistent edits -> conclusion updated, source=learned, confidence > 0.5.

    edit_diff new_value MUST be a valid field shape (Voice dict for the voice field).
    Distill writes that value straight into the column.
    """
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    new_voice_dict = Voice(tone=["casual"], length_pref="short").model_dump()
    for _ in range(6):
        record_edit(
            session,
            user_id="u",
            field="voice",
            edit_diff={"old_value": None, "new_value": new_voice_dict},
        )
    session.commit()

    result = distill_field(session, user_id="u", field="voice", volume_gate_n=5)
    session.commit()

    assert result.updated is True
    assert result.n_consistent >= 5

    refreshed = view_profile(session, user_id="u")
    assert refreshed.voice.tone == ["casual"]
    assert refreshed.voice.length_pref == "short"
    assert refreshed.field_meta["voice"].source == "learned"
    assert refreshed.field_meta["voice"].confidence > 0.5


@pytest.mark.unit
def test_distill_bounded_window_drops_oldest(session: Session) -> None:
    """Edits beyond K are dropped during distill."""
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    for i in range(25):
        record_edit(
            session,
            user_id="u",
            field="voice",
            edit_diff={"old_value": "x", "new_value": f"v{i}"},
        )
    session.commit()

    result = distill_field(session, user_id="u", field="voice", window_k=20, volume_gate_n=100)
    session.commit()
    # 5 oldest dropped
    assert result.discarded_count == 5
    # Conclusion not updated (volume gate=100 not met)
    assert result.updated is False


# ── propose-confirm for big shifts ────────────────────────────────────────


@pytest.mark.unit
def test_propose_creates_pending_record(session: Session) -> None:
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    proposal = propose_shift(
        session,
        user_id="u",
        field="voice",
        proposed_value={"tone": ["formal"], "length_pref": "long"},
        signal_count=15,
        rationale="user has been writing notably longer + more formal for 2 weeks",
    )
    session.commit()
    assert proposal.status == "pending"
    assert proposal.signal_count == 15


@pytest.mark.unit
def test_confirm_proposal_applies_to_profile(session: Session) -> None:
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    session.commit()
    proposal = propose_shift(
        session,
        user_id="u",
        field="voice",
        proposed_value={"tone": ["formal"]},
        signal_count=10,
    )
    session.commit()
    confirmed = confirm_proposal(session, proposal_id=proposal.id, actor="u")
    session.commit()
    assert confirmed.status == "approved"

    refreshed = view_profile(session, user_id="u")
    assert refreshed.voice.tone == ["formal"]
    assert refreshed.field_meta["voice"].source == "learned"


@pytest.mark.unit
def test_reject_proposal_leaves_profile_unchanged(session: Session) -> None:
    seed_profile(
        session,
        seed=SeedInput(user_id="u", org_unit="sales", voice=Voice(tone=["casual"])),
    )
    session.commit()
    proposal = propose_shift(
        session,
        user_id="u",
        field="voice",
        proposed_value={"tone": ["formal"]},
        signal_count=10,
    )
    session.commit()
    rejected = reject_proposal(session, proposal_id=proposal.id, actor="u")
    session.commit()
    assert rejected.status == "rejected"

    refreshed = view_profile(session, user_id="u")
    # Original 'casual' preserved
    assert refreshed.voice.tone == ["casual"]


@pytest.mark.unit
def test_double_decide_proposal_rejected(session: Session) -> None:
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    proposal = propose_shift(
        session, user_id="u", field="voice", proposed_value={"tone": ["x"]}, signal_count=5
    )
    session.commit()
    confirm_proposal(session, proposal_id=proposal.id, actor="u")
    session.commit()
    with pytest.raises(ProposalError):
        confirm_proposal(session, proposal_id=proposal.id, actor="u")


# ── delete (full wipe) ────────────────────────────────────────────────────


@pytest.mark.unit
def test_delete_wipes_profile_and_history(session: Session) -> None:
    """Per MD: user can delete EVERYTHING — profile + edits + proposals all gone."""
    seed_profile(session, seed=SeedInput(user_id="u", org_unit="sales"))
    record_edit(session, user_id="u", field="voice", edit_diff={"old_value": "a", "new_value": "b"})
    propose_shift(
        session, user_id="u", field="voice", proposed_value={"tone": ["x"]}, signal_count=1
    )
    session.commit()

    deleted = delete_profile(session, user_id="u")
    session.commit()
    assert deleted is True

    with pytest.raises(ProfileNotFound):
        view_profile(session, user_id="u")


@pytest.mark.unit
def test_delete_unknown_user_returns_false(session: Session) -> None:
    assert delete_profile(session, user_id="nobody") is False
