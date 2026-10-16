"""STEP-15 · the brief is kept once per seat per local day — a second composer reads the first's — and your mark on a
line is kept, the latest standing.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_the_brief_is_kept_once_a_day.py

`executive/morning_store` (tree `yc2_w27_s15` M44.C4.L-data.V0.U01) over `0230_morning_briefs`. Two composers of one
seat's day write one row: the second is handed the first's brief, equal to what was kept. A day's brief, and the
seat's last brief before a day, read back as kept. A mark is one per line per person: useful, or not useful with your
words; a later mark replaces an earlier one, never the reverse; the line names its brief.
"""
from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning_store as S

pytestmark = pytest.mark.pg

ORG = "org_s15_store"
AT = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)
DAY = date(2026, 9, 30)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'store@example.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _brief(seat="seat_owner", day=DAY, words="Bluepeak: introduce Meera Shah to the two pilot leads.", about="node_b"):
    item = B.Item(item_id=B.item_id_for(B.DECISION, about), kind=B.DECISION, about=about, subject="Meera Shah",
                  material=B.Material(words=(("headline", words),),
                                      numbers=(B.Number(name="your_reply_time", says="usually 1.5 days (n=6, person)",
                                                        value=1.5, n=6, calculator="c"),)),
                  sources=(B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), stakes="high", urgency="high", at=AT)
    line = B.Line(line_id=B.line_id_for(ORG, seat, day, B.TODAY, item.item_id), item_id=item.item_id,
                  section=B.TODAY, words=words, kind=item.kind, subject=item.subject, sources=item.sources)
    return B.Brief(org_id=ORG, seat_id=seat, local_date=day, timezone="Asia/Kolkata", as_of=AT,
                   one_line="1 thing needs you.", lines=(line,), items=(item,), written_by=B.TEMPLATE_BRIEF,
                   why="the template", model=None, tier=None, cost_micro_usd=0, cut=((B.WATCHING, 2),),
                   material_digest=B.digest_of((item,)))


def test_a_brief_is_kept_once_and_the_second_composer_reads_the_first(engine):
    first = _brief()
    with engine.begin() as c:
        kept, wrote = S.keep(c, first)
    assert wrote is True and kept == first
    second = _brief(words="Bluepeak: something else entirely.")
    with engine.begin() as c:
        kept, wrote = S.keep(c, second)
    assert wrote is False and kept == first
    with engine.connect() as c:
        row = c.execute(text("select one_line, written_by, cost_micro_usd, material_digest, lines -> 0 ->> 'words' "
                             "as words, timezone from morning_briefs where org_id = :o"), {"o": ORG}).one()
    assert tuple(row) == ("1 thing needs you.", "template", 0, first.material_digest, first.lines[0].words,
                          "Asia/Kolkata")


def test_a_days_brief_and_the_last_before_a_day_read_back_as_kept(engine):
    older, last, other = _brief(day=DAY - timedelta(days=3)), _brief(day=DAY - timedelta(days=1)), _brief(seat="seat_two")
    with engine.begin() as c:
        for brief in (older, last, other, _brief()):
            S.keep(c, brief)
    with engine.connect() as c:
        assert S.read(c, ORG, "seat_owner", DAY) == _brief()
        assert S.read(c, ORG, "seat_two", DAY) == other                # one seat's day is never another's
        assert S.read(c, ORG, "seat_owner", DAY + timedelta(days=1)) is None
        assert S.last_before(c, ORG, "seat_owner", DAY) == last
        assert S.last_before(c, ORG, "seat_owner", DAY - timedelta(days=1)) == older
        assert S.last_before(c, ORG, "seat_owner", DAY - timedelta(days=3)) is None
        assert S.last_before(c, ORG, "seat_two", DAY + timedelta(days=1)) == other


def test_a_mark_is_kept_per_line_per_person_the_latest_standing(engine):
    brief = _brief()
    line = brief.lines[0].line_id
    with engine.begin() as c:
        S.keep(c, brief)
        first = S.mark_line(c, org_id=ORG, line_id=line, marked_by="seat_owner", mark=S.USEFUL, words=None, at=AT)
        S.mark_line(c, org_id=ORG, line_id=line, marked_by="seat_two", mark=S.NOT_USEFUL, words=" I  sent it ", at=AT)
    assert (first.mark, first.seat_id, first.local_date) == (S.USEFUL, "seat_owner", DAY)
    with engine.begin() as c:
        later = S.mark_line(c, org_id=ORG, line_id=line, marked_by="seat_owner", mark=S.NOT_USEFUL,
                       words="already done", at=AT + timedelta(hours=1))
        stale = S.mark_line(c, org_id=ORG, line_id=line, marked_by="seat_owner", mark=S.USEFUL, words=None,
                       at=AT - timedelta(hours=1))
    assert (later.mark, later.words) == (S.NOT_USEFUL, "already done")
    assert (stale.mark, stale.words, stale.marked_at) == (S.NOT_USEFUL, "already done", AT + timedelta(hours=1))
    with engine.connect() as c:
        marks = S.marks_for(c, ORG, "seat_owner", DAY)
    assert [(m.marked_by, m.mark, m.words) for m in marks[line]] == [
        ("seat_owner", S.NOT_USEFUL, "already done"), ("seat_two", S.NOT_USEFUL, "I sent it")]


@pytest.mark.parametrize("mark, words, error", [
    ("meh", None, ValueError), (S.NOT_USEFUL, "  ", ValueError), (S.USEFUL, "nice", ValueError),
])
def test_a_mark_that_is_not_one_is_refused(engine, mark, words, error):
    brief = _brief()
    with engine.begin() as c:
        S.keep(c, brief)
        with pytest.raises(error):
            S.mark_line(c, org_id=ORG, line_id=brief.lines[0].line_id, marked_by="seat_owner", mark=mark, words=words,
                   at=AT)


def test_a_line_no_kept_brief_holds_takes_no_mark(engine):
    with engine.begin() as c:
        S.keep(c, _brief())
        with pytest.raises(LookupError):
            S.mark_line(c, org_id=ORG, line_id="bl_nowhere", marked_by="seat_owner", mark=S.USEFUL, words=None, at=AT)
