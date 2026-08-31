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
    """Separate meanings, and only the ones we actually measure.

    `identity` used to be `85 if 'company' in facts else 30` and `situation` an 80/50 ternary —
    both invented in the API layer, which measures neither. This test asserted those inventions,
    so it certified the bug. The vector's SHAPE was right and its CONTENT was 75% fabricated.
    """
    facts = {"company": "DevDash", "thread.last_inbound": "2026-08-09T00:00:00+00:00"}
    c = _confidence_block(facts, {"C": 81}, actionable=True)
    assert c["evidence"] == 81                  # the one dimension the score block really carries
    # No correlated situation → say so, do not guess from whichever facts happen to be present.
    assert c["identity"] is None
    assert c["situation"] is None
    assert set(c["absent"]) == {"identity", "situation", "consistency"}
    assert c["source"] == "unavailable"
    # a non-actionable card must NOT inherit high recommendation confidence
    assert _confidence_block(facts, {"C": 81}, actionable=False)["recommendation"] == 10


def test_confidence_is_sourced_from_layer_2_when_a_situation_exists():
    """L2 computes a real five-dimension vector per situation; the API's job is to pass it
    through, not to re-derive it from a different input with different semantics."""
    sit = {"confidence_overall": 62, "confidence_identity": 90, "confidence_consistency": 62}
    c = _confidence_block({}, {"C": 81}, actionable=True, situation=sit)
    assert c["identity"] == 90
    assert c["situation"] == 62
    assert c["consistency"] == 62
    assert c["absent"] == []
    assert c["source"] == "context_situations"
    # The recommendation rests on its weakest input — re-emitting `evidence` under a second name
    # made a card look twice as substantiated as it was.
    assert c["recommendation"] == 62


# ── CTA effects ─────────────────────────────────────────────────────────────────
def test_cta_effects_are_documented_and_claim_is_not_completion():
    acts = _annotate_effects([{"type": "do_it_myself"}, {"type": "run_play"}, {"type": "snooze"}])
    by = {a["type"]: a["effect"] for a in acts}
    assert by["do_it_myself"] == "claim_only"   # claims ownership, never marks complete
    assert by["run_play"] == "draft_only"
    assert by["snooze"] == "defer_surface"


# ── the zero-clarity gate is pack data, not an if/elif chain ────────────────────
def test_an_undeclared_reason_code_fails_closed():
    """The old gate ended in an unconditional `return {"state": "actionable"}`.

    That covered 34 of 41 live signals and left the sales-critical remainder — closed_lost_risk,
    objection_open, demo_requested, timeline_slip — asserting a confident imperative with no
    grounding check at all, and handed every future rule the same free pass by default.
    """
    from genios_engine.reason.actionability import evaluate

    assert evaluate("a_rule_nobody_described", {"question"}, {"company"})["state"] == "context_incomplete"
    assert evaluate("closed_lost_risk", set(), set())["state"] == "context_incomplete"
    assert evaluate("closed_lost_risk", {"objection"}, set())["state"] == "actionable"


def test_every_pack_rule_declares_what_its_action_needs():
    """Adding a rule is a pack-data edit. Nobody making one would think to also edit an API
    projection helper, so the co-maintenance is enforced here instead of hoped for."""
    from genios_engine.reason.actionability import undeclared_reason_codes

    assert undeclared_reason_codes() == set(), (
        "these rules would ship an ungrounded imperative — declare their decisive context in "
        "SALES_V1_ACTIONABILITY / GENERAL_V1_ACTIONABILITY")


def test_the_match_requirement_and_the_action_requirement_are_different_things():
    """`commitment.due_at` is enough to know something is overdue and nowhere near enough to know
    what to deliver — which is how "deliver the commitment" shipped on commitments whose text was
    never captured."""
    from genios_engine.reason.actionability import REQUIREMENTS

    req = REQUIREMENTS["commitment_overdue"]
    assert "commitment.action" in req.facts
    assert "commitment.due_at" not in req.facts
