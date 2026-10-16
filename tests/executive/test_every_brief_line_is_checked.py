"""STEP-15 · the line check, pure — every written line held to its own item's material.

    .venv/bin/python -m pytest -q tests/executive/test_every_brief_line_is_checked.py

`executive/morning_check` (tree `yc2_w27_s15` M45.C2.L-logic.V0.U02). A written line is checked against its OWN
item's material by the engine's invention rule (`platform/grounding.invention_ok`: no name, number or date it was
not handed — which already refuses a connector or any other person the item's own material does not name); it
must call the founder "you" (`speaks_of_you`, `03` F178) and never state an address. The answer as a whole must
hand back exactly one line per item, in the item's own order — a count mismatch, or a line that cannot be told
apart from its neighbours, is MALFORMED, not checked line by line. A line that fails any check is given back its
item's own template words (`executive/morning_template.words_for`), with why; the budget is the whole answer's own
concern, read against what actually stands once every verdict is in.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_check as C
from genios_engine.executive import morning_order as O
from genios_engine.executive import morning_template as T

pytestmark = pytest.mark.unit


def _item(kind, about, *, words=(), numbers=(), dates=(), names=(), **over):
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about, subject=over.pop("subject", None),
                  material=B.Material(words=words, numbers=numbers, dates=dates, names=names),
                  sources=(B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), **over)


DECISION = _item(B.DECISION, "node_bluepeak", subject="Bluepeak",
                 words=(("name", "Bluepeak"), ("headline", "Introduce Meera Shah to the two pilot leads"),
                        ("reason", "Meera Shah's own deadline is this week")),
                 dates=(("by", "2026-10-02"),), names=("Meera Shah",))
QUESTION = _item(B.QUESTION, "node_cell", subject="University Startup Cell",
                 words=(("name", "University Startup Cell"),
                        ("question", "Find out whether you count as a startup incubated on the campus")))

FOUNDER = ("Rohit Swerashi",)


# ── one line, against its own item ──────────────────────────────────────────────────────────

def test_a_faithful_line_is_kept():
    check = C.check_line(DECISION, "Bluepeak: reply to Meera Shah about the two pilot leads.", founder=FOUNDER)
    assert check.verdict == B.KEPT
    assert check.reason is None
    assert check.words == "Bluepeak: reply to Meera Shah about the two pilot leads."


def test_a_name_the_item_does_not_hold_is_given_back():
    check = C.check_line(DECISION, "Bluepeak: ask Boardy to make the introduction.", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK
    assert check.reason and "name" in check.reason
    assert check.words == T.words_for(DECISION, B.TODAY)


def test_a_number_the_item_does_not_hold_is_given_back():
    check = C.check_line(DECISION, "Bluepeak: reply to Meera Shah within 3 days.", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK
    assert "number" in check.reason


def test_a_date_the_item_does_not_hold_is_given_back():
    check = C.check_line(DECISION, "Bluepeak: reply to Meera Shah by 9 Oct.", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK


def test_a_line_that_names_the_founder_is_given_back():
    check = C.check_line(DECISION, "Rohit Swerashi should reply to Meera Shah.", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK
    assert "you" in check.reason.lower()


def test_a_line_that_says_the_founder_is_given_back():
    check = C.check_line(DECISION, "The founder should reply to Meera Shah.", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK


def test_a_line_that_names_an_address_is_given_back():
    check = C.check_line(DECISION, "Reply to meera@bluepeak.test about the pilot.", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK
    assert "address" in check.reason


def test_an_empty_line_is_given_back():
    check = C.check_line(DECISION, "   ", founder=FOUNDER)
    assert check.verdict == B.GIVEN_BACK
    assert "empty" in check.reason


def test_a_question_item_is_checked_the_same_way():
    check = C.check_line(QUESTION, "University Startup Cell: find out whether you count as a startup.",
                         founder=FOUNDER)
    assert check.verdict == B.KEPT


def test_a_line_may_use_a_reason_the_item_actually_holds():
    check = C.check_line(DECISION, "Bluepeak: reply to Meera Shah — her own deadline is this week.",
                         founder=FOUNDER)
    assert check.verdict == B.KEPT


# ── the whole answer: one line per item, in order; malformed is not line-by-line ───────────

def test_a_faithful_answer_keeps_every_line():
    ordered = O.order((DECISION, QUESTION), now=datetime(2026, 9, 30, tzinfo=timezone.utc), tz="UTC")
    items = tuple(item for _section, held in ordered.sections for item in held)
    texts = tuple("Bluepeak: reply to Meera Shah." if i is DECISION else
                 "University Startup Cell: find out whether you count as a startup." for i in items)
    answer = C.check_answer(items, texts, founder=FOUNDER)
    assert not answer.malformed
    assert all(line.verdict == B.KEPT for line in answer.lines)
    assert answer.words == sum(B.count_words(t) for t in texts)


def test_a_different_count_of_lines_is_malformed_not_checked_line_by_line():
    answer = C.check_answer((DECISION, QUESTION), ("Bluepeak: reply to Meera Shah.",), founder=FOUNDER)
    assert answer.malformed
    assert answer.reason
    assert len(answer.lines) == 2
    assert all(line.verdict == B.GIVEN_BACK for line in answer.lines)


def test_an_empty_answer_for_no_items_is_not_malformed():
    answer = C.check_answer((), (), founder=FOUNDER)
    assert not answer.malformed
    assert answer.lines == ()
    assert answer.words == 0


def test_the_budget_is_read_against_what_actually_stands():
    """A long draft that fails the check is given back the TEMPLATE's words — shorter — so the answer's word
    count is the template's, not the draft's."""
    long_line = "Bluepeak: ask Boardy to " + " ".join(["please"] * 50) + "."       # invents "Boardy"
    answer = C.check_answer((DECISION,), (long_line,), founder=FOUNDER)
    assert answer.lines[0].verdict == B.GIVEN_BACK
    assert answer.words == B.count_words(T.words_for(DECISION, B.TODAY))
