"""STEP-14 · a version of a file's card says what it showed, what changed, and whether that is material.

    .venv/bin/python -m pytest -q tests/contracts/test_a_card_version_says_what_changed.py

`genios_engine/contracts/card_version.py` (tree `yc2_w27_s14` M42.C1.L-contract.V0.U02; STEP-14 §8.4 items 1-2,
s14-D1). A file's card lives: each new decision or question on the file is a VERSION of it — the words it showed
(headline, situation, the move, the draft, the lane), the signal it carried, the change (created, updated,
reworded, renewed, asked, answered, reopened) and whether it is MATERIAL by one closed rule: another ask,
recipient, date, lane or mode. A rewording or a renewal is a quiet version, kept in the card's history; only a
material one is pushed again. Pure and frozen; read back as stored.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import card_version as cv
from genios_engine.contracts.card_version import CardVersion, VersionWords, version_of

pytestmark = pytest.mark.unit

MOVE = VersionWords(headline="Reply to Maria today", situation="Maria asked for the deck on 11 Aug.",
                    move="Reply to Maria today with the deck she asked for", draft="Hi Maria — the deck.",
                    lane="decision", mode="act", ask="loop:deck", recipient="maria@alyst.vc",
                    by_when="2026-08-14")


def _with(words: VersionWords, **over) -> VersionWords:
    return VersionWords(**{**words.as_mapping(), **over})


def test_the_vocabularies_are_closed():
    assert cv.CHANGES == ("created", "updated", "reworded", "renewed", "asked", "answered", "reopened")
    assert cv.MATERIAL == ("ask", "recipient", "by_when", "lane", "mode")
    assert cv.WORDS == ("headline", "situation", "move", "draft")


def test_a_new_card_is_created_and_material():
    first = version_of(None, MOVE, version=1, signal_id="sig_1")
    assert (first.change, first.material, first.before, first.changed) == ("created", True, None, ())
    with pytest.raises(ValueError):
        version_of(None, MOVE, version=2, signal_id="sig_1")


@pytest.mark.parametrize("field, value", [
    ("ask", "loop:intro"), ("recipient", "ritika@alyst.vc"), ("by_when", "2026-08-21"),
    ("lane", "investigation"), ("mode", "wait"),
])
def test_another_ask_recipient_date_lane_or_mode_is_material(field, value):
    v = version_of(MOVE, _with(MOVE, **{field: value}), version=2, signal_id="sig_2")
    assert (v.change, v.material, v.changed) == ("updated", True, (field,))


@pytest.mark.parametrize("field", ["headline", "situation", "move", "draft"])
def test_other_words_alone_are_a_quiet_rewording(field):
    v = version_of(MOVE, _with(MOVE, **{field: "said otherwise"}), version=2, signal_id="sig_2")
    assert (v.change, v.material, v.changed) == ("reworded", False, (field,))


def test_the_same_advice_on_a_new_signal_is_a_quiet_renewal():
    v = version_of(MOVE, MOVE, version=3, signal_id="sig_3")
    assert (v.change, v.material, v.changed, v.before) == ("renewed", False, (), MOVE)


def test_a_material_change_beside_a_rewording_is_material():
    v = version_of(MOVE, _with(MOVE, headline="Send Maria the deck", by_when="2026-08-20"),
                   version=2, signal_id="sig_2")
    assert (v.change, v.material, v.changed) == ("updated", True, ("headline", "by_when"))


def test_a_question_version_is_asked():
    question = VersionWords(headline="Who at the fund decides?", situation="we hold this file until you answer",
                            lane="investigation", mode=cv.QUESTION_MODE, ask="fq_1")
    v = version_of(MOVE, question, version=2, signal_id="sig_q")
    assert (v.change, v.material) == ("asked", True)
    again = version_of(question, _with(question, ask="fq_2", headline="Is the round closed?"),
                       version=3, signal_id="sig_q2")
    assert (again.change, again.material) == ("asked", True), "another question is asked again"
    reworded = version_of(question, _with(question, situation="said otherwise"), version=3, signal_id="sig_q3")
    assert reworded.change == "reworded", "the same question, its words moved, is no new ask"


def test_an_answer_is_its_own_version():
    question = VersionWords(headline="Who decides?", situation="we hold this file until you answer",
                            lane="investigation", mode=cv.QUESTION_MODE, ask="fq_1")
    answer = VersionWords(headline="Your answer is in; the file is read again", situation="Who decides?",
                          lane="monitor", mode=cv.ANSWERED_MODE, ask="fq_1")
    v = version_of(question, answer, version=3, signal_id="sig_q", answered=True)
    assert (v.change, v.changed) == ("answered", ("headline", "situation", "lane", "mode"))
    with pytest.raises(ValueError):
        version_of(None, answer, version=1, signal_id="sig_q", answered=True)


def test_a_reopened_card_says_so_and_is_material_only_by_the_rule():
    quiet = version_of(MOVE, MOVE, version=2, signal_id="sig_2", reopened=True)
    assert (quiet.change, quiet.material) == ("reopened", False)
    moved = version_of(MOVE, _with(MOVE, by_when="2026-09-01"), version=2, signal_id="sig_2", reopened=True)
    assert (moved.change, moved.material, moved.changed) == ("reopened", True, ("by_when",))


@pytest.mark.parametrize("bad", [
    {"version": 0}, {"signal_id": " "}, {"change": "replaced"},
    {"change": "created", "before": None, "version": 2},
    {"change": "updated", "before": None, "changed": ()},        # only a created card has nothing before
    {"material": False},                                          # the rule says material
    {"changed": ("headline",)},                                   # not what changed
    {"changed": ("ask", "headline")},                             # …still material, and still not what changed
])
def test_a_version_that_is_not_one_is_refused(bad):
    good = version_of(MOVE, _with(MOVE, ask="loop:intro"), version=2, signal_id="sig_2").as_mapping()
    raw = {**good, **{k: (list(v) if isinstance(v, tuple) else v) for k, v in bad.items()}}
    if "before" in bad:
        raw["before"] = None
    with pytest.raises(ValueError):
        CardVersion.from_mapping(raw)


@pytest.mark.parametrize("bad", [{"headline": "  "}, {"situation": ""}])
def test_a_version_shows_words(bad):
    with pytest.raises(ValueError):
        _with(MOVE, **bad)


def test_words_are_read_as_shown_whitespace_and_all():
    w = _with(MOVE, headline="  Reply   to Maria\n today ")
    assert w.headline == "Reply to Maria today" and w == MOVE


def test_read_back_as_stored():
    for v in (version_of(None, MOVE, version=1, signal_id="sig_1"),
              version_of(MOVE, _with(MOVE, ask="loop:intro"), version=2, signal_id="sig_2"),
              version_of(MOVE, MOVE, version=3, signal_id="sig_3", reopened=True)):
        assert CardVersion.from_mapping(v.as_mapping()) == v
    import json
    stored = json.loads(json.dumps(version_of(MOVE, MOVE, version=2, signal_id="s").as_mapping()))
    assert CardVersion.from_mapping(stored).before == MOVE
