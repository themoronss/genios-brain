"""STEP-15 · every open question your files ask you, in one read — oldest first, each with the card that asks it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_every_open_question_is_listed.py

`context/your_desk.open_questions` (tree `yc2_w27_s15` M44.C2.L-data.V0.U02; `03` s15-F13). A file's open question was
read one file at a time (`context/founder_questions.open_question`); the brief lists every one (`06` D60: beside the
card that asks it — STEP-13's question card, whose Answer is where the brief's line leads). Open only, asked by the
instant asked about; the card is the open one on the signal the asking run raised for that file.

The read lives beside your desk (`context/your_desk`), not in `context/founder_questions` — that module is the
STEP-16 builder's this step (the lead, 12 Oct); it reads the same table and writes nothing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import your_desk as D

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s15_questions", "org_s15_questions_other"
NOW = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)


@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the questions are read from Postgres")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    with engine.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"), {"o": org, "e": f"{org}@x.test"})
    yield engine
    with engine.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _question(engine, qid, file, *, run, asked, state="open", org=ORG):
    with engine.begin() as c:
        c.execute(text(
            "insert into founder_questions (org_id, question_id, file_id, fingerprint, run_id, question, why, asked_at, "
            "state, answer, answered_by, answered_at, retired_at, retired_why) values (:o, :q, :f, 'fp', :r, :question, "
            "'why', :at, :s, :a, :by, :aat, :rat, :rwhy)"),
            {"o": org, "q": qid, "f": file, "r": run, "question": f"Is {file} so?", "at": asked, "s": state,
             "a": "yes" if state == "answered" else None, "by": "seat" if state == "answered" else None,
             "aat": asked if state == "answered" else None, "rat": asked if state == "retired" else None,
             "rwhy": "replaced" if state == "retired" else None})


def _read(engine, now=NOW):
    with engine.connect() as c:
        return D.open_questions(c, ORG, now=now)


def test_every_open_question_oldest_first(pg):
    _question(pg, "q_new", "node_b", run="run_b", asked=NOW - timedelta(days=2))
    _question(pg, "q_old", "node_a", run="run_a", asked=NOW - timedelta(days=10))
    got = _read(pg)
    assert [(q.question_id, q.file_id, q.card_id, q.run_id) for q in got] == [
        ("q_old", "node_a", None, "run_a"), ("q_new", "node_b", None, "run_b")]
    assert got[0].question == "Is node_a so?" and got[0].asked_at == NOW - timedelta(days=10)


def test_the_card_that_asks_it_on_a_golden_tenant(pg):
    """F54 as the real chain leaves it (replayed from its cassette, no spend): two files each ask you a question,
    each on its own open question card (STEP-13's), raised by the run that asked it."""
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    case = next(c for c in load_cases() if c.case_id == "F54")
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    try:
        with engine.connect() as c:
            got = D.open_questions(c, run.org_id, now=case.sweeps[-1])
            cards = dict(c.execute(text(
                "select s.subject_node_id, k.card_id from cards k join signals s on s.org_id = k.org_id "
                "and s.signal_id = k.signal_id where k.org_id = :o and s.output_lane = 'investigation' "
                "and k.state = 'queued'"), {"o": run.org_id}).all())
        assert len(got) == 2 and [q.asked_at for q in got] == sorted(q.asked_at for q in got)
        assert {q.file_id: q.card_id for q in got} == cards and all(q.card_id for q in got)
        # Cards that are NOT a question's — each sorts before the real one, so a looser read would take it: a
        # decision card on the file from the asking run (0a), and the other file's question card moved onto this
        # file (0c): on this file from another run, and that run's card on another file. ⛔ Restated on the 16 Oct merge
        # with STEP-14 (0220, one open card per file): a decoy cannot be a second open card OF the file, so each is a
        # card that is no file's (`file_id` null — the legacy and compiled lanes' cards), which is what the reader's
        # join on signals must still tell apart from the question's.
        a, b = got
        with engine.begin() as c:
            def clone(card, signal_from, *, file=None, lane=None):
                c.execute(text(
                    "insert into signals select (jsonb_populate_record(s, jsonb_build_object("
                    "'signal_id', cast(:sid as text), 'rule_id', cast(:sid as text), "
                    "'subject_node_id', coalesce(cast(:file as text), s.subject_node_id), "
                    "'output_lane', coalesce(cast(:lane as text), s.output_lane)))).* from signals s "
                    "where s.org_id = :o and s.signal_id = (select signal_id from cards where org_id = :o "
                    "and card_id = :from)"),
                    {"sid": f"sig_{card}", "file": file, "lane": lane, "o": run_org, "from": signal_from})
                c.execute(text(
                    "insert into cards select (jsonb_populate_record(k, jsonb_build_object('card_id', "
                    "cast(:card as text), 'signal_id', cast(:sid as text), 'file_id', null))).* from cards k "
                    "where k.org_id = :o and k.card_id = :from"),
                    {"card": card, "sid": f"sig_{card}", "o": run_org, "from": signal_from})
            run_org = run.org_id
            clone("card_0a", a.card_id, lane="decision")
            clone("card_0c", b.card_id, file=a.file_id)
        with engine.connect() as c:
            again = D.open_questions(c, run.org_id, now=case.sweeps[-1])
        assert {q.file_id: q.card_id for q in again} == cards
        with engine.begin() as c:                                      # a closed card asks nothing any more
            c.execute(text("update cards set state = 'expired' where org_id = :o"), {"o": run.org_id})
        with engine.connect() as c:
            assert [q.card_id for q in D.open_questions(c, run.org_id, now=case.sweeps[-1])] == [None, None]
    finally:
        engine_runner.remove_tenant(engine, run.org_id)


def test_only_open_questions_asked_by_the_instant_of_this_tenant(pg):
    _question(pg, "q_open", "node_a", run="r1", asked=NOW - timedelta(days=1))
    _question(pg, "q_retired", "node_b", run="r2", asked=NOW - timedelta(days=5), state="retired")
    _question(pg, "q_answered", "node_c", run="r3", asked=NOW - timedelta(days=5), state="answered")
    _question(pg, "q_later", "node_d", run="r4", asked=NOW + timedelta(hours=1))
    _question(pg, "q_theirs", "node_e", run="r5", asked=NOW - timedelta(days=1), org=OTHER)
    assert [q.question_id for q in _read(pg)] == ["q_open"]
    assert _read(pg, now=NOW - timedelta(days=2)) == ()
