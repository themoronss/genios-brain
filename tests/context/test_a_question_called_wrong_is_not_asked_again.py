"""STEP-16 · a question you call wrong is retired, and never asked again in its words.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q \
        tests/context/test_a_question_called_wrong_is_not_asked_again.py

Tree `yc2_w27_s16` M46.C3.L-data.V0.U05 (`context/founder_questions`; S16-D10, `s16-F13`). *"Don't ask me
this"* is the most useful thing you can say about a question. `retire` takes a closed why for it,
`CALLED_WRONG`; and `ask` does not file again, on the same file, a question in the words of one you called
wrong — it returns that retired question, so its caller counts the file held with no card. Only an answer
or your *wrong* closes the words: a question retired for any other reason may be asked again. The scope is
the file: the same words on another file are that file's to ask.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import founder_questions as Q

pytestmark = pytest.mark.pg

ORG = "fq_called_wrong_org"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
FILE = "node_saka"
ASKED = "Is saka.vc a fund you are raising from? Its mail names no partner."
OTHER = "Whom at saka.vc should the deck go to?"


def test_the_closed_whys_are_four_and_called_wrong_is_one():
    assert Q.RETIRED_WHYS == (Q.REPLACED, Q.NO_LONGER_ASKED, Q.LEFT_COVERAGE, Q.CALLED_WRONG)
    assert len(set(Q.RETIRED_WHYS)) == 4 and "wrong" in Q.CALLED_WRONG


class _Unreachable:
    def execute(self, *_a, **_k):                                    # pragma: no cover - the point
        raise AssertionError("a retirement with no closed why reached the database")


def test_a_retirement_says_one_of_the_closed_whys():
    with pytest.raises(ValueError):
        Q.retire(_Unreachable(), org_id=ORG, file_id=FILE, why="because", at=AT)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fq@wrong.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _ask(c, question=ASKED, *, fingerprint="ffp-1", at=AT, file=FILE):
    return Q.ask(c, org_id=ORG, file_id=file, fingerprint=fingerprint, run_id="run_1", question=question,
                 why="the file names no partner", at=at)


def _rows(c, file=FILE):
    return c.execute(text("select question, state, retired_why from founder_questions where org_id = :o "
                          "and file_id = :f order by asked_at, question_id"), {"o": ORG, "f": file}).all()


def _called_wrong(c):
    asked = _ask(c)
    assert Q.retire(c, org_id=ORG, file_id=FILE, why=Q.CALLED_WRONG, at=AT + timedelta(hours=1))
    return asked


@pytest.mark.pg
def test_calling_a_question_wrong_retires_it_saying_so(engine):
    with engine.begin() as c:
        asked = _called_wrong(c)
        kept = Q.by_id(c, ORG, asked.question_id)
        assert Q.open_question(c, ORG, FILE) is None
    assert (kept.state, kept.retired_why, kept.retired_at) == (Q.RETIRED, Q.CALLED_WRONG, AT + timedelta(hours=1))


@pytest.mark.pg
def test_the_words_you_called_wrong_are_not_asked_again_whatever_review_asks_them(engine):
    with engine.begin() as c:
        asked = _called_wrong(c)
        again = _ask(c, fingerprint="ffp-2", at=AT + timedelta(days=1))
        rows = _rows(c)
        assert Q.open_question(c, ORG, FILE) is None
    assert again.question_id == asked.question_id
    assert (again.state, again.retired_why) == (Q.RETIRED, Q.CALLED_WRONG)
    assert rows == [(ASKED, Q.RETIRED, Q.CALLED_WRONG)], "no second row, nothing open"


@pytest.mark.pg
def test_an_open_question_the_review_no_longer_asks_retires_when_it_asks_words_you_called_wrong(engine):
    with engine.begin() as c:
        asked = _called_wrong(c)
        other = _ask(c, OTHER, fingerprint="ffp-2", at=AT + timedelta(hours=2))
        again = _ask(c, fingerprint="ffp-3", at=AT + timedelta(hours=3))
        assert Q.open_question(c, ORG, FILE) is None
        retired_other = Q.by_id(c, ORG, other.question_id)
    assert again.question_id == asked.question_id and again.retired_why == Q.CALLED_WRONG
    assert (retired_other.state, retired_other.retired_why) == (Q.RETIRED, Q.NO_LONGER_ASKED)


@pytest.mark.pg
@pytest.mark.parametrize("why", [Q.NO_LONGER_ASKED, Q.REPLACED, Q.LEFT_COVERAGE])
def test_a_question_retired_for_any_other_reason_may_be_asked_again(engine, why):
    """The negative control: only an answer or your wrong closes the words."""
    with engine.begin() as c:
        _ask(c)
        Q.retire(c, org_id=ORG, file_id=FILE, why=why, at=AT + timedelta(hours=1))
        again = _ask(c, fingerprint="ffp-2", at=AT + timedelta(days=1))
    assert again.state == Q.OPEN and again.question == ASKED


@pytest.mark.pg
def test_other_words_on_the_file_are_asked(engine):
    with engine.begin() as c:
        _called_wrong(c)
        other = _ask(c, OTHER, fingerprint="ffp-2", at=AT + timedelta(days=1))
    assert other.state == Q.OPEN and other.question == OTHER


@pytest.mark.pg
def test_the_same_words_on_another_file_are_that_files_to_ask(engine):
    with engine.begin() as c:
        _called_wrong(c)
        elsewhere = _ask(c, file="node_other_fund", at=AT + timedelta(days=1))
    assert elsewhere.state == Q.OPEN and elsewhere.question == ASKED
