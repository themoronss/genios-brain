"""G1 · ALG-09 — the date/time normalizer. "Next week" is a range plus a certainty.

The acceptance rows are fixed by doc 05 L1.5.2 and are all here as one table: every one of the
eleven cascade rows, the two documented "next Friday" answers, the locale-unknown refusal, a DST
boundary in both directions, a timezone crossing, a past date that is kept rather than rolled
forward, and the same phrase against two different `eval_time` values producing two different
answers — which is the only assertion that can actually prove no clock is being read.

Two rules this file obeys, both learned the hard way:

* **Nothing is asserted about the module's text.** `tests/test_l1_seam.py:192` asserts a literal
  substring appears in a function's source, which passes for a rename and fails for a reformat —
  a test that measures typography. The purity checks at the bottom of this file parse the module
  into an AST and assert on what the code DOES: no float value, no clock call, no import outside
  a named allowlist. Those fail when the property fails and for no other reason.
* **Every expected instant is written out in full.** No expectation is computed with the same
  arithmetic the module uses, because a test that recomputes the answer agrees with the bug.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from pydantic import ValidationError

from genios_engine.capture.validate import dates as dates_module
from genios_engine.capture.validate.dates import (
    CalendarDuration,
    add_business_days,
    add_calendar_duration,
    resolve_calendar_duration,
    resolve_date,
    resolve_duration,
    resolve_recurrence,
)
from genios_engine.contracts.units import DateCertainty

WAVE = "W1"
GATE = "G1"

#: The shared Layer 1 clock, restated here so the table can name absolute instants instead of
#: recomputing them. `test_table_runs_against_the_shared_layer_1_clock` fails if the two drift.
EVAL = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)  # a Wednesday

EXACT = DateCertainty.EXACT
RANGE = DateCertainty.RANGE
RELATIVE = DateCertainty.RELATIVE
UNRESOLVED = DateCertainty.UNRESOLVED


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0,
        second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def end_of(year: int, month: int, day: int) -> datetime:
    """23:59:59 UTC — the instant an EXACT day resolves to for a UTC org."""
    return utc(year, month, day, 23, 59, 59)


@pytest.fixture
def cite(span_of):
    """One real `EvidenceSpan` per phrase, built by FINDING the phrase in a source string.

    `ResolvedDate` refuses to exist without evidence, and hand-built spans with invented offsets
    would make every row in this file a test of nothing. `span_of` locates the quote and raises
    if it is absent or ambiguous, so a span here is constructed the way L1.5.1 verifies one.
    """
    def _cite(phrase: str):
        return [span_of(phrase, text=f"the deadline is {phrase} and nothing else")]
    return _cite


def test_table_runs_against_the_shared_layer_1_clock(eval_time):
    """The suite has one clock (`tests/capture/conftest.py`). If it moves, every absolute instant
    written into the table below is silently wrong, so the two are pinned to each other."""
    assert EVAL == eval_time


# --------------------------------------------------------------------------------------------
# L1.5.2-U1 · the eleven-row cascade (ALG-09)
# --------------------------------------------------------------------------------------------

CASCADE_ROWS = [
    # (row, phrase, certainty, earliest, latest)
    (1, "2026-03-15", EXACT, end_of(2026, 3, 15), end_of(2026, 3, 15)),
    (1, "March 15, 2026", EXACT, end_of(2026, 3, 15), end_of(2026, 3, 15)),
    (1, "15 March 2026", EXACT, end_of(2026, 3, 15), end_of(2026, 3, 15)),
    (1, "2026/03/15", EXACT, end_of(2026, 3, 15), end_of(2026, 3, 15)),
    # 13 cannot be a month, so exactly one reading exists and no locale is needed to pick it.
    (1, "13/04/2026", EXACT, end_of(2026, 4, 13), end_of(2026, 4, 13)),
    # Two readings and no declared locale: refuse rather than pick. Rule 5 of the reverse prompt.
    (1, "03/04/2026", UNRESOLVED, None, None),
    (1, "2026-02-30", UNRESOLVED, None, None),
    # An explicit past date is kept as written — rule 6, "do NOT roll it forward".
    (1, "January 9, 2026", EXACT, end_of(2026, 1, 9), end_of(2026, 1, 9)),
    (2, "October 15", EXACT, end_of(2026, 10, 15), end_of(2026, 10, 15)),
    (2, "January 20", EXACT, end_of(2026, 1, 20), end_of(2026, 1, 20)),
    # No year given, so the phrase means the NEXT January 9th — 2026's has already gone.
    (2, "January 9", EXACT, end_of(2027, 1, 9), end_of(2027, 1, 9)),
    (2, "15 October", EXACT, end_of(2026, 10, 15), end_of(2026, 10, 15)),
    (3, "by Friday", EXACT, end_of(2026, 1, 16), end_of(2026, 1, 16)),
    # Said ON a Wednesday: strictly after the eval date, so a week out, never today.
    (3, "Wednesday", EXACT, end_of(2026, 1, 21), end_of(2026, 1, 21)),
    (4, "today", EXACT, end_of(2026, 1, 14), end_of(2026, 1, 14)),
    (4, "tomorrow", EXACT, end_of(2026, 1, 15), end_of(2026, 1, 15)),
    (4, "yesterday", EXACT, end_of(2026, 1, 13), end_of(2026, 1, 13)),
    (5, "next week", RANGE, utc(2026, 1, 19), end_of(2026, 1, 25)),
    (5, "next month", RANGE, utc(2026, 2, 1), end_of(2026, 2, 28)),
    (5, "next quarter", RANGE, utc(2026, 4, 1), end_of(2026, 6, 30)),
    (6, "this week", RANGE, EVAL, end_of(2026, 1, 18)),
    (6, "this month", RANGE, EVAL, end_of(2026, 1, 31)),
    (7, "end of month", RANGE, utc(2026, 1, 29), end_of(2026, 1, 31)),
    (7, "end of the quarter", RANGE, utc(2026, 3, 29), end_of(2026, 3, 31)),
    (7, "end of Q3", RANGE, utc(2026, 9, 28), end_of(2026, 9, 30)),
    # "of" before the period word keeps rows 5 and 6 off it — this is row 7's three-day window,
    # not row 5's four-week one.
    (7, "end of next month", RANGE, utc(2026, 2, 26), end_of(2026, 2, 28)),
    (7, "end of this month", RANGE, utc(2026, 1, 29), end_of(2026, 1, 31)),
    (8, "in 3 days", EXACT, end_of(2026, 1, 17), end_of(2026, 1, 17)),
    (8, "in 2 weeks", EXACT, end_of(2026, 1, 28), end_of(2026, 1, 28)),
    (8, "in 3 months", EXACT, end_of(2026, 4, 14), end_of(2026, 4, 14)),
    (8, "within two weeks", EXACT, end_of(2026, 1, 28), end_of(2026, 1, 28)),
    # Five business days from a Wednesday is seven calendar days — the whole point of U3.
    (8, "in 5 business days", EXACT, end_of(2026, 1, 21), end_of(2026, 1, 21)),
    (9, "pretty soon", RELATIVE, EVAL, utc(2026, 1, 28, 9)),
    (9, "shortly", RELATIVE, EVAL, utc(2026, 1, 28, 9)),
    (10, "later", RELATIVE, EVAL, utc(2026, 4, 14, 9)),
    (10, "down the line", RELATIVE, EVAL, utc(2026, 4, 14, 9)),
    (11, "the vendor will circle back to us", UNRESOLVED, None, None),
    (11, "in a few weeks", UNRESOLVED, None, None),
]


@pytest.mark.gate
@pytest.mark.parametrize(
    ("row", "phrase", "certainty", "earliest", "latest"), CASCADE_ROWS,
    ids=[f"row{row:02d}-{phrase}" for row, phrase, _, _, _ in CASCADE_ROWS])
def test_cascade_row_resolves_to_its_documented_window(row, phrase, certainty, earliest, latest,
                                                       cite):
    """One row per phrase class doc 05 names, resolved against the shared Wednesday in UTC.

    The `row` column is the cascade rule that must claim the phrase; it is carried so a failure
    names the rule that misfired rather than only the string that broke.
    """
    resolved = resolve_date(phrase, eval_time=EVAL, tz="UTC", evidence=cite(phrase))

    assert resolved.certainty is certainty, f"row {row}"
    assert resolved.earliest == earliest, f"row {row}"
    assert resolved.latest == latest, f"row {row}"
    assert resolved.as_written == phrase
    assert resolved.resolved_against == EVAL


def test_every_cascade_row_of_the_spec_is_covered():
    """The acceptance line is "every one of the 11 cascade rows". A table that quietly lost row 7
    would still be green, so the coverage of the table is itself asserted."""
    assert {row for row, *_ in CASCADE_ROWS} == set(range(1, 12))


@pytest.mark.parametrize(("phrase", "certainty"), [
    ("2026-03-15", EXACT), ("next week", RANGE), ("pretty soon", RELATIVE),
    ("no date at all", UNRESOLVED),
])
def test_certainty_and_window_always_agree(phrase, certainty, cite):
    """The contract's own invariants, checked on real normalizer output rather than on
    hand-built objects: EXACT is one instant, UNRESOLVED carries no window, and everything else
    is a non-empty interval that runs forwards."""
    resolved = resolve_date(phrase, eval_time=EVAL, tz="UTC", evidence=cite(phrase))

    assert resolved.certainty is certainty
    if certainty is UNRESOLVED:
        assert resolved.earliest is None and resolved.latest is None
        assert resolved.window is None
    elif certainty is EXACT:
        assert resolved.earliest == resolved.latest
    else:
        assert resolved.earliest < resolved.latest
        assert resolved.window == (resolved.earliest, resolved.latest)


# --------------------------------------------------------------------------------------------
# Rule precedence: WHICH cascade row is allowed to claim a period phrase (D3)
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("phrase", "earliest", "latest"), [
    # The article-free forms, which were always right, kept alongside so the pair reads as one
    # question: does an optional "the" change which rule answers?
    ("end of next quarter", utc(2026, 6, 28), end_of(2026, 6, 30)),
    ("end of the next quarter", utc(2026, 6, 28), end_of(2026, 6, 30)),
    ("end of next month", utc(2026, 2, 26), end_of(2026, 2, 28)),
    ("end of the next month", utc(2026, 2, 26), end_of(2026, 2, 28)),
    ("end of next week", utc(2026, 1, 23), end_of(2026, 1, 25)),
    ("end of the next week", utc(2026, 1, 23), end_of(2026, 1, 25)),
    ("end of this month", utc(2026, 1, 29), end_of(2026, 1, 31)),
    ("end of the current month", utc(2026, 1, 29), end_of(2026, 1, 31)),
    ("end of the current quarter", utc(2026, 3, 29), end_of(2026, 3, 31)),
    ("close of the next quarter", utc(2026, 6, 28), end_of(2026, 6, 30)),
    ("end of the next year", utc(2027, 12, 29), end_of(2027, 12, 31)),
])
def test_an_article_before_the_qualifier_still_leaves_the_phrase_with_row_7(phrase, earliest,
                                                                           latest, cite):
    """"End of THE next quarter" is the same promise as "end of next quarter" — three days.

    Row 7's own pattern accepts the article, so the article form is known to occur; the question
    is only which row gets to answer it. Rows 5 and 6 answer with the WHOLE period, and a
    ninety-one-day window where a three-day one was written is a deadline that never looks
    urgent — the proximity term of ALG-17 reads the width, not the words. The precedence has to
    hold for every prefix row 7 accepts, not for the one spelling somebody happened to test.
    """
    resolved = resolve_date(phrase, eval_time=EVAL, tz="UTC", evidence=cite(phrase))

    assert resolved.certainty is RANGE
    assert (resolved.earliest, resolved.latest) == (earliest, latest)


#: How wide each answer is, in LOCAL CALENDAR DAYS covered by [earliest, latest] against the
#: shared Wednesday clock. Written out per class and per period rather than derived, because the
#: width is the thing a hijack destroys: the last few days of a period are three days wide
#: whichever period it is, so a row that lets a wider rule claim the phrase shows up as 3 -> 91
#: rather than as an off-by-one nobody reads.
SPAN_DAYS = {
    #: row 7 — the last three days of the named period.
    "END_OF": {"week": 3, "month": 3, "quarter": 3, "year": 3},
    #: row 5 — the whole of the following period (Feb 2026, Q2 2026, 2027).
    "WHOLE_NEXT": {"week": 7, "month": 28, "quarter": 91, "year": 365},
    #: row 6 — the eval instant to the end of the current period (Wed 14 Jan 2026).
    "REST_OF_THIS": {"week": 5, "month": 18, "quarter": 77, "year": 352},
    #: row 11 — no row claims it. A phrase this file has no rule for gets no window at all,
    #: which is the honest answer and not a defect; a WRONG window would be.
    "NO_WINDOW": None,
}

#: Every optional prefix the period patterns actually accept, plus the ones they do not, so the
#: table covers the boundary rather than only the inside of it. "the X" rows are the D3 shape.
QUALIFIERS = ("", "the", "this", "current", "next", "the current", "the next",
              "last", "coming", "upcoming", "the last", "the coming", "the upcoming")

#: Row 7's two openers ("end of" / "close of") against everything else somebody writes in front
#: of a period. `mid` carries no "of", which is deliberate: the `(?<!of )` guard that used to
#: sit on rows 5 and 6 keyed on that one token, so the two spellings had to answer differently.
CLAIMED_BY = {
    ("end of", ""): "END_OF", ("end of", "the"): "END_OF",
    ("end of", "this"): "END_OF", ("end of", "current"): "END_OF",
    ("end of", "next"): "END_OF",
    ("end of", "the current"): "END_OF", ("end of", "the next"): "END_OF",
    # No row reads a period backwards or reads "coming" at all — see the gap note in the test.
    ("end of", "last"): "NO_WINDOW", ("end of", "coming"): "NO_WINDOW",
    ("end of", "upcoming"): "NO_WINDOW", ("end of", "the last"): "NO_WINDOW",
    ("end of", "the coming"): "NO_WINDOW", ("end of", "the upcoming"): "NO_WINDOW",
    # start-of / beginning-of / mid: row 7 never matches, so rows 5 and 6 answer with the period
    # that CONTAINS the moment named. Wider than the phrase, but its bounds are the right ones
    # and RANGE says it is not a point; the alternative is no window at all.
    ("plain", ""): "NO_WINDOW", ("plain", "the"): "NO_WINDOW",
    ("plain", "this"): "REST_OF_THIS", ("plain", "current"): "REST_OF_THIS",
    ("plain", "next"): "WHOLE_NEXT",
    ("plain", "the current"): "REST_OF_THIS", ("plain", "the next"): "WHOLE_NEXT",
    ("plain", "last"): "NO_WINDOW", ("plain", "coming"): "NO_WINDOW",
    ("plain", "upcoming"): "NO_WINDOW", ("plain", "the last"): "NO_WINDOW",
    ("plain", "the coming"): "NO_WINDOW", ("plain", "the upcoming"): "NO_WINDOW",
}

PRECEDENCE_ROWS = [
    (prefix, qualifier, period,
     CLAIMED_BY[("end of" if prefix in ("end of", "close of") else "plain", qualifier)])
    for prefix in ("end of", "close of", "start of", "beginning of", "mid")
    for qualifier in QUALIFIERS
    for period in ("week", "month", "quarter", "year")
]


@pytest.mark.gate
@pytest.mark.parametrize(("prefix", "qualifier", "period", "expected"), PRECEDENCE_ROWS,
                         ids=[" ".join(filter(None, row[:3])) for row in PRECEDENCE_ROWS])
def test_the_cascade_picks_the_same_rule_for_every_prefix_the_period_patterns_accept(
        prefix, qualifier, period, expected, cite):
    """The cross product, asserted as a WIDTH CLASS rather than as dates.

    D3 was a negative lookbehind on rows 5 and 6 that blocked "of next" and not "of the next",
    while row 7's own pattern accepted the article — so one spelling of the same phrase resolved
    to three days and the other to a quarter. Enumerating articles inside a lookbehind is fragile
    by construction: it has to be re-derived every time the sibling pattern accepts one more
    prefix, and nothing fails when it is not. This table is the check that outlives that guard —
    every prefix crossed with every period, asserting how WIDE the answer is, so a rule claiming
    a phrase it was not meant to claim is a blow-out and not a rounding difference.

    Known gaps this table also pins, so they stay visible: no row reads "last", "coming" or
    "upcoming", so those phrases are UNRESOLVED rather than wrong.
    """
    phrase = " ".join(filter(None, (prefix, qualifier, period)))

    resolved = resolve_date(phrase, eval_time=EVAL, tz="UTC", evidence=cite(phrase))

    span = SPAN_DAYS[expected][period] if SPAN_DAYS[expected] else None
    if span is None:
        assert resolved.certainty is UNRESOLVED, phrase
        assert resolved.earliest is None and resolved.latest is None, phrase
    else:
        assert resolved.certainty is RANGE, phrase
        assert (resolved.latest.date() - resolved.earliest.date()).days + 1 == span, phrase


@pytest.mark.parametrize(("text", "winner", "earliest", "latest"), [
    # Pre-existing, and the precedent: rule 3 already outranks rule 5 whatever the word order.
    ("we'll talk next week, definitely by Friday", 3, end_of(2026, 1, 16), end_of(2026, 1, 16)),
    # The same doctrine one row further down, which is what moving row 7 ahead of rows 5 and 6
    # extends: the more specific reading wins even when the vaguer phrase is written first.
    ("we'll decide next week and sign end of month", 7, utc(2026, 1, 29), end_of(2026, 1, 31)),
])
def test_the_cascade_ranks_by_rule_and_not_by_where_the_phrase_sits_in_the_string(
        text, winner, earliest, latest, cite):
    """Precedence is by rule, not by position — stated here because moving row 7 up applies it.

    `as_written` is one phrase the extractor already isolated, so a string carrying two of them is
    outside the contract and the cascade has to pick something; picking the more specific rule is
    the same answer it has always given for "next week ... by Friday". Written down because the
    alternative (leftmost match across rules) is the reading somebody will assume from the code.
    """
    resolved = resolve_date(text, eval_time=EVAL, tz="UTC", evidence=cite(text))

    assert (resolved.earliest, resolved.latest) == (earliest, latest), f"row {winner}"


# --------------------------------------------------------------------------------------------
# The documented ambiguities: "next Friday", locale, and the past
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("said_on", "weekday", "expected"), [
    (utc(2026, 1, 14, 9), "Wednesday", end_of(2026, 1, 16)),   # two days out
    (utc(2026, 1, 17, 9), "Saturday", end_of(2026, 1, 23)),    # the coming Friday, six days out
    (utc(2026, 1, 16, 9), "Friday", end_of(2026, 1, 23)),      # said ON a Friday: a week out
])
def test_next_friday_takes_the_next_occurrence_strictly_after_the_eval_date(said_on, weekday,
                                                                           expected, cite):
    """ALG-09's stated answer to the "this week's or next?" ambiguity, on all three sides of it.

    Strictly after means the same-day reading is never taken, including on the Friday itself. The
    third row is the one that matters: it is where a "next occurrence >= eval_time" rule would
    quietly hand back a deadline that is already most of the way spent.
    """
    resolved = resolve_date("next Friday", eval_time=said_on, tz="UTC", evidence=cite("Friday"))

    assert resolved.certainty is EXACT
    assert resolved.latest == expected, f"said on a {weekday}"


@pytest.mark.parametrize(("locale", "certainty", "expected"), [
    (None, UNRESOLVED, None),          # two readings, nothing to pick with
    ("en", UNRESOLVED, None),          # a language is not a region; English writes both orders
    ("xx_ZZ", EXACT, end_of(2026, 4, 3)),   # a region we do not list is day-first, as most are
    ("en_US", EXACT, end_of(2026, 3, 4)),
    ("en_GB", EXACT, end_of(2026, 4, 3)),
    ("en-IN", EXACT, end_of(2026, 4, 3)),
    ("en_PH", EXACT, end_of(2026, 3, 4)),
])
def test_numeric_date_order_comes_from_the_locale_and_is_never_guessed(locale, certainty,
                                                                      expected, cite):
    """03/04/2026 is March 4th in Chicago and the 3rd of April in Chennai.

    This is the Globe Worked fault's shape: a locale separator/order bug that every layer above
    propagates faithfully. With no region to decide, the phrase comes back UNRESOLVED — a missing
    date a founder can be asked about, rather than a confident date a month out of place.
    """
    resolved = resolve_date("03/04/2026", eval_time=EVAL, tz="UTC", locale=locale,
                            evidence=cite("03/04/2026"))

    assert resolved.certainty is certainty
    assert resolved.latest == expected


def test_a_past_date_keeps_its_date_and_reports_itself_as_past(cite):
    """"The renewal was 9 January", said on the 14th, is a fact about a date that was missed.

    Rolling it to 2027 would erase the only interesting thing about it, so the window is returned
    as written and `date_in_past` — derived from the window and the eval instant, never stored —
    is what tells the caller.
    """
    resolved = resolve_date("January 9, 2026", eval_time=EVAL, tz="UTC",
                            evidence=cite("January 9, 2026"))

    assert resolved.latest == end_of(2026, 1, 9)
    assert resolved.date_in_past is True
    assert resolve_date("tomorrow", eval_time=EVAL, tz="UTC",
                        evidence=cite("tomorrow")).date_in_past is False


# --------------------------------------------------------------------------------------------
# Timezone: resolve in the org's zone, store UTC
# --------------------------------------------------------------------------------------------

def test_resolution_uses_the_org_calendar_day_not_the_utc_one(cite):
    """21:30 UTC on the 14th is already 03:00 on the 15th in Mumbai, so "today" is the 15th.

    A normalizer that resolved in UTC would answer the 14th and be a whole day early for every
    org east of the meridian — and the founder would see a deadline that expired last night.
    """
    late_evening = utc(2026, 1, 14, 21, 30)

    mumbai = resolve_date("today", eval_time=late_evening, tz="Asia/Kolkata",
                          evidence=cite("today"))
    london = resolve_date("today", eval_time=late_evening, tz="Europe/London",
                          evidence=cite("today"))

    assert mumbai.latest == utc(2026, 1, 15, 18, 29, 59)   # 23:59:59 IST on the 15th
    assert london.latest == utc(2026, 1, 14, 23, 59, 59)   # 23:59:59 GMT on the 14th
    assert mumbai.latest != london.latest


@pytest.mark.parametrize(("label", "eval_time", "phrase", "expected"), [
    # Spring forward: 8 March 2026, New York moves to UTC-4 at 02:00 local.
    ("the day before the gap", utc(2026, 3, 6, 12), "tomorrow", utc(2026, 3, 8, 4, 59, 59)),
    ("the gap day itself", utc(2026, 3, 7, 12), "tomorrow", utc(2026, 3, 9, 3, 59, 59)),
    # Fall back: 1 November 2026, New York returns to UTC-5 at 02:00 local.
    ("the day before the overlap", utc(2026, 10, 30, 12), "tomorrow",
     utc(2026, 11, 1, 3, 59, 59)),
    ("the overlap day itself", utc(2026, 10, 31, 12), "tomorrow", utc(2026, 11, 2, 4, 59, 59)),
])
def test_dst_boundaries_shift_the_stored_utc_instant_by_the_offset_in_force(label, eval_time,
                                                                           phrase, expected,
                                                                           cite):
    """End of day is a LOCAL instant, so its UTC value moves by an hour across a transition.

    Both directions are here because they fail differently: a normalizer that resolves in UTC and
    subtracts a fixed offset is an hour early after spring-forward and an hour late after
    fall-back, and an hour either side of midnight is a different calendar day.
    """
    resolved = resolve_date(phrase, eval_time=eval_time, tz="America/New_York",
                            evidence=cite(phrase))

    assert resolved.latest == expected, label


@pytest.mark.parametrize(("label", "eval_time", "earliest", "latest", "elapsed"), [
    # Spring forward: 8 March 2026, New York moves to UTC-4 at 02:00 local. Evaluated on Wed
    # 25 Feb, "next week" is Mon 2 - Sun 8 March, which CONTAINS the transition: its two bounds
    # are stored at two different UTC offsets and the window is an hour short of 168 hours while
    # still being seven local days.
    ("the week containing spring forward", utc(2026, 2, 25, 12),
     utc(2026, 3, 2, 5),                                   # Mon 2 Mar 00:00:00 EST (UTC-5)
     utc(2026, 3, 9, 3, 59, 59),                           # Sun 8 Mar 23:59:59 EDT (UTC-4)
     timedelta(days=7, hours=-1, seconds=-1)),
    # The week after is wholly on the far side, so BOTH bounds sit at UTC-4. A normalizer that
    # captured the offset in force at eval_time (still EST on 4 March) and reused it would open
    # this week an hour late, on the wrong side of local midnight.
    ("the week after spring forward", utc(2026, 3, 4, 12),
     utc(2026, 3, 9, 4),                                   # Mon 9 Mar 00:00:00 EDT (UTC-4)
     utc(2026, 3, 16, 3, 59, 59),                          # Sun 15 Mar 23:59:59 EDT (UTC-4)
     timedelta(days=7, seconds=-1)),
    # Fall back: 1 November 2026, New York returns to UTC-5 at 02:00 local. The mirror image —
    # seven local days spending an hour MORE than 168 hours of elapsed time.
    ("the week containing fall back", utc(2026, 10, 21, 12),
     utc(2026, 10, 26, 4),                                 # Mon 26 Oct 00:00:00 EDT (UTC-4)
     utc(2026, 11, 2, 4, 59, 59),                          # Sun 1 Nov 23:59:59 EST (UTC-5)
     timedelta(days=7, hours=1, seconds=-1)),
])
def test_a_week_range_is_seven_local_days_whatever_dst_does_to_elapsed_time(
        label, eval_time, earliest, latest, elapsed, cite):
    """"Next week" names the same seven local days whether or not a transition falls inside it.

    Doc 05 fixes the bounds ("resolve in the org's timezone, not UTC... store UTC") but is silent
    on a RANGE that straddles a transition, so this row pins the choice: each bound is converted
    from local wall clock independently, never derived as the other bound plus a fixed number of
    elapsed seconds. The elapsed assertion is the one that can tell those two implementations
    apart — an elapsed-seconds end would close the spring-forward week at 22:59:59 on Sunday
    local, dropping the last hour of its last day out of every proximity score computed from it,
    and would run the fall-back week an hour into Monday.

    The first and last rows are the ones that actually straddle; the middle row is the week
    immediately after spring forward, which catches the other half of the same bug — an offset
    read once at `eval_time` and reused for bounds that live on the far side of the transition.
    """
    resolved = resolve_date("next week", eval_time=eval_time, tz="America/New_York",
                            evidence=cite("next week"))

    assert resolved.earliest == earliest, label
    assert resolved.latest == latest, label
    assert resolved.latest - resolved.earliest == elapsed, label


def test_an_unknown_timezone_raises_rather_than_defaulting_to_utc(cite):
    """A silently-defaulted zone is an unanswered question that surfaces days later as a
    reminder on the wrong day; a raise is answered by whoever configured the connection."""
    with pytest.raises(Exception):
        resolve_date("tomorrow", eval_time=EVAL, tz="Mars/Olympus_Mons", evidence=cite("tomorrow"))

    with pytest.raises(ValueError):
        resolve_date("tomorrow", eval_time=EVAL, tz="  ", evidence=cite("tomorrow"))


# --------------------------------------------------------------------------------------------
# No clock, and therefore replayable
# --------------------------------------------------------------------------------------------

def test_the_same_phrase_resolves_differently_against_two_eval_times(cite):
    """The assertion that actually proves no clock is read.

    A module reading a clock would answer both calls identically no matter what was passed in.
    Two eval instants a month apart must produce two different windows, each carrying the instant
    it was resolved against.
    """
    january = resolve_date("next week", eval_time=EVAL, tz="UTC", evidence=cite("next week"))
    february = resolve_date("next week", eval_time=utc(2026, 2, 14, 9), tz="UTC",
                            evidence=cite("next week"))

    assert january.earliest == utc(2026, 1, 19)
    assert february.earliest == utc(2026, 2, 16)
    assert january.resolved_against == EVAL
    assert february.resolved_against == utc(2026, 2, 14, 9)
    assert january.earliest != february.earliest


def test_replaying_the_same_input_reproduces_a_byte_identical_object(cite):
    """Replay is the whole reason `resolved_against` exists: an audit row re-derived a year later
    must equal the row that was stored. Compared as serialised JSON rather than as objects,
    because that is the form the row is actually kept and re-read in."""
    first = resolve_date("end of Q3", eval_time=EVAL, tz="Asia/Kolkata",
                         evidence=cite("end of Q3"))
    second = resolve_date("end of Q3", eval_time=EVAL, tz="Asia/Kolkata",
                          evidence=cite("end of Q3"))

    assert first.model_dump_json() == second.model_dump_json()
    assert first == second


def test_a_resolved_date_still_requires_its_receipt(cite):
    """Universal rule 4. The normalizer does not get an exemption from evidence just because it
    is arithmetic: the phrase it converted was quoted from somewhere, and a window with no span
    behind it is a deadline nobody wrote."""
    with pytest.raises(ValidationError):
        resolve_date("next week", eval_time=EVAL, tz="UTC", evidence=[])

    with pytest.raises(ValueError):
        resolve_date("next week", eval_time=datetime(2026, 1, 14, 9), tz="UTC",
                     evidence=cite("next week"))


def test_two_phrasings_of_one_day_produce_overlapping_windows(cite):
    """ALG-12 compares windows, so "by Friday" and "16 January 2026" have to land on the same
    instant rather than merely the same day — otherwise the conflict detector reports a
    disagreement between two sources that agree."""
    weekday = resolve_date("by Friday", eval_time=EVAL, tz="UTC", evidence=cite("by Friday"))
    explicit = resolve_date("16 January 2026", eval_time=EVAL, tz="UTC",
                            evidence=cite("16 January 2026"))

    assert weekday.window == explicit.window
    assert weekday.overlaps(explicit)


# --------------------------------------------------------------------------------------------
# L1.5.2-U2 · duration and recurrence
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("phrase", "exact", "calendar_form"), [
    ("30 days notice", timedelta(days=30), CalendarDuration(days=30)),
    ("30-day notice period", timedelta(days=30), CalendarDuration(days=30)),
    ("ninety days", timedelta(days=90), CalendarDuration(days=90)),
    ("two weeks' notice", timedelta(days=14), CalendarDuration(days=14)),
    ("48 hours", timedelta(hours=48), CalendarDuration(seconds=172_800)),
    # A month has no length until it is anchored, so the timedelta form refuses and the calendar
    # form keeps the phrase's own units.
    ("3 months notice", None, CalendarDuration(months=3)),
    ("one year notice", None, CalendarDuration(months=12)),
    ("a quarter", None, CalendarDuration(months=3)),
    # Business days have no length at all without a holiday calendar — that is U3's job.
    ("5 business days", None, None),
    ("sometime next year", None, None),
    ("no duration here", None, None),
])
def test_duration_converts_only_when_the_conversion_is_lossless(phrase, exact, calendar_form):
    """`resolve_duration` returning a 90-day `timedelta` for "3 months" is exactly the invented
    precision this layer exists to stop: three months before 1 November is 1 August, which is 92
    days, and the two-day difference lands on the side nobody re-checks."""
    assert resolve_duration(phrase) == exact
    assert resolve_calendar_duration(phrase) == calendar_form


@pytest.mark.parametrize(("anchor", "duration", "expected"), [
    # 3 months notice before a 1 November renewal.
    (utc(2026, 11, 1, 9), CalendarDuration(months=3).negated(), utc(2026, 8, 1, 9)),
    # Day-of-month clamps rather than overflowing: 31 March minus a month is the 28th, not 3 Mar.
    (utc(2026, 3, 31, 9), CalendarDuration(months=-1), utc(2026, 2, 28, 9)),
    (utc(2026, 1, 14, 9), CalendarDuration(days=30), utc(2026, 2, 13, 9)),
    (utc(2026, 1, 14, 9), CalendarDuration(seconds=172_800), utc(2026, 1, 16, 9)),
])
def test_a_notice_period_applied_to_an_anchor_gives_the_date_to_act_on(anchor, duration,
                                                                      expected):
    """L1.5.2-U2's WHY, executed: a renewal date without its notice period gives the founder the
    wrong deadline, and the notice period only becomes a date against a real anchor."""
    assert add_calendar_duration(anchor, duration) == expected


def test_a_calendar_duration_crossing_dst_keeps_the_local_time_of_day():
    """Thirty local days from 10:00 on 1 March in New York is 10:00 on 31 March, not 09:00.
    Applying the days as elapsed seconds would shift the whole notice period by an hour."""
    start = utc(2026, 3, 1, 15)   # 10:00 EST
    assert add_calendar_duration(start, CalendarDuration(days=30),
                                 tz="America/New_York") == utc(2026, 3, 31, 14)  # 10:00 EDT


@pytest.mark.parametrize(("phrase", "rrule"), [
    ("annual", "FREQ=YEARLY;INTERVAL=1"),
    ("renews annually", "FREQ=YEARLY;INTERVAL=1"),
    ("per annum", "FREQ=YEARLY;INTERVAL=1"),
    ("every year", "FREQ=YEARLY;INTERVAL=1"),
    ("every quarter", "FREQ=MONTHLY;INTERVAL=3"),
    ("quarterly", "FREQ=MONTHLY;INTERVAL=3"),
    ("semi-annual", "FREQ=MONTHLY;INTERVAL=6"),
    ("billed monthly", "FREQ=MONTHLY;INTERVAL=1"),
    ("every 2 weeks", "FREQ=WEEKLY;INTERVAL=2"),
    ("every three months", "FREQ=MONTHLY;INTERVAL=3"),
    ("fortnightly", "FREQ=WEEKLY;INTERVAL=2"),
    ("daily", "FREQ=DAILY;INTERVAL=1"),
    # Genuinely ambiguous English — every two weeks, or twice a week? A cadence wrong by a factor
    # of four is worse than a cadence left open.
    ("biweekly", None),
    ("bi-weekly", None),
    ("next week", None),
    ("no cadence here", None),
])
def test_recurrence_phrases_become_rrule_bodies_or_nothing(phrase, rrule):
    """RRULE rather than a private enum, so a renewal cadence can go straight to a calendar or a
    scheduler without a translation table only this repository owns."""
    assert resolve_recurrence(phrase) == rrule


# --------------------------------------------------------------------------------------------
# L1.5.2-U3 · business-day arithmetic
# --------------------------------------------------------------------------------------------

NEW_YEAR = frozenset({date(2026, 1, 19)})       # a stand-in org holiday, a Monday

BUSINESS_DAY_ROWS = [
    # (label, start, n, holidays, expected)
    ("five from a Wednesday is seven calendar days", utc(2026, 1, 14, 10), 5, frozenset(),
     utc(2026, 1, 21, 10)),
    ("one from a Friday lands on Monday", utc(2026, 1, 16, 10), 1, frozenset(),
     utc(2026, 1, 19, 10)),
    ("one from a Saturday lands on Monday", utc(2026, 1, 17, 10), 1, frozenset(),
     utc(2026, 1, 19, 10)),
    ("a Monday holiday pushes it to Tuesday", utc(2026, 1, 16, 10), 1, NEW_YEAR,
     utc(2026, 1, 20, 10)),
    ("the holiday costs a day across the whole span", utc(2026, 1, 14, 10), 5, NEW_YEAR,
     utc(2026, 1, 22, 10)),
    ("zero does not roll a weekend date", utc(2026, 1, 17, 10), 0, frozenset(),
     utc(2026, 1, 17, 10)),
    ("negative counts backwards over the weekend", utc(2026, 1, 14, 10), -3, frozenset(),
     utc(2026, 1, 9, 10)),
    ("negative skips the holiday too", utc(2026, 1, 20, 10), -1, NEW_YEAR,
     utc(2026, 1, 16, 10)),
]


@pytest.mark.parametrize(("label", "start", "n", "holidays", "expected"), BUSINESS_DAY_ROWS,
                         ids=[row[0] for row in BUSINESS_DAY_ROWS])
def test_business_days_skip_weekends_and_the_injected_holidays(label, start, n, holidays,
                                                               expected):
    """"Five business days" is seven calendar days at minimum and eight across one holiday.

    The zero row is the deliberate one: a zero-day offset returns the date it was given even on a
    Saturday, because rolling it would move a date the caller never asked to move — and a
    normalizer that silently rolls is indistinguishable from one that is off by a day.
    """
    assert add_business_days(start, n, holidays) == expected, label


def test_business_days_are_counted_in_the_org_timezone(cite):
    """09:00 Monday in Auckland is still Sunday in UTC. Counting in UTC would spend the step
    escaping a weekend the org is not in and land a whole working day late."""
    monday_morning_nz = utc(2026, 1, 18, 20)   # Mon 19 Jan 09:00 NZDT

    assert add_business_days(monday_morning_nz, 1, tz="Pacific/Auckland") == utc(2026, 1, 19, 20)
    assert add_business_days(monday_morning_nz, 1, tz="UTC") == utc(2026, 1, 19, 20)
    # Same instant, but in UTC it is a Sunday: the UTC count spends its step reaching Monday,
    # the Auckland count spends it reaching Tuesday.
    assert add_business_days(monday_morning_nz, 1, tz="Pacific/Auckland").astimezone(
        dates_module.ZoneInfo("Pacific/Auckland")).date() == date(2026, 1, 20)


def test_business_days_keep_the_local_time_of_day_across_dst():
    """A 10:00 deadline three business days out is still 10:00 after the clocks change. Counting
    in elapsed seconds would deliver it at 09:00, which is the kind of drift that only shows up
    on the one day a year it matters."""
    start = utc(2026, 3, 5, 15)   # Thu 5 Mar, 10:00 EST
    assert add_business_days(start, 3, tz="America/New_York") == utc(2026, 3, 10, 14)  # 10:00 EDT


def test_the_cascade_routes_business_day_phrases_through_the_holiday_calendar(cite):
    """Row 8's business-day branch is not a separate code path a caller has to remember: "in 5
    business days" resolves through the same holiday set the org supplies to `resolve_date`."""
    without = resolve_date("in 5 business days", eval_time=EVAL, tz="UTC",
                           evidence=cite("in 5 business days"))
    with_holiday = resolve_date("in 5 business days", eval_time=EVAL, tz="UTC",
                                holidays=NEW_YEAR, evidence=cite("in 5 business days"))

    assert without.latest == end_of(2026, 1, 21)
    assert with_holiday.latest == end_of(2026, 1, 22)


