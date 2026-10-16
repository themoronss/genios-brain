"""STEP-15 · the day, ordered by code from the expert's own judgment — today's five, and every section after it.

    .venv/bin/python -m pytest -q tests/executive/test_the_day_is_ordered.py

`executive/morning_order` (tree `yc2_w27_s15` M44.C3.L-logic.V0.U01; STEP-15 §8.4 item 2, s15-D1, s15-D4). Always in
today: a meeting today in the org's timezone, a dated deadline or promise within 48 hours (overdue included) — the
five flexes for them, and says by how much. Then the open decisions in the book re-rank's order (a decision with no
card after every carded one, by its appraisal), then the questions, oldest first. Stuck: a decision whose move is
yours quiet past 14 days. Watching: a waiting file quiet past 7 days (F39, F40, F43 out). Each section capped, the cut
counted; the word budget kept by cutting from the back, never an always-in item.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_order as O

pytestmark = pytest.mark.unit

TZ = "Asia/Kolkata"
NOW = datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc)          # 08:00 IST


def _item(kind, about, **over):
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about, subject=about,
                  material=B.Material(words=(("headline", about),)), sources=(B.Source(B.SOURCE_REVIEW, about),),
                  **over)


def _ids(items):
    return [i.about for i in items]


def test_a_meeting_today_and_a_deadline_within_48_hours_are_always_in():
    decisions = [_item(B.DECISION, f"d{n}", book_score_bp=9000 - n) for n in range(5)]
    items = decisions + [
        _item(B.MEETING, "insight", at=NOW + timedelta(hours=7)),
        _item(B.PROMISE, "deck", at=NOW + timedelta(hours=30)),
        _item(B.PROMISE, "late", at=NOW - timedelta(days=2)),
        _item(B.PROMISE, "later", at=NOW + timedelta(days=3)),
        _item(B.MEETING, "tomorrow", at=datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc)),  # 01:30 IST, 7 Oct
    ]
    day = O.order(items, now=NOW, tz=TZ)
    assert _ids(day.items(B.TODAY)) == ["late", "insight", "deck", "d0", "d1"]
    assert day.flexed == 0 and day.always == frozenset(i.item_id for i in items if i.about in
                                                       ("late", "insight", "deck"))
    assert _ids(day.items(B.PROMISES)) == ["later"] and _ids(day.items(B.MEETINGS)) == ["tomorrow"]
    assert dict(day.cut)[B.TODAY] == 3                             # d2, d3, d4: neither seated nor stuck


def test_the_five_flexes_for_what_is_always_in_and_says_so():
    items = [_item(B.PROMISE, f"p{n}", at=NOW + timedelta(hours=n)) for n in range(7)]
    items.append(_item(B.DECISION, "d", book_score_bp=9999))
    day = O.order(items, now=NOW, tz=TZ)
    assert _ids(day.items(B.TODAY)) == [f"p{n}" for n in range(7)] and day.flexed == 2
    assert dict(day.cut)[B.TODAY] == 1


def test_decisions_by_the_book_rank_then_by_appraisal_then_the_questions_oldest_first():
    items = [
        _item(B.QUESTION, "q_new", at=NOW - timedelta(days=1)),
        _item(B.QUESTION, "q_old", at=NOW - timedelta(days=9)),
        _item(B.DECISION, "uncarded_low", stakes="low", urgency="high"),
        _item(B.DECISION, "carded_low", book_score_bp=6000),
        _item(B.DECISION, "uncarded_high", stakes="high", urgency="low"),
        _item(B.DECISION, "carded_high", book_score_bp=9900),
    ]
    day = O.order(items, now=NOW, tz=TZ)
    assert _ids(day.items(B.TODAY)) == ["carded_high", "carded_low", "uncarded_high", "uncarded_low", "q_old"]
    assert _ids(day.items(B.ASKED)) == ["q_new"]


def test_a_carded_decision_the_re_rank_scored_down_to_zero_still_comes_before_an_uncarded_one():
    items = [_item(B.DECISION, "uncarded", stakes="high", urgency="high"),
             _item(B.DECISION, "carded_zero", book_score_bp=0, stakes="low", urgency="low")]
    assert _ids(O.order(items, now=NOW, tz=TZ).items(B.TODAY)) == ["carded_zero", "uncarded"]


def test_a_tie_on_level_goes_to_the_quieter_file_then_the_id():
    items = [_item(B.DECISION, "b", stakes="high", urgency="high", quiet_days=3.0),
             _item(B.DECISION, "a", stakes="high", urgency="high", quiet_days=3.0),
             _item(B.DECISION, "c", stakes="high", urgency="high", quiet_days=9.0),
             _item(B.DECISION, "m", stakes="high", urgency="medium", quiet_days=40.0)]
    assert _ids(O.order(items, now=NOW, tz=TZ).items(B.TODAY))[:3] == ["c", *sorted(["a", "b"], key=lambda x:
                                                                                     B.item_id_for(B.DECISION, x))]


def test_stuck_is_your_move_quiet_past_two_weeks_and_not_already_today():
    top = [_item(B.DECISION, f"top{n}", book_score_bp=9000 - n) for n in range(5)]
    items = top + [
        _item(B.DECISION, "stuck", book_score_bp=100, our_move=True, quiet_days=20.0),
        _item(B.DECISION, "theirs", book_score_bp=90, our_move=False, quiet_days=20.0),
        _item(B.DECISION, "recent", book_score_bp=80, our_move=True, quiet_days=14.0),
    ]
    day = O.order(items, now=NOW, tz=TZ)
    assert _ids(day.items(B.STUCK)) == ["stuck"] and dict(day.cut)[B.TODAY] == 2


def test_watching_is_quiet_past_the_first_rung_the_quietest_first_and_capped():
    items = [_item(B.WATCHED, "f14", quiet_days=25.1), _item(B.WATCHED, "f08a", quiet_days=14.2),
             _item(B.WATCHED, "f08b", quiet_days=16.2), _item(B.WATCHED, "f39", quiet_days=2.2),
             _item(B.WATCHED, "f43", quiet_days=0.3), _item(B.WATCHED, "edge", quiet_days=7.0),
             _item(B.WATCHED, "old", quiet_days=60.0), _item(B.WATCHED, "unknown")]
    day = O.order(items, now=NOW, tz=TZ)
    assert _ids(day.items(B.WATCHING)) == ["old", "f14", "f08b"]
    assert dict(day.cut)[B.WATCHING] == 1                          # f08a: past the cap of three


def test_the_other_sections_and_their_order():
    items = [_item(B.CHANGE, "c_old", at=NOW - timedelta(days=1)), _item(B.CHANGE, "c_new", at=NOW - timedelta(hours=2)),
             _item(B.DESK, "desk"), _item(B.NO_FOLLOW_UP, "mixer", at=NOW - timedelta(days=8)),
             _item(B.MEETING, "thu", at=NOW + timedelta(days=1, hours=3))]
    day = O.order(items, now=NOW, tz=TZ)
    assert [name for name, _ in day.sections] == list(B.SECTIONS)
    assert _ids(day.items(B.CHANGED)) == ["c_new", "c_old"] and _ids(day.items(B.YOUR_DESK)) == ["desk"]
    assert _ids(day.items(B.MEETINGS)) == ["mixer", "thu"] and day.cut == ()
    assert day.items("nowhere") == ()


def test_every_capped_section_counts_what_it_cut():
    items = [_item(B.CHANGE, f"c{n}", at=NOW - timedelta(hours=n)) for n in range(7)]
    items += [_item(B.QUESTION, f"q{n}", at=NOW - timedelta(days=n)) for n in range(10)]
    day = O.order(items, now=NOW, tz=TZ)
    assert len(day.items(B.CHANGED)) == B.CAPS[B.CHANGED] and dict(day.cut)[B.CHANGED] == 2
    assert len(day.items(B.ASKED)) == B.CAPS[B.ASKED] and dict(day.cut)[B.ASKED] == 2


def test_the_budget_cuts_from_the_back_and_never_an_always_in_item():
    items = [_item(B.PROMISE, "due", at=NOW + timedelta(hours=5)), _item(B.DECISION, "d", book_score_bp=9000),
             _item(B.WATCHED, "w1", quiet_days=30.0), _item(B.WATCHED, "w2", quiet_days=20.0)]
    day = O.order(items, now=NOW, tz=TZ)
    fitted = O.fit(day, lambda _section, _item: 100, budget=250)
    assert _ids(fitted.items(B.TODAY)) == ["due", "d"] and _ids(fitted.items(B.WATCHING)) == []
    assert dict(fitted.cut) == {B.WATCHING: 2}
    tight = O.fit(day, lambda _section, _item: 100, budget=50)
    assert _ids(tight.items(B.TODAY)) == ["due"] and dict(tight.cut) == {B.TODAY: 1, B.WATCHING: 2}
    assert O.fit(day, lambda _s, _i: 1, budget=600) == day
