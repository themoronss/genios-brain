"""ALG-09 · L1.5.2-U2/U3 wired — a duration, a cadence and a run of business days, ON THE PATH.

**WHY THIS FILE EXISTS.** `resolve_duration`, `add_calendar_duration`, `resolve_recurrence` and
`add_business_days` were built, tested and never CALLED: a grep for each name across
`genios_engine/` found nothing but their own definitions, their own docstrings and `__all__`.
Half of ALG-09 was therefore a library, not a normalizer — a commitment that said "every two
weeks", "for 3 months", "30 days notice" or "3 working days" left the extractor as an UNRESOLVED
date carrying no window at all, which ALG-17's deadline-proximity term reads as *no deadline*.
The notice period doc 05 L1.5.2-U2 exists to protect ("a renewal date without its notice period
gives the founder the wrong deadline") was computed by nothing.

So every assertion here goes through `extractor.extract` — the one production caller of
`resolve_date` — with a fake model standing in for the words. A test that called
`resolve_duration` directly would prove the unit and leave the hole, which is the sixth time
that has happened in this build.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from genios_engine.capture.semantic import extractor as ex
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.units import DateCertainty

RANGE = DateCertainty.RANGE
UNRESOLVED = DateCertainty.UNRESOLVED

PREPARED_ID = "evt_alg09_durations"

#: One line, one occurrence of each phrase, so `text.index` is a receipt rather than a guess.
TEXT = (
    "Rohit, we will send a written status update every two weeks until the migration closes. "
    "The pilot runs for 3 months from signature, the cancellation clause needs 30 days notice, "
    "and our turnaround on a countersignature is 3 working days."
)

#: The four phrases and the window each one names, resolved against the suite's frozen Wednesday
#: (2026-01-14 09:00 UTC). Every `latest` is derived from a unit that had no caller:
#:   "every two weeks"  -> resolve_recurrence -> FREQ=WEEKLY;INTERVAL=2 -> add_calendar_duration
#:   "for 3 months"     -> resolve_calendar_duration (months stay months) -> add_calendar_duration
#:   "30 days notice"   -> resolve_duration (lossless, so a timedelta)
#:   "3 working days"   -> add_business_days (Wed -> Thu, Fri, MON, never Saturday)
PHRASES: list[tuple[str, datetime]] = [
    ("every two weeks", datetime(2026, 1, 28, 9, 0, tzinfo=timezone.utc)),
    ("for 3 months", datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc)),
    ("30 days notice", datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)),
    ("3 working days", datetime(2026, 1, 19, 9, 0, tzinfo=timezone.utc)),
]


def _cite(quote: str) -> list[dict[str, Any]]:
    """A model-shaped citation with the offsets FOUND, never hand-counted."""
    start = TEXT.index(quote)
    assert TEXT.find(quote, start + 1) < 0, f"{quote!r} appears twice — the span would be ambiguous"
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


@pytest.fixture
def prepared() -> PreparedContent:
    return PreparedContent(prepared_content_id=PREPARED_ID, event_id=PREPARED_ID,
                           clean_text=TEXT, language="en")


@pytest.fixture
def request_for(prepared: PreparedContent, eval_time: datetime):
    def _build(**overrides: Any) -> ex.ExtractionRequest:
        kwargs: dict[str, Any] = dict(
            org_id="org_alg09", event_id=PREPARED_ID, source="gmail", profile_id="email",
            tier="T2", prepared=prepared,
            envelope=ex.EventEnvelope(direction="inbound", sender="priya@acme.example",
                                      recipients=("rohit@vendor.example",),
                                      thread_position=1, thread_depth=1, subject="Pilot terms"),
            eval_time=eval_time, timezone="UTC", locale="en_US")
        kwargs.update(overrides)
        return ex.ExtractionRequest(**kwargs)
    return _build


@pytest.fixture
def payload() -> dict[str, Any]:
    """What a correct model returns for this message: the phrases, and no windows.

    The model is asked for `as_written` and nothing else about a date — `_resolved_date` reads
    and DISCARDS any window a model offers — so a payload that carried one would be testing the
    fake instead of the cascade.
    """
    return {
        "intent": "commit",
        "stance": "neutral",
        "dates_mentioned": [{"as_written": phrase, "evidence": _cite(phrase)}
                            for phrase, _ in PHRASES],
        "commitments": [
            {"actor": "we", "action": "send a written status update", "is_conditional": False,
             "due": {"as_written": "every two weeks", "evidence": _cite("every two weeks")},
             "evidence": _cite("we will send a written status update"),
             "confidence_bp": 8600},
        ],
    }


@pytest.fixture
def extraction(request_for, payload, fake_llm):
    """One real extraction. `store=None` so nothing is cached between tests in this file."""
    outcome = ex.extract(request_for(), llm=fake_llm(payload), store=None,
                         nonce="deadbeefcafe0009")
    assert outcome.result is not None, outcome.diagnostics
    return outcome.result


def _by_phrase(extraction) -> dict[str, Any]:
    return {resolved.as_written: resolved for resolved in extraction.dates_mentioned}


@pytest.mark.parametrize(("phrase", "latest"), PHRASES, ids=[p for p, _ in PHRASES])
def test_a_duration_phrase_leaves_the_extractor_carrying_the_window_it_names(
        phrase, latest, extraction, eval_time):
    """THE WIRING ASSERTION. Each phrase names a span of time; before ALG-09's duration,
    recurrence and business-day units were reachable from `resolve_date`, all four came back
    UNRESOLVED with `earliest is None` — a deadline that disappeared without anyone choosing to
    drop it."""
    resolved = _by_phrase(extraction)[phrase]

    assert resolved.certainty is RANGE, f"{phrase!r} still resolves to nothing"
    assert resolved.earliest == eval_time, "a stated span runs from the instant it was stated"
    assert resolved.latest == latest
    assert resolved.resolved_against == eval_time


def test_a_recurring_commitment_carries_its_own_next_window(extraction, eval_time):
    """L1.5.2-U2's WHY at the seam that matters: the commitment's `due`, not just a date in a
    list. "Every two weeks" is a promise with a next occurrence, and a `Commitment` whose `due`
    is UNRESOLVED is tracked as an open loop that is never once escalated."""
    commitment = extraction.commitments[0]

    assert commitment.due is not None and commitment.due.as_written == "every two weeks"
    assert commitment.due.certainty is RANGE
    assert commitment.due.window == (eval_time,
                                     datetime(2026, 1, 28, 9, 0, tzinfo=timezone.utc))


def test_business_days_skip_the_weekend_the_org_actually_has(extraction):
    """U3's whole point: three working days from a Wednesday is FIVE calendar days, because
    Saturday and Sunday are not working days. A calendar-day reading would land on Saturday the
    17th and every compliance deadline computed from it would be two days early."""
    resolved = _by_phrase(extraction)["3 working days"]

    assert resolved.latest.date().isoformat() == "2026-01-19", "Monday, not Saturday"
    assert (resolved.latest - resolved.earliest).days == 5, "3 business days spans 5 calendar days"


def test_a_phrase_that_names_no_span_is_still_unresolved(request_for, fake_llm, eval_time):
    """The wiring must not turn the cascade into a machine that always answers. "in a few weeks"
    carries no count, so it stays row 11 — an honest "somebody wrote a date-ish thing and we will
    not guess which day"."""
    text = "We will circle back in a few weeks."
    prepared = PreparedContent(prepared_content_id="evt_vague", event_id="evt_vague",
                               clean_text=text, language="en")
    payload = {"intent": "inform", "stance": "neutral",
               "dates_mentioned": [{"as_written": "in a few weeks",
                                    "evidence": [{"quote": "in a few weeks",
                                                  "start_offset": text.index("in a few weeks"),
                                                  "end_offset": text.index("in a few weeks") + 14}]}]}

    outcome = ex.extract(request_for(prepared=prepared, event_id="evt_vague"),
                         llm=fake_llm(payload), store=None, nonce="deadbeefcafe000a")

    resolved = outcome.result.dates_mentioned[0]
    assert resolved.certainty is UNRESOLVED
    assert resolved.earliest is None and resolved.latest is None