def test_a_non_integer_business_day_count_raises():
    """`True` satisfies an `int` annotation and would advance one day. A count that arrived as a
    bool is a caller bug, and a silent one-day shift is the worst way to learn about it."""
    with pytest.raises(TypeError):
        add_business_days(EVAL, True)


# --------------------------------------------------------------------------------------------
# The purity law — properties of the module, checked on its AST
# --------------------------------------------------------------------------------------------

#: Everything ALG-09 is allowed to reach. Anything else — a database session, an HTTP client, a
#: model client — makes this a non-replayable extractor wearing a validator's name.
ALLOWED_IMPORT_ROOTS = frozenset({
    "__future__", "calendar", "re", "collections", "dataclasses", "datetime", "zoneinfo",
    "genios_engine",
})

CLOCK_CALLS = frozenset({"now", "utcnow", "today", "fromtimestamp"})


def module_tree() -> ast.Module:
    return ast.parse(Path(dates_module.__file__).read_text(encoding="utf-8"))


@pytest.mark.gate
def test_the_module_never_reads_a_clock():
    """G1's first grep, made structural: no call to any wall-clock constructor anywhere.

    A clock read here makes replay impossible and makes last March's "next week" resolve against
    this morning — the one failure `resolved_against` exists to prevent, and the one a passing
    unit test would never notice because it would agree with itself.
    """
    offenders = [
        node.func.attr for node in ast.walk(module_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in CLOCK_CALLS
    ]

    assert offenders == []


@pytest.mark.gate
def test_the_module_contains_no_float_value_or_conversion():
    """G1's second grep. Binary fractions have no honest use in date arithmetic, and one that
    creeps in stops the result being reproducible on another machine."""
    tree = module_tree()
    literals = [node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, float)]
    conversions = [node.func.id for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "float"]
    divisions = [node for node in ast.walk(tree)
                 if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)]

    assert literals == []
    assert conversions == []
    assert divisions == [], "true division yields a float; the module uses // throughout"


@pytest.mark.gate
def test_the_module_imports_nothing_outside_the_pure_allowlist():
    """G1's third grep, generalised: no model client, and no database or network client either.

    Grepping for one vendor's name only catches that vendor. An allowlist catches the next one
    too, which matters because the failure it prevents — a validator that cannot run offline or
    twice — is the same whichever library introduces it.
    """
    roots = set()
    for node in ast.walk(module_tree()):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])

    assert roots <= ALLOWED_IMPORT_ROOTS, f"unexpected imports: {sorted(roots - ALLOWED_IMPORT_ROOTS)}"


@pytest.mark.gate
def test_resolve_date_refuses_to_default_its_eval_time():
    """The parameter must stay required. A default — of any kind — is where a clock read gets
    reintroduced by a caller who "just wanted it to work", and the whole replay guarantee then
    depends on every call site remembering."""
    import inspect

    parameter = inspect.signature(resolve_date).parameters["eval_time"]

    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
