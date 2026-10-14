"""STEP-14 · an expert card in the gold shape — who and what the file is, what remains, why now, the move whole, its
alternative, when to stop, what done looks like, its window, its receipts, the measured confidence.

    .venv/bin/python -m pytest -q tests/deliver/test_an_expert_card_is_in_the_gold_shape.py

Tree `yc2_w27_s14` M43.C3.L-interface.V3.U01 (`deliver/card_builder.build_draft`; STEP-14 §8.4 item 5, s14-F6–F9,
s14-D8). Measured on the 39 golden expert cards: why now 0/39, what remains 0/39, role 0/39, a bare domain as the
subject 21/39, the window the 7-day default 20/39, R = 50 (a default) 39/39, and the move cut at 60 characters —
38/39 longer, 10 cut mid-phrase, the date then on no field. The decision now carries the gold lines on its render
block (`reason/expert/decide._render`, `gold`); the card reads them:

  * the subject is the file's PERSON when it has one, its role the brief's, what remains its open asks, why now the
    trigger's sentence, the window the file's (said where it came from, among the card's receipts);
  * the move WHOLE under `recommended`; the headline the move CUT AT A CLAUSE, never on a bare function word
    (*"…before the"*, *"…call on"*) — by code, no prompt change (s14-D8);
  * the alternative and the stop rule as the check held them; only the confidence axes that were measured — the
    expert's reader publishes no recency, so R is a default and not shown;
  * a card no review wrote — and an expert card from before 0221, with no lines — is built as before.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.deliver import card_builder as B
from genios_engine.deliver.render import HEADLINE_CAP
from genios_engine.reason.expert import decide as D

pytestmark = pytest.mark.unit

AT = datetime(2026, 8, 12, tzinfo=timezone.utc)
MOVE = "Send Tara Sethi your deck to read ahead of a call, and offer her two times for the call"
WORDS = C.CardWords(headline=MOVE, situation="An investor your connector introduced has asked for your deck",
                    done_when="Tara has your deck and a call is booked", draft="Hi Tara, here is our deck.",
                    to="Tara Sethi", evidence=("evt_tara",), quotes=("could you send me your deck?",),
                    alternative="If the deck is not ready, write to Tara with a summary",
                    wait_or_stop="If no answer comes within a week, nudge once, then stop")
GOLD = {"subject": "Tara Sethi", "company": "quillstone.test", "kind_of_work": "investor", "role": "lead",
        "why_now": "Tara wrote on 6 Aug", "what_remains": ["Tara asked for your deck, since 6 Aug",
                                                       "you asked Tara for a call, since 6 Aug"],
        "recommended": {"who": "You", "what": MOVE, "for_whom": "Tara Sethi at Quillstone Ventures",
                        "by_when": None, "to": "Tara Sethi"},
        "alternative": WORDS.alternative, "wait_or_stop": WORDS.wait_or_stop,
        "window": {"days": 4, "from": "reply_time", "said": "how long this file's people take to reply, measured here"}}


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    monkeypatch.setattr(B, "load_node", lambda *_a, **_k: ("quillstone.test", "company", {}, {}))
    monkeypatch.setattr(B, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(B, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))
    monkeypatch.setattr(B, "co_recipients_for", lambda *_a, **_k: [])


def _signal(*, gold=GOLD, capability_id=D.CAPABILITY_ID, headline=MOVE, **over) -> dict:
    checked = C.CheckedReview(verdicts=(), fate=C.SHOWN, words=WORDS, cited=("evt_tara",))
    render = {"fallback": {"headline": headline, "situation": WORDS.situation}, "sources": D.sources_of(checked)}
    if gold is not None:
        render["gold"] = gold
    signal = {"signal_id": "sig_1", "subject_node_id": "node_q", "reason_code": "file_review",
              "level": "prescriptive", "score": 70, "play": D.MOVE_PLAY, "capability_id": capability_id,
              "evidence": [], "capability_render": render, "decision_window": 7,
              "score_inputs": {"U": 80, "I": 80, "R": 50, "C": 60}, "capability_domain": "founder_office",
              "play_review_state": "proposed"}
    signal.update(over)
    return signal


def _draft(signal):
    return B.build_draft(object(), "org_1", signal, {"pack_id": "founder_office", "templates": {}}, AT)


def test_the_card_reads_who_and_what_the_file_is_what_remains_and_why_now():
    draft = _draft(_signal())
    assert draft["business_subject"] == "Tara Sethi", "the file's person, never the bare domain"
    assert draft["relationship_role"] == "lead"
    assert draft["unresolved_item"] == "Tara asked for your deck, since 6 Aug; you asked Tara for a call, since 6 Aug"
    assert draft["why_now"] == "Tara wrote on 6 Aug"


def test_the_move_whole_is_recommended_beside_its_alternative_and_when_to_stop():
    draft = _draft(_signal())
    assert draft["recommended"] == GOLD["recommended"]
    assert (draft["alternative"], draft["wait_or_stop"]) == (WORDS.alternative, WORDS.wait_or_stop)


def test_the_window_is_the_files_and_says_where_it_came_from():
    draft = _draft(_signal())
    assert draft["outcome_window_days"] == 4
    [window] = [w for w in draft["why"] if w.get("source") == "card_lines"]
    assert window == {"window": GOLD["window"]["said"], "days": 4, "from": "reply_time", "source": "card_lines"}
    assert any(w.get("review") == B.PLAYBOOK_NOT_YET_REVIEWED for w in draft["why"]), "D3, said on the card"


def test_only_the_measured_confidence_axes_are_shown():
    draft = _draft(_signal())
    assert draft["confidence_vector"] == {"C": 60, "U": 80, "I": 80}, "R is the expert reader's default, not shown"
    other = _draft(_signal(gold=None, capability_id="expertise.opportunity"))
    assert other["confidence_vector"] == {"C": 60, "U": 80, "I": 80, "R": 50}, "the negative control"


@pytest.mark.parametrize("move, headline", [
    (MOVE, "Send Tara Sethi your deck to read ahead of a call"),
    ("Reply to Sofia Brandt accepting a twenty-minute product demo and proposing Tuesday or Wednesday afternoon",
     "Reply to Sofia Brandt accepting a twenty-minute product demo"),
    ("Confirm the call with Sana Qadri on Wednesday at 2 pm, to show her the monthly investor update",
     "Confirm the call with Sana Qadri on Wednesday at 2 pm"),
    ("Write to Omkar Joshi", "Write to Omkar Joshi"),
])
def test_the_headline_is_the_move_cut_at_a_clause(move, headline):
    assert B.gold_headline(move) == headline


@pytest.mark.parametrize("move", [
    "Accept the invite from Leela Krishnan of Ferngrove and read a one-page brief on her company before the call on Thursday",
    "Ask Kavitha Nair at Lakshya Accelerator whether the Demo Day slot on the twentieth is still held for us",
    "Tell Tanvi Shah whether you will apply to Copperleaf's founder programme for this year's cohort intake",
    # no clause ends inside the cap: cut at a word, and the bare "the" before it dropped
    "Prepare Kestrel Capital's diligence questionnaire plus the cap table summary for Monday",
])
def test_a_cut_never_ends_on_a_bare_function_word_and_is_the_moves_own_start(move):
    head = B.gold_headline(move)
    assert len(head) <= HEADLINE_CAP and move.startswith(head) and head
    assert move[len(head):len(head) + 1] in ("", " ", ","), f"cut inside a word: {head!r}"
    assert head.split()[-1].lower().strip(",;:—") not in B.FUNCTION_WORDS, head


def test_the_card_headline_is_cut_and_the_whole_move_is_recommended():
    draft = _draft(_signal())
    assert draft["_template"]["fallback"]["headline"] == "Send Tara Sethi your deck to read ahead of a call"
    assert draft["recommended"]["what"] == MOVE


def test_a_card_with_no_gold_lines_is_built_as_before():
    """An expert card from before 0221, and any card no review wrote: its fields as they were."""
    draft = _draft(_signal(gold=None))
    assert draft["business_subject"] == "quillstone.test" and draft["relationship_role"] is None
    assert draft["recommended"] is None and draft["alternative"] is None and draft["wait_or_stop"] is None
    assert draft["_template"]["fallback"]["headline"] == MOVE, "the renderer caps it, as before"


def test_a_held_files_card_recommends_nothing_and_keeps_its_question():
    gold = {**GOLD, "recommended": None}
    draft = _draft(_signal(gold=gold, headline="Is it so: Tara asked for your deck? It is not in what it cites."))
    assert draft["recommended"] is None and draft["business_subject"] == "Tara Sethi"
    assert draft["_template"]["fallback"]["headline"] == \
        "Is it so: Tara asked for your deck? It is not in what it cites.", "the question's own words, uncut"


def test_the_builder_version_moved():
    assert B.BUILDER_VERSION == "card-builder.v7-the-gold-shape"