# ── a cadence that schedules something, against one that describes a noun ─────────────
@pytest.fixture
def resolve_through_extractor(request_for, fake_llm):
    """One phrase, resolved through `extract` — the real caller — inside a sentence that
    contains it. Every row below is a full extraction rather than a direct `resolve_date` call,
    for the reason this whole file exists."""
    def _resolve(sentence: str, phrase: str):
        start = sentence.index(phrase)
        prepared = PreparedContent(prepared_content_id="evt_cadence", event_id="evt_cadence",
                                   clean_text=sentence, language="en")
        payload = {"intent": "inform", "stance": "neutral",
                   "dates_mentioned": [{"as_written": phrase,
                                        "evidence": [{"quote": phrase, "start_offset": start,
                                                      "end_offset": start + len(phrase)}]}]}
        outcome = ex.extract(request_for(prepared=prepared, event_id="evt_cadence"),
                             llm=fake_llm(payload), store=None, nonce="deadbeefcafe000b")
        assert outcome.result is not None, outcome.diagnostics
        return outcome.result.dates_mentioned[0]
    return _resolve


#: sentence, phrase, certainty, latest — the line between a phrase that SCHEDULES something and
#: one that merely describes a noun. Both sides are cadences `resolve_recurrence` reads
#: correctly; only one of them names a date, and row 12 is where that second question is asked.
CADENCE_ROWS = [
    ("We review the numbers quarterly.", "quarterly", RANGE,
     datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc)),
    ("You are billed monthly in arrears.", "billed monthly", RANGE,
     datetime(2026, 2, 14, 9, 0, tzinfo=timezone.utc)),
    # A noun's adjective. "Our annual contract" is the agreement we are already inside — it says
    # nothing is going to happen, and a year-wide window on it would be invented urgency.
    ("Confirming our annual contract renewal terms.", "annual contract", UNRESOLVED, None),
    ("The fee is $84K per annum.", "per annum", UNRESOLVED, None),
    # Genuinely ambiguous English — every two weeks, or twice a week? `resolve_recurrence`
    # refuses it, and a row that fell through to a guess would undo that refusal.
    ("We will meet biweekly from now on.", "biweekly", UNRESOLVED, None),
    # Precedence, documented: a named weekday is a DAY, and row 3 claims it long before row 12.
    ("We sync every Friday without fail.", "every Friday", DateCertainty.EXACT,
     datetime(2026, 1, 16, 23, 59, 59, tzinfo=timezone.utc)),
]


@pytest.mark.parametrize(("sentence", "phrase", "certainty", "latest"), CADENCE_ROWS,
                         ids=[row[1] for row in CADENCE_ROWS])
def test_a_cadence_is_a_date_only_when_it_schedules_something(
        sentence, phrase, certainty, latest, resolve_through_extractor):
    resolved = resolve_through_extractor(sentence, phrase)

    assert resolved.certainty is certainty, phrase
    assert resolved.latest == latest, phrase
