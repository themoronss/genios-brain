"""STEP-13 · a file asks you one question at a time, and keeps your answer.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_a_file_asks_one_question.py

`context/founder_questions` (tree `yc2_w27_s13` M36.C2.L-data.V1.U02; STEP-13 §3.6, `06` D60). `ask` files a
file's question — the same question asked again is the one already open, never a second; a new question
retires the file's old one, saying why. `answer` keeps your words once. `retire` closes a question the
review no longer asks. A file's open question, and the answers it holds, are one read each. The question's
id is its content's (the file, the review, the words) — so asking mints no id another part of a run would
have minted (`03` F170's rule).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import founder_questions as Q

pytestmark = pytest.mark.pg

ORG = "fq_store_org"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
FILE = "node_altavia"
ASKED = "Is it so: “Marco asked for a short deck”? It is not in what it cites."


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fq@store.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _ask(c, question=ASKED, *, fingerprint="ffp-1", at=AT, file=FILE):
    return Q.ask(c, org_id=ORG, file_id=file, fingerprint=fingerprint, run_id="run_1", question=question,
                 why="misquoted (fact 1)", at=at)


def test_a_file_asks_its_question_and_it_is_open(engine):
    with engine.begin() as c:
        asked = _ask(c)
        assert Q.open_question(c, ORG, FILE) == asked
    assert (asked.state, asked.question, asked.why, asked.fingerprint, asked.run_id) == (
        Q.OPEN, ASKED, "misquoted (fact 1)", "ffp-1", "run_1")
    assert asked.question_id == Q.question_id_for(ORG, FILE, "ffp-1", ASKED)


def test_the_same_question_asked_again_is_the_one_already_open(engine):
    with engine.begin() as c:
        first = _ask(c)
        again = _ask(c, fingerprint="ffp-2", at=AT + timedelta(hours=6))
        count = c.execute(text("select count(*) from founder_questions where org_id = :o"), {"o": ORG}).scalar()
    assert again == first and count == 1


def test_a_new_question_retires_the_old_one_and_says_why(engine):
    with engine.begin() as c:
        first = _ask(c)
        second = _ask(c, "Whom should “Send the deck” go to? It is addressed to you.", fingerprint="ffp-2",
                      at=AT + timedelta(days=1))
        old = Q.by_id(c, ORG, first.question_id)
        assert Q.open_question(c, ORG, FILE) == second
    assert (old.state, old.retired_why, old.retired_at) == (Q.RETIRED, Q.REPLACED, AT + timedelta(days=1))


def test_your_answer_is_kept_once(engine):
    with engine.begin() as c:
        asked = _ask(c)
        answered = Q.answer(c, org_id=ORG, question_id=asked.question_id, words="Yes — on 11 Aug, by mail.",
                            by="user_arjun", at=AT + timedelta(hours=2))
        assert Q.open_question(c, ORG, FILE) is None
        assert Q.answers_for(c, ORG, FILE) == (answered,)
        with pytest.raises(ValueError, match="answered once"):
            Q.answer(c, org_id=ORG, question_id=asked.question_id, words="No.", by="user_arjun", at=AT)
    assert (answered.state, answered.answer, answered.answered_by) == (
        Q.ANSWERED, "Yes — on 11 Aug, by mail.", "user_arjun")


@pytest.mark.parametrize("words", ["", "   "])
def test_an_answer_says_something(engine, words):
    with engine.begin() as c:
        asked = _ask(c)
        with pytest.raises(ValueError, match="says nothing"):
            Q.answer(c, org_id=ORG, question_id=asked.question_id, words=words, by="user_arjun", at=AT)


def test_a_question_the_review_no_longer_asks_is_retired(engine):
    with engine.begin() as c:
        asked = _ask(c)
        assert Q.retire(c, org_id=ORG, file_id=FILE, why=Q.NO_LONGER_ASKED, at=AT + timedelta(days=1))
        assert not Q.retire(c, org_id=ORG, file_id=FILE, why=Q.NO_LONGER_ASKED, at=AT + timedelta(days=2))
        gone = Q.by_id(c, ORG, asked.question_id)
        assert Q.open_question(c, ORG, FILE) is None and Q.answers_for(c, ORG, FILE) == ()
    assert (gone.state, gone.retired_why) == (Q.RETIRED, Q.NO_LONGER_ASKED)


def test_answers_are_the_files_own_newest_first(engine):
    with engine.begin() as c:
        one = _ask(c, "First?", fingerprint="ffp-1")
        Q.answer(c, org_id=ORG, question_id=one.question_id, words="one", by="u", at=AT + timedelta(hours=1))
        two = _ask(c, "Second?", fingerprint="ffp-2", at=AT + timedelta(days=1))
        Q.answer(c, org_id=ORG, question_id=two.question_id, words="two", by="u", at=AT + timedelta(days=1, hours=1))
        other = _ask(c, "Elsewhere?", file="node_kitepath")
        Q.answer(c, org_id=ORG, question_id=other.question_id, words="not this file", by="u", at=AT)
        assert [a.answer for a in Q.answers_for(c, ORG, FILE)] == ["two", "one"]


def test_a_question_already_answered_is_not_asked_again(engine):
    """The same review asking what the founder already answered gets the answer, not a new question."""
    with engine.begin() as c:
        asked = _ask(c)
        Q.answer(c, org_id=ORG, question_id=asked.question_id, words="Yes.", by="u", at=AT + timedelta(hours=1))
        again = _ask(c, at=AT + timedelta(hours=6))
        assert Q.open_question(c, ORG, FILE) is None
    assert (again.question_id, again.state, again.answer) == (asked.question_id, Q.ANSWERED, "Yes.")


def test_a_later_review_asking_the_same_words_is_its_own_question(engine):
    """Its id is the review's and the words' — so the record of what each review asked stays whole."""
    with engine.begin() as c:
        first = _ask(c)
        Q.retire(c, org_id=ORG, file_id=FILE, why=Q.NO_LONGER_ASKED, at=AT + timedelta(days=1))
        later = _ask(c, fingerprint="ffp-9", at=AT + timedelta(days=3))
        assert Q.by_id(c, ORG, first.question_id).state == Q.RETIRED
    assert later.question_id != first.question_id and later.state == Q.OPEN
