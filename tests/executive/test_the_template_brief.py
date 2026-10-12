"""STEP-15 · the template brief — code's own words for every line, from its item's material only.

    .venv/bin/python -m pytest -q tests/executive/test_the_template_brief.py

`executive/morning_template` (tree `yc2_w27_s15` M44.C3.L-logic.V1.U03). What you read when no model writes: each line
from its item's material — the checked headline, the wait rule where it held, the question, the numbers with their n,
local dates — you as "you", a file by its counterparty's name, never an address, no quote. The one line says how many
things need you, a meeting today, who waits on you — and *"Nothing needs you today."* only when nothing is open, asked,
due or watched (`03` s15-F2).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_template as T

pytestmark = pytest.mark.unit

TZ = "Asia/Kolkata"
NOW = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)
LOCAL = date(2026, 9, 30)


def _item(kind, about, *, words=(), numbers=(), dates=(), names=(), **over):
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about, subject=over.pop("subject", None),
                  material=B.Material(words=words, numbers=numbers, dates=dates, names=names),
                  sources=(B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), **over)


def _n(name, value, n, says=None, unit="days"):
    return B.Number(name=name, says=says or f"{n} {unit}", value=value, n=n, calculator="c", unit=unit)


DECISION = _item(B.DECISION, "node_bluepeak", subject="Bluepeak",
                 words=(("name", "Bluepeak"), ("headline", "Introduce Meera Shah to the two pilot leads"),
                        ("reply_with", "Meera Shah")),
                 numbers=(_n("your_reply_time", 1.5, 6, "usually 1.5 days (n=6, person)"), _n("quiet", 15, 15)),
                 dates=(("by", "2026-10-02"),), book_score_bp=9900, stakes="high", urgency="high")
QUESTION = _item(B.QUESTION, "node_cell", subject="University Startup Cell",
                 words=(("name", "University Startup Cell"),
                        ("question", "Find out whether you count as a startup incubated on the campus")),
                 dates=(("by", "2026-09-30"), ("asked", "2026-09-07")), at=NOW - timedelta(days=23))
WATCHED = _item(B.WATCHED, "node_fjord", subject="Fjord Venture Partners",
                words=(("name", "Fjord Venture Partners"), ("headline", "A conditional deferral, wait for the milestone"),
                       ("wait_rule", "Stop the weekly updates to Tara and wait for a real milestone")),
                numbers=(_n("quiet", 25, 25),), quiet_days=25.1)
PROMISE = _item(B.PROMISE, "c_pilot", subject="Gaurav",
                words=(("promise", "send the pilot proposal"), ("to", "Gaurav"), ("file", "Stackfield")),
                dates=(("due", "2026-10-04"),), at=NOW + timedelta(days=4))
LATE = _item(B.PROMISE, "c_late", subject="Tara Bose", words=(("promise", "share the numbers"), ("to", "Tara Bose")),
             dates=(("due", "2026-09-28"),), at=NOW - timedelta(days=2))
MEETING = _item(B.MEETING, "m_insight", subject="Insight call",
                words=(("title", "Insight call"), ("when", "Wed 30 Sep, 14:30"),
                       ("prep", "Neel Shah (Partner) · last touch 3 d ago; Still open: the pre-read")),
                names=("Neel Shah",), at=NOW + timedelta(hours=6))
MIXER = _item(B.NO_FOLLOW_UP, "m_mixer", subject="Fintech founders mixer - Bluebay",
              words=(("title", "Fintech founders mixer - Bluebay"), ("when", "20 Aug")), names=("Kavya", "Rhea"),
              at=NOW - timedelta(days=41))
DESK = _item(B.DESK, None, words=(("waiting:f1", "Dev Malhotra"), ("waiting:f2", "Rhea Thomas")),
             numbers=(_n("waiting", 2, 2, "2 people", "people"), _n("waiting:f1", 26, 26), _n("waiting:f2", 22, 22),
                      _n("since_your_last_mail", 28, 28)), names=("Dev Malhotra", "Rhea Thomas"))
WROTE = _item(B.CHANGE, "node_ssm:wrote", subject="State Startup Mission",
              words=(("name", "State Startup Mission"),
                     ("what", "State Startup Mission wrote; their move, quiet 18 days — past the 5 days they usually take")),
              at=NOW - timedelta(hours=3))
CHANGE = _item(B.CHANGE, "node_ssm:change", subject="State Startup Mission",
               words=(("name", "State Startup Mission"), ("what", "wrote")), at=NOW - timedelta(hours=3))


@pytest.mark.parametrize("item, section, said", [
    (DECISION, B.TODAY, "Bluepeak: Introduce Meera Shah to the two pilot leads. By 2 Oct. "
                        "You usually answer Meera Shah in 1.5 days (n=6)."),
    (DECISION, B.STUCK, "Bluepeak: Introduce Meera Shah to the two pilot leads. By 2 Oct. "
                        "You usually answer Meera Shah in 1.5 days (n=6). Quiet for 15 days."),
    (QUESTION, B.ASKED, "University Startup Cell: Find out whether you count as a startup incubated on the campus. "
                        "By 30 Sep."),
    (WATCHED, B.WATCHING, "Fjord Venture Partners: A conditional deferral, wait for the milestone. Stop the weekly "
                          "updates to Tara and wait for a real milestone. Quiet for 25 days."),
    (PROMISE, B.PROMISES, "You promised Gaurav: send the pilot proposal (Stackfield) — due 4 Oct."),
    (LATE, B.TODAY, "You promised Tara Bose: share the numbers — was due 28 Sep."),
    (MEETING, B.TODAY, "Wed 30 Sep, 14:30: Insight call with Neel Shah. Neel Shah (Partner) · last touch 3 d ago; "
                       "Still open: the pre-read."),
    (MIXER, B.MEETINGS, "Fintech founders mixer - Bluebay, 20 Aug: no follow-up from you to anyone you met there — "
                        "Kavya, Rhea."),
    (DESK, B.YOUR_DESK, "You have sent nothing for 28 days while 2 people wait on you: Dev Malhotra (26 days), "
                        "Rhea Thomas (22 days)."),
    (CHANGE, B.CHANGED, "State Startup Mission: wrote."),
    (WROTE, B.CHANGED, "State Startup Mission wrote; their move, quiet 18 days — past the 5 days they usually take."),
])
def test_every_kind_in_code_s_words_from_its_material(item, section, said):
    assert T.words_for(item, section, local_date=LOCAL) == said


def test_the_words_of_an_edge_case_in_each_kind():
    asked = _item(B.QUESTION, "q", words=(("name", "Cell"), ("question", "Are you incubated there?")))
    assert T.words_for(asked, B.ASKED) == "Cell: Are you incubated there?"               # no second full stop
    nameless = _item(B.DECISION, "d", words=(("name", "Bluepeak"), ("headline", "Write to Meera")),
                     numbers=(_n("your_reply_time", 1.5, 6),))
    assert T.words_for(nameless, B.TODAY) == "Bluepeak: Write to Meera."                 # a time with nobody to say
    same = _item(B.PROMISE, "p", words=(("promise", "send the deck"), ("to", "Gaurav"), ("file", "Gaurav")),
                 dates=(("due", "2026-10-04"),))
    assert T.words_for(same, B.PROMISES) == "You promised Gaurav: send the deck — due 4 Oct."
    unnamed = _item(B.DESK, None, numbers=(_n("waiting", 1, 1, "1 person", "people"), _n("waiting:f9", 4, 4)))
    assert T.words_for(unnamed, B.YOUR_DESK) == "1 person waits on you: someone (4 days)."


def test_what_changed_alone_is_no_thing_to_know():
    brief = T.template_brief(org_id="o", seat_id="s", now=NOW, tz=TZ, items=(WATCHED, CHANGE, WROTE))
    assert brief.one_line == "Nothing urgent today; 1 thing to know."


def test_a_desk_whose_silence_cannot_be_said_says_only_who_waits():
    one = _item(B.DESK, None, words=(("waiting:f1", "Dev Malhotra"),),
                numbers=(_n("waiting", 1, 1, "1 people", "people"), _n("waiting:f1", 26, 26)))
    assert T.words_for(one, B.YOUR_DESK) == "1 person waits on you: Dev Malhotra (26 days)."


def test_the_brief_reads_the_day_in_its_sections_with_every_line_sourced():
    brief = T.template_brief(org_id="org_a", seat_id="seat_owner", now=NOW, tz=TZ,
                             items=(CHANGE, WATCHED, MIXER, DESK, PROMISE, QUESTION, MEETING, DECISION))
    assert [l.section for l in brief.lines] == [B.TODAY, B.TODAY, B.TODAY, B.YOUR_DESK, B.CHANGED, B.PROMISES,
                                               B.MEETINGS, B.WATCHING]
    assert [l.item_id for l in brief.section(B.TODAY)] == [MEETING.item_id, DECISION.item_id, QUESTION.item_id]
    assert brief.one_line == "3 things need you; a meeting today: Insight call; 2 people waiting on you."
    for line in brief.lines:
        item = brief.item(line.item_id)
        assert line.sources == item.sources and line.subject == item.subject and line.kind == item.kind
        assert line.line_id == B.line_id_for("org_a", "seat_owner", LOCAL, line.section, item.item_id)
        assert line.by == B.TEMPLATE and line.verdict is None
        assert "@" not in line.words and "the founder" not in line.words.lower()
    assert (brief.written_by, brief.model, brief.cost_micro_usd, brief.why) == (B.TEMPLATE_BRIEF, None, 0, T.TEMPLATE_WHY)
    assert brief.local_date == LOCAL and brief.timezone == TZ and brief.as_of == NOW


@pytest.mark.parametrize("items, said", [
    ((), "Nothing needs you today."),
    ((CHANGE,), "Nothing needs you today."),                         # a change alone needs nothing of you
    ((WATCHED,), "Nothing urgent today; 1 thing to know."),           # watching is not nothing (s15-F2)
    ((WATCHED, MIXER), "Nothing urgent today; 2 things to know."),
    ((DECISION,), "1 thing needs you."),
])
def test_the_one_line_says_nothing_needs_you_only_when_nothing_does(items, said):
    assert T.template_brief(org_id="o", seat_id="s", now=NOW, tz=TZ, items=items).one_line == said


def test_the_brief_keeps_its_budget_and_counts_what_it_cut():
    long = "word " * 120
    many = [_item(B.WATCHED, f"w{n}", words=(("name", f"File {n}"), ("headline", long)), quiet_days=30.0 + n)
            for n in range(3)]
    many += [_item(B.QUESTION, f"q{n}", words=(("name", f"Q {n}"), ("question", long)), at=NOW - timedelta(days=n))
             for n in range(6)]
    brief = T.template_brief(org_id="o", seat_id="s", now=NOW, tz=TZ, items=many)
    assert brief.words <= B.WORD_BUDGET
    assert sum(n for _s, n in brief.cut) == len(many) - len(brief.lines) > 0


def test_a_flexed_today_is_kept_and_said():
    due = [_item(B.PROMISE, f"p{n}", words=(("promise", f"do {n}"), ("to", "Gaurav")), dates=(("due", "2026-09-30"),),
                 at=NOW + timedelta(hours=n)) for n in range(7)]
    brief = T.template_brief(org_id="o", seat_id="s", now=NOW, tz=TZ, items=due)
    assert len(brief.section(B.TODAY)) == 7 and brief.flexed == 2   # the five flexed by two, and says so
    assert brief.one_line == "7 things need you."
