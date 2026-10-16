"""STEP-14 · an expert card is graded by its check, not by the formula lane's quote gate.

    .venv/bin/python -m pytest -q tests/deliver/test_an_expert_card_is_graded_by_its_check.py

Tree `yc2_w27_s14` M42.C3.L-logic.V0.U01 (`deliver/card_builder.build_draft`; STEP-14 §8.4 item 4, s14-F1). Measured
on 31 golden cases: 10 of 39 expert cards were demoted to `review` by the formula lane's gates — no counterparty
quote on record, so no Run Play and no app surface — 6 of them must-detect passes the app never showed. Wrong for an
expert card: its move rests on facts the check verified (`reason/expert/verify`) and is often OURS (write to the
person introduced, find a working address, accept an invite). So a shown move is prescriptive, grounded by the
sources its check kept (`_sentence_sources`); a held file's card is a question (`review`). `clarity_verdict`,
`states_absence` and `quotable` stay for every other card — the negative control. And the draft names its file
(`file_id`, `migrations/0220`): an expert card is its file's.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.deliver import card_builder as B
from genios_engine.reason.expert import decide as D

pytestmark = pytest.mark.unit

AT = datetime(2026, 8, 12, tzinfo=timezone.utc)
WORDS = C.CardWords(headline="Write to Maria directly", situation="Boardy introduced Maria on 11 Aug",
                    done_when="Maria has replied", draft="Hi Maria — Boardy introduced us.", to="Maria",
                    evidence=("evt_intro_0811",), quotes=())


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    monkeypatch.setattr(B, "load_node", lambda *_a, **_k: ("Maria Exconde", "person", {}, {}))
    monkeypatch.setattr(B, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(B, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))
    monkeypatch.setattr(B, "co_recipients_for", lambda *_a, **_k: [])


def _signal(capability_id=D.CAPABILITY_ID, fate=C.SHOWN, **over) -> dict:
    checked = (C.CheckedReview(verdicts=(), fate=C.SHOWN, words=WORDS, cited=("evt_intro_0811",))
               if fate == C.SHOWN else
               C.CheckedReview(verdicts=(), fate=C.HELD, words=C.CardWords(None, WORDS.situation, None, None, None),
                               cited=(), question="Did Maria ask to be written to?", because="misquoted (fact 1)"))
    signal = {"signal_id": "sig_1", "subject_node_id": "node_maria", "reason_code": "file_review",
              "level": "prescriptive", "score": 70, "play": D.MOVE_PLAY, "capability_id": capability_id,
              "evidence": [{"field": "thread.ball_in_court", "value": "us"}],
              "capability_render": {"fallback": {"headline": "Write to Maria directly", "situation": "s"},
                                    "sources": D.sources_of(checked)}}
    signal.update(over)
    return signal


def _draft(signal, quotes=None):
    return B.build_draft(object(), "org_1", signal, {"pack_id": "founder_office", "templates": {}}, AT,
                         quotes=quotes)


def test_a_shown_expert_move_with_no_quote_on_record_is_prescriptive_and_reaches_the_app():
    draft = _draft(_signal())
    assert (draft["level"], draft["abstained_because"]) == ("prescriptive", None)
    assert "run_play" in [a["type"] for a in draft["actions"]]
    assert draft["surfaces"][0] == "app", draft["surfaces"]
    assert draft["why"][0]["sentence"] == "headline" and draft["why"][0]["evidence"] == ["evt_intro_0811"], \
        "grounded by the sources its check kept"


def test_a_held_expert_card_is_a_question():
    draft = _draft(_signal(fate=C.HELD))
    assert draft["level"] == "review" and draft["abstained_because"]
    assert [a["type"] for a in draft["actions"]] == ["snooze", "wrong"]


def test_an_expert_card_with_no_check_on_it_is_never_graded_as_shown():
    """A decision that carries no sentence sources (a run before STEP-13's check) has nothing to stand on."""
    draft = _draft(_signal(capability_render={"fallback": {"headline": "h", "situation": "s"}}))
    assert draft["level"] == "review"


def test_an_absence_situation_on_an_expert_card_does_not_demote_it():
    signal = _signal(capability_render={**_signal()["capability_render"],
                                        "fallback": {"headline": "h", "situation": "s", "states_absence": True}})
    assert _draft(signal)["level"] == "prescriptive"


def test_any_other_card_with_no_quote_is_still_demoted():
    """⛔ THE NEGATIVE CONTROL: a corpus capability's card, no counterparty sentence on record — `review`, no Run
    Play, no app, as it always was."""
    draft = _draft(_signal(capability_id="expertise.opportunity", reason_code="opportunity"))
    assert draft["level"] == "review" and "run_play" not in [a["type"] for a in draft["actions"]]
    assert "app" not in draft["surfaces"]


def test_the_draft_names_its_file():
    assert _draft(_signal())["file_id"] == "node_maria"
    assert _draft(_signal(capability_id="expertise.opportunity", reason_code="opportunity"))["file_id"] is None


def test_why_a_held_card_does_not_instruct_is_its_own_phrase():
    assert _draft(_signal(fate=C.HELD))["abstained_because"] == B.EXPERT_HELD
    unchecked = _draft(_signal(capability_render={"fallback": {"headline": "h", "situation": "s"}}))
    assert unchecked["abstained_because"] == B.EXPERT_UNCHECKED


def test_a_headline_that_stands_on_nothing_is_never_shown_as_a_move():
    signal = _signal(capability_render={"fallback": {"headline": "h", "situation": "s"},
                                        "sources": {"headline": {"evidence": [], "quotes": []}}})
    assert (_draft(signal)["level"], _draft(signal)["abstained_because"]) == ("review", B.EXPERT_UNCHECKED)


def test_the_clarity_gate_is_the_formula_lanes_not_the_experts():
    """Whatever reason code an expert decision carries, the legacy clarity map never demotes it: its check grades it."""
    assert _draft(_signal(reason_code="unanswered_email"))["level"] == "prescriptive"
    assert _draft(_signal(capability_id="legacy", reason_code="unanswered_email"),
                  quotes=[{"quote": "Can you send it?", "kind": "statement", "from_counterparty": True}])["level"] \
        != "prescriptive", "the negative control: the gate still holds a legacy card"
