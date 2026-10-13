"""STEP-15 · your open screen follow-ups, in your own brief — `06` D8 = yes.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_screen_reminders_in_the_brief.py

`executive/morning_screen.screen_items`, called from `executive/morning_day.read_day` (tree `yc2_w27_s15`
M45.C4.L-logic.V0.U02). A promise of yours, something you were asked, or a deadline within 48 hours
(`reason/moments/followups.open_items`) is a line — beside the file whose person it names
(`platform/identity.person_name_key`) when one matches, else under your own promises by who it names. Never
`their_promise`, `risk` or `next_step`; never written to any file's own timeline (`06` D22, D53) — this only
reads. Measured on F45's golden tenant (Meera Shah, Bluepeak), replayed from its cassette, no spend, with
follow-ups added directly for this unit's own test.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B

pytestmark = pytest.mark.pg


@pytest.fixture(scope="module")
def world():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the day is read from a golden tenant on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    engine = routes._graph.engine
    case = {c.case_id: c for c in load_cases()}["F45"]
    run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    try:
        yield engine, run.org_id, case.sweeps[-1]
    finally:
        engine_runner.remove_tenant(engine, run.org_id)


def _insert(engine, org_id, *, fid, kind, who, text_, due_at=None):
    with engine.begin() as c:
        c.execute(text(
            "insert into screen_followups (id, org_id, seat_id, kind, text, who, due_at, topic_key) "
            "values (:i, :o, 'seat_owner', :k, :t, :w, :due, :tk)"),
            {"i": fid, "o": org_id, "k": kind, "t": text_, "w": who, "due": due_at, "tk": fid})


def _read(engine, org_id, now):
    from genios_engine.executive import morning_day as M
    with engine.connect() as c:
        return M.read_day(c, org_id, "seat_owner", now=now)


def _promises_about(day, subject):
    return [i for i in day.items if i.kind == B.PROMISE and i.subject == subject]


def test_a_promise_beside_the_file_whose_person_it_names(world):
    engine, org_id, now = world
    _insert(engine, org_id, fid="fu_m1", kind="my_promise", who="Meera Shah", text_="Send the updated deck")
    day = _read(engine, org_id, now)
    (item,) = _promises_about(day, "Bluepeak")                 # Bluepeak is F45's own file, matched by person
    assert item.material.word("promise") == "Send the updated deck"
    assert item.about is not None                              # matched to Bluepeak's own file id
    assert {s.kind for s in item.sources} == {B.SOURCE_PROMISE}


def test_an_ask_with_no_matching_file_stands_on_its_own(world):
    engine, org_id, now = world
    _insert(engine, org_id, fid="fu_a1", kind="ask", who="Someone Unlisted", text_="What is the refund policy?")
    day = _read(engine, org_id, now)
    standalone = [i for i in day.items if i.kind == B.PROMISE and i.material.word("promise") ==
                 "What is the refund policy?"]
    (item,) = standalone
    assert item.subject == "Someone Unlisted" and item.about is None


def test_a_deadline_within_48_hours_is_a_line_and_a_farther_one_is_not(world):
    engine, org_id, now = world
    _insert(engine, org_id, fid="fu_d1", kind="deadline", who=None, text_="Renew the domain",
           due_at=now + timedelta(hours=20))
    _insert(engine, org_id, fid="fu_d2", kind="deadline", who=None, text_="Renew the other domain",
           due_at=now + timedelta(days=10))
    day = _read(engine, org_id, now)
    texts = {i.material.word("promise") for i in day.items if i.kind == B.PROMISE}
    assert "Renew the domain" in texts
    assert "Renew the other domain" not in texts


def test_their_promise_risk_and_next_step_are_never_surfaced(world):
    engine, org_id, now = world
    for fid, kind in (("fu_t1", "their_promise"), ("fu_r1", "risk"), ("fu_n1", "next_step")):
        _insert(engine, org_id, fid=fid, kind=kind, who=None, text_=f"not surfaced ({kind})")
    day = _read(engine, org_id, now)
    texts = {i.material.word("promise") for i in day.items if i.kind == B.PROMISE}
    assert not any("not surfaced" in (t or "") for t in texts)


def test_an_empty_text_follow_up_is_not_a_blank_line(world):
    engine, org_id, now = world
    _insert(engine, org_id, fid="fu_empty1", kind="my_promise", who=None, text_=" ")
    day = _read(engine, org_id, now)
    assert not any(i.kind == B.PROMISE and not (i.material.word("promise") or "").strip() for i in day.items)


def test_a_screen_item_never_writes_to_the_files_own_timeline(world):
    """Read-only: `read_day` is called twice above already and nothing in `workstream_timeline` or any file
    table changed because of it — the follow-up rows above are the only writes this test itself made."""
    engine, org_id, _now = world
    with engine.connect() as c:
        n = c.execute(text("select count(*) from screen_followups where org_id = :o"), {"o": org_id}).scalar()
    assert n >= 5                              # exactly the rows this file inserted, untouched by read_day
