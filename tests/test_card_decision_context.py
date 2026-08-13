"""Update 1 — the card decision-context clarity gate.

These tests pin the deterministic contract: a card may carry a confident action imperative ONLY when
its decisive context is grounded; otherwise it fails closed to `review_source`. Scores, tags, and
profile attributes can never bypass the gate, and fields we cannot ground stay `missing` rather than
being invented.
"""
from genios_engine.api.routes import (
    _actionability,
    _annotate_effects,
    _confidence_block,
    _decision_projection,
)


# ── the clarity gate ────────────────────────────────────────────────────────────
def test_unanswered_with_a_recorded_ask_is_actionable():
    assert _actionability("unanswered_email", {"question"}, set())["state"] == "actionable"


def test_unanswered_without_any_ask_fails_closed():
    a = _actionability("unanswered_email", {"positive_reply"}, set())
    assert a["state"] == "context_incomplete"
    assert "what response they need" in a["missing"]


def test_commitment_without_promised_outcome_fails_closed():
    a = _actionability("commitment_overdue", set(), {"commitment.due_at"})
    assert a["state"] == "context_incomplete"


def test_commitment_with_promised_outcome_is_actionable():
    a = _actionability("commitment_overdue", set(), {"commitment.due_at", "commitment.action"})
    assert a["state"] == "actionable"


def test_meeting_without_agenda_fails_closed():
    assert _actionability("meeting_no_followup", set(), set())["state"] == "context_incomplete"


# ── decision projection ─────────────────────────────────────────────────────────
CARD = {"score_block": {"C": 77}, "situation": "6d since they wrote"}


def test_incomplete_context_yields_review_source_never_reply():
    incomplete = {"state": "context_incomplete", "missing": ["x"], "recommended": "Open it"}
    d = _decision_projection("unanswered_email", CARD, {}, set(), incomplete)
    assert d["recommendation"]["verdict"] == "review_source"
    assert "verif" in d["recommendation"]["avoid"].lower()


def test_grounded_unanswered_yields_reply_with_concrete_steps():
    ok = {"state": "actionable"}
    d = _decision_projection("unanswered_email", CARD, {}, {"question", "meeting_request"}, ok)
    assert d["recommendation"]["verdict"] == "reply"
    steps = d["recommendation"]["steps"]
    assert any("question" in s.lower() for s in steps)
    assert any("meeting" in s.lower() for s in steps)


def test_commitment_objective_carries_the_promised_outcome():
    ok = {"state": "actionable"}
    facts = {"commitment.action": "send the pricing deck"}
    d = _decision_projection("commitment_overdue", CARD, facts, set(), ok)
    assert "send the pricing deck" in d["recommendation"]["objective"]


def test_stakes_and_completion_stay_missing_until_captured():
    d = _decision_projection("unanswered_email", CARD, {}, {"question"}, {"state": "actionable"})
    assert d["grounding"]["stakes"] == "missing"
    assert d["grounding"]["completion"] == "missing"
    assert d["grounding"]["request"] == "grounded"


def test_confidences_are_separate_meanings():
    facts = {"company": "DevDash", "thread.last_inbound": "2026-08-09T00:00:00+00:00"}
    c = _confidence_block(facts, {"C": 81}, actionable=True)
    assert c["evidence"] == 81
    assert c["identity"] >= 80          # company on record → resolved identity
    assert c["situation"] >= 80         # trigger fact present
    # a non-actionable card must NOT inherit high recommendation confidence
    assert _confidence_block(facts, {"C": 81}, actionable=False)["recommendation"] == 10


# ── CTA effects ─────────────────────────────────────────────────────────────────
def test_cta_effects_are_documented_and_claim_is_not_completion():
    acts = _annotate_effects([{"type": "do_it_myself"}, {"type": "run_play"}, {"type": "snooze"}])
    by = {a["type"]: a["effect"] for a in acts}
    assert by["do_it_myself"] == "claim_only"   # claims ownership, never marks complete
    assert by["run_play"] == "draft_only"
    assert by["snooze"] == "defer_surface"
