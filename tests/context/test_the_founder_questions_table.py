"""STEP-13 · the one question a file asks you is kept: asked, then answered by you or retired, never lost.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_the_founder_questions_table.py

`migrations/0201_founder_questions.sql` (tree `yc2_w27_s13` M36.C2.L-contract.V0.U01; STEP-13 §3.6, `06` D60,
`03` F184). A file whose review's move lost its ground — or whose review must find out first — asks the founder
ONE question: the file, the review that asks it (its fingerprint and the audited run that ended insufficient),
the question, why it matters, when it was asked; then answered (the words, by whom, when) or retired (why).
One open question per file. Not `evidence_needs`: a question to the founder is answered by the founder, and
the needs executor closes for good a need no source can fetch. The state vocabulary is closed in the schema,
an answer and a retirement each carry what makes them one, `/reset` erases the table, the tenant's deletion
cascades, and the migration is additive (`tests/platform/test_the_code_can_always_be_rolled_back.py`).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from genios_engine.api import account_routes

pytestmark = pytest.mark.pg

ORG = "fq0201_org"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fq0201@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _ask(c, qid="fq_1", file="node_altavia", **over):
    row = {"o": ORG, "q": qid, "f": file, "fp": "ffp-1", "run": "run_1",
           "question": "Is it so: “Marco asked for a short deck”? It is not in what it cites.",
           "why": "misquoted (fact 1)", "at": AT, "state": "open", "answer": None, "by": None,
           "answered_at": None, "retired_at": None, "retired_why": None}
    row.update(over)
    c.execute(text(
        "insert into founder_questions (org_id, question_id, file_id, fingerprint, run_id, question, why, "
        "asked_at, state, answer, answered_by, answered_at, retired_at, retired_why) values (:o, :q, :f, :fp, "
        ":run, :question, :why, :at, :state, :answer, :by, :answered_at, :retired_at, :retired_why)"), row)


def test_the_table_holds_what_a_question_is(engine):
    with engine.connect() as c:
        cols = {r[0] for r in c.execute(text(
            "select column_name from information_schema.columns where table_name = 'founder_questions'"))}
    assert cols == {"org_id", "question_id", "file_id", "fingerprint", "run_id", "question", "why",
                    "asked_at", "state", "answer", "answered_by", "answered_at", "retired_at", "retired_why"}


def test_a_question_asked_answered_and_retired(engine):
    with engine.begin() as c:
        _ask(c)
        _ask(c, qid="fq_2", file="node_kitepath", state="answered", answer="Yes — he asked on 11 Aug.",
             by="user_arjun", answered_at=AT)
        _ask(c, qid="fq_3", file="node_bluepeak", state="retired", retired_at=AT,
             retired_why="the next review no longer asks it")
        states = dict(c.execute(text("select question_id, state from founder_questions where org_id = :o"),
                                {"o": ORG}).all())
    assert states == {"fq_1": "open", "fq_2": "answered", "fq_3": "retired"}


@pytest.mark.parametrize("over", [
    {"state": "pending"},                                             # the vocabulary is closed
    {"question": "  "}, {"why": ""},                                  # a question says what and why
    {"state": "answered"},                                            # an answer has its words, who, when
    {"state": "answered", "answer": "yes", "by": "user_arjun"},
    {"answer": "yes", "by": "user_arjun", "answered_at": AT},         # words on an open question
    {"answer": "yes"}, {"answered_at": AT},                           # …or any part of an answer
    {"state": "retired", "retired_at": AT},                           # a retirement says why
    {"retired_at": AT, "retired_why": "moved on"},                    # …and only a retired one has one
    {"retired_why": "moved on"},
])
def test_the_schema_refuses_a_question_that_is_not_one(engine, over):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _ask(c, **over)


def test_a_file_has_one_open_question(engine):
    with engine.begin() as c:
        _ask(c, qid="fq_1")
        _ask(c, qid="fq_old", state="retired", retired_at=AT, retired_why="a newer question replaced it")
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _ask(c, qid="fq_2")


def test_deleting_the_tenant_cascades_and_reset_erases_it(engine):
    assert "founder_questions" in account_routes._ORG_SCOPED_TABLES
    with engine.begin() as c:
        _ask(c)
        _ask(c, qid="fq_2", file="node_kitepath")
        wiped = account_routes._wipe(c, ORG)
        left = c.execute(text("select count(*) from founder_questions where org_id = :o"), {"o": ORG}).scalar()
    assert wiped["founder_questions"] == 2 and left == 0
    with engine.begin() as c:
        _ask(c, qid="fq_3")
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        assert c.execute(text("select count(*) from founder_questions where org_id = :o"),
                         {"o": ORG}).scalar() == 0
