"""STEP-13 · a number is its value with its unit (crosscheck X02, X45).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_figures.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U10 (`reason/expert/verify`, `contracts/expert_review.number_tokens`). A
number counted as checked when its DIGITS appeared anywhere on the cited item — the mail's own timestamp
(`2026-08-11 09:20 UTC`) grounded any small day-count, a sibling calculator on the same line grounded the
one cited ("quiet 5.89 days" is the longest gap, not the quiet), and "50 crore" stood on a mail that says
"50 lakh". Now a text's figures are read as what they are: printed dates and times are taken out first and
held to the dates and times its lines print; a `num:` id grounds only its own clause, never a sibling's;
a value carries its unit and magnitude (days ≠ weeks, lakh ≠ crore, M ≠ K, %, a currency) and must find
the same on its lines; Indian digit grouping (`12,50,000`) is one number. A calculator still corrects a
wrong value — only within its unit.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import number_tokens
from genios_engine.reason.expert.verify import check_review, value_of
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

QUIET = "num:days_quiet"


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


@pytest.mark.parametrize("said", ["5.89", "2", "7"])
def test_a_calculator_grounds_only_its_own_value_never_a_sibling_s(said):
    """X02's run: the timeline prints usual gap, longest gap and quiet on ONE line. "Quiet 5.89 days" is
    the longest gap's value — corrected to the quiet's own, as "2" (in the usual gap's "2 times") is."""
    checked = _check(fact3={"claim": f"The file has been quiet {said} days", "evidence": [QUIET]})
    assert _verdict(checked, "fact:3") == C.LineVerdict(
        "fact:3", C.CORRECTED, C.BY_CALCULATOR, f"number:{said} -> 8.99 ({QUIET})")


def test_a_mail_s_timestamp_grounds_no_date_and_no_count():
    """X02's runs: "on 10 Aug" stood on the introduction's 10:00, "20 days" on the ask's 09:20."""
    late = _check(fact4={"claim": "Introly introduced Marco on 10 Aug"})
    assert _verdict(late, "fact:4") == C.LineVerdict("fact:4", C.DROPPED, C.WRONG_NUMBER, "number:10 Aug")
    count = _check(fact1={"claim": "Marco asked 20 days ago for a short deck before setting up a call"})
    assert _verdict(count, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.WRONG_NUMBER, "number:20")
    assert _verdict(_check(), "fact:4").verdict == C.KEPT, "the introduction's own date, 4 Aug, stands"


def test_a_timestamp_s_digits_ground_no_number_in_the_card():
    checked = _check(move={"what": "Send Marco the 9 slides and offer two times for a call"})
    assert _verdict(checked, "move") == C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:9")
    assert checked.fate == C.HELD


@pytest.mark.parametrize("claim, kept", [
    ("Marco wrote at 9:20 on 11 Aug", True),
    ("Marco wrote at 09:20 UTC on 2026-08-11", True),
    ("Marco wrote on 11 Aug 2026", True),
    ("Marco wrote on the 11th", True),
    ("Marco wrote at 9:30 on 11 Aug", False),
    ("Marco wrote on 11 Aug 2025", False),
    ("Marco wrote on the 12th", False),
    ("Marco wrote on 11 Sep", False),
    ("Marco wrote on Aug 11", True),
    ("Marco wrote on Aug 12", False),
    ("Marco wrote in 2026", True),                    # a year stands on a date of that year
    ("Marco wrote in 2025", False),
])
def test_a_date_and_a_time_are_held_to_the_dates_and_times_its_lines_print(claim, kept):
    checked = _check(fact1={"claim": claim, "quote": None}, move={"rests_on": ["fact:2"]})
    assert (_verdict(checked, "fact:1").verdict == C.KEPT) is kept, _verdict(checked, "fact:1")


def test_a_card_text_holds_a_calculator_to_its_own_value_too():
    """The move and the situation read a calculator's figures as the facts do: its own clause only."""
    over = dict(fact3={"claim": "The file has been quiet 8.99 days", "evidence": [QUIET]},
                move={"rests_on": ["fact:1", "fact:2", "fact:3"],
                      "what": "Send Marco the short deck; the file has been quiet 5.89 days"})
    checked = _check(**over)
    assert _verdict(checked, "move") == C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:5.89")
    situation = _check(fact3=over["fact3"], frames={"primary": "The file has been quiet 5.89 days",
                                                    "rivals": ["a pass"]})
    assert _verdict(situation, "situation") == C.LineVerdict("situation", C.DROPPED, C.WRONG_NUMBER,
                                                             "number:5.89")
    assert _check(**{**over, "move": {**over["move"], "what": "Send Marco the short deck; the file has "
                                                              "been quiet 8.99 days"}}).fate == C.SHOWN


def test_a_wrong_unit_is_no_value_and_no_calculator_corrects_across_units():
    """X02's run: "6 weeks" stood on "6 days". And a calculator corrects 9 days to its 8.99 days, never
    9 weeks to "8.99 weeks"."""
    weeks = _check(fact3={"claim": "Marco answered our first mail in 6 weeks"})
    assert _verdict(weeks, "fact:3") == C.LineVerdict("fact:3", C.DROPPED, C.WRONG_NUMBER, "number:6")
    across = _check(fact3={"claim": "The file has been quiet 9 weeks", "evidence": [QUIET]})
    assert _verdict(across, "fact:3") == C.LineVerdict("fact:3", C.DROPPED, C.WRONG_NUMBER, "number:9")
    days = _check(fact3={"claim": "The file has been quiet 9 days", "evidence": [QUIET]})
    assert _verdict(days, "fact:3").verdict == C.CORRECTED
    dated = _check(fact3={"claim": "Marco answered our first mail on 9 Aug", "evidence": [W.REPLY_TIME, W.INTRO]})
    assert _verdict(dated, "fact:3") == C.LineVerdict("fact:3", C.DROPPED, C.WRONG_NUMBER, "number:9 Aug"), \
        "a calculator corrects a value, never a date"


@pytest.mark.parametrize("mail, said, held", [
    ("We invest 50 lakh at seed.", "Marco invests 50 crore at seed", False),      # X02's run
    ("We invest 50 lakh at seed.", "Marco invests 50 lakh at seed", True),
    ("We invest $2M at seed.", "Marco invests 2K at seed", False),
    ("We invest $2M at seed.", "Marco invests ₹2M at seed", False),
    ("We invest $2M at seed.", "Marco invests 2M at seed", True),
    ("We invest $2M at seed.", "Marco invests $2 million at seed", True),
    ("40 of our funds invest at seed.", "40% of Marco's funds invest at seed", False),
    ("We can commit ₹12,50,000 this quarter.", "Marco can commit ₹1250000 this quarter", True),  # X45
])
def test_a_value_carries_its_unit_magnitude_and_currency(mail, said, held):
    words = f"Thanks Arjun — could you send a short deck before we set up a call? {mail}"
    checked = _check({"ask_words": words}, frames={"primary": said, "rivals": ["a pass"]})
    assert (checked.words.situation is not None) is held, _verdict(checked, "situation")
    if not held:
        assert _verdict(checked, "situation").reason == C.WRONG_NUMBER


def test_indian_grouping_is_one_number():
    """X45: `12,50,000` (twelve lakh fifty thousand) read as "12" and "50000"."""
    assert number_tokens("₹12,50,000 and 1,23,456.5") == {"1250000", "123456.5"}
    assert number_tokens("1,400 calls, on 7,8 and 9 Oct") == {"1400", "7", "8", "9"}, "STEP-12's, unchanged"


def test_figures_are_read_as_what_they_are():
    from genios_engine.reason.expert.verify import figures_in, unheld
    figs = figures_in("On 11 Aug at 9:20 Marco asked for ₹12,50,000 — 6 days, 40%, 2M — by the 15th [num:x_9]")
    assert figs.dates == {(8, 11, None)} and figs.times == {(9, 20)} and figs.days == {15}
    assert figs.values == {("1250000", "", "inr"), ("6", "d", ""), ("40", "%", ""), ("2", "m", "")}
    assert figures_in("at 3pm and 11 am, or 9.30 am").times == {(15, 0), (11, 0), (9, 30)}
    assert figures_in("Marco's note of 3.48 days").values == {("3.48", "d", "")}, "a decimal is no time"
    assert unheld(figures_in("6 days"), figures_in("quiet 6 days")) == []
    assert unheld(figures_in("6"), figures_in("quiet 6 days")) == [], "a bare count needs no unit"
    assert value_of("quiet now: 8.99 days [num:days_quiet]", QUIET) == "8.99"
