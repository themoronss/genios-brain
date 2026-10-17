"""STEP-13b · a line cited by its own words is read as that line.

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_line_cited_by_its_words.py

Tree `yc2_w27_s13b` M37.C4.L-logic.V9.U04 (`reason/expert/verify`). Haiku cited a line of the dossier by its WORDS where
the dossier prints an id — "THE FILE", "WHAT WAS CHECKED" 86 times. A fact, inference or pattern citing the text of a line
the dossier prints EXACTLY ONCE, its ids aside, is corrected to that line's id and counted (`by_line`). A section title, a
version, a text that matches no line or several, or a line that prints several ids still drops: a slip of format, never of
fact. The line it names is then checked as if cited by id.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

KIND = "Kind of work: investor"


def _check(**over):
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)


def _v(checked, line):
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def _by_line(checked, line):
    return [v for v in checked.verdicts if v.line == line and v.reason == C.BY_LINE]


def test_a_fact_citing_a_line_by_its_words_is_read_as_that_line():
    cited_by_words = _check(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, KIND]})
    by_id = _check(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, "file:kind"]})
    assert _v(cited_by_words, "fact:4").verdict == _v(by_id, "fact:4").verdict == C.KEPT
    [note] = _by_line(cited_by_words, "fact:4")
    assert (note.verdict, note.detail) == (C.NOTED, f"{KIND} -> file:kind")
    assert not _by_line(by_id, "fact:4"), "an id cited as an id is no slip"


@pytest.mark.parametrize("cited", [KIND, "kind of  work: INVESTOR.", "“Kind of work: investor”",
                                   "- Kind of work: investor [file:kind]", "[file:kind] Kind of work: investor"])
def test_the_words_are_read_whole_whatever_the_marks_around_them(cited):
    checked = _check(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, cited]})
    assert _v(checked, "fact:4").verdict == C.KEPT, checked.verdicts


def test_an_inference_and_a_pattern_are_read_the_same_way():
    checked = _check(inferences=[{"claim": "Marco is an investor", "based_on": [KIND]}],
                     patterns=[{"kind": "pattern", "claim": "he answers in a week", "based_on": ["Whose move: ours"]}])
    assert _v(checked, "inference:1").verdict == _v(checked, "pattern:1").verdict == C.KEPT
    assert _by_line(checked, "inference:1") and _by_line(checked, "pattern:1")


@pytest.mark.parametrize("cited", [
    "THE FILE", "WHAT WAS CHECKED", "dossier.v2", "expert-review.v5",       # a title, a version
    "Kind of work: lawyer",                                                  # no such line
    "Kind of work",                                                          # part of a line is no line
    "Open asks:",                                                            # prints no id
    "Usual gap between touches",                                             # several ids on the line, and no whole text
])
def test_a_title_a_version_or_text_that_matches_no_line_still_drops(cited):
    checked = _check(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, cited]})
    assert (_v(checked, "fact:4").verdict, _v(checked, "fact:4").reason) == (C.DROPPED, C.UNKNOWN_EVIDENCE)
    assert not _by_line(checked, "fact:4")


def test_a_line_that_prints_several_ids_is_not_resolved_to_one():
    dossier, people = W.world()
    line = next(l for l in dossier.text.splitlines() if l.startswith("Usual gap between touches"))
    bare = " ".join(__import__("re").sub(r"\[[^\[\]\s]+\]", "", line).split())
    checked = check_review(W.review(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, bare]}),
                           dossier.text, people)
    assert _v(checked, "fact:4").reason == C.UNKNOWN_EVIDENCE and not _by_line(checked, "fact:4")


def test_a_text_that_matches_two_lines_is_not_resolved():
    dossier, people = W.world()
    doubled = dossier.text + "\nKind of work: investor [file:kind_again]"
    checked = check_review(W.review(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, KIND]}),
                           doubled, people)
    assert _v(checked, "fact:4").reason == C.UNKNOWN_EVIDENCE and not _by_line(checked, "fact:4")


def test_words_that_another_line_prints_without_an_id_are_not_printed_once():
    dossier, people = W.world()
    twice = dossier.text + "\nKind of work: investor"
    checked = check_review(W.review(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, KIND]}),
                           twice, people)
    assert _v(checked, "fact:4").reason == C.UNKNOWN_EVIDENCE


def test_the_line_named_is_checked_as_if_cited_by_id():
    """Cited by its words the fact still must stand on that line: a claim the line does not hold drops."""
    checked = _check(fact4={"claim": "Neel introduced Marco", "evidence": [KIND]})
    assert _v(checked, "fact:4").reason == C.UNSUPPORTED


def test_the_resolved_id_is_what_a_confidence_counts():
    checked = _check(fact4={"claim": "Introly introduced Marco on 4 Aug", "evidence": [W.INTRO, KIND]})
    assert "file:kind" in checked.cited and KIND not in checked.cited


def test_a_review_citing_no_words_is_checked_as_before():
    assert not [v for v in _check().verdicts if v.reason == C.BY_LINE]
    assert C.BY_LINE in C.NOTES
