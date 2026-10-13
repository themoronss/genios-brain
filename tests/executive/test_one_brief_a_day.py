"""STEP-15 · one brief a day — composed, kept, and composed once per seat when its 08:00 has passed in the org's timezone.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_one_brief_a_day.py

`executive/morning` (tree `yc2_w27_s15` M44.C4.L-integration.V1.U02; `06` D9: the engine composes at 08:00 in your org's
timezone). `compose`: the seat's day, ordered, in the template's words, kept — a second compose of the same local day
reads the kept one. `compose_due`: for each org's account owner whose brief is due — the local time past 08:00 and none
kept for that local day — compose once; a seat that fails is counted, never raised past.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning as MB
from genios_engine.executive import morning_store

pytestmark = pytest.mark.pg

ORGS = ("org_s15_compose_ist", "org_s15_compose_ny", "org_s15_compose_noseat", "org_s15_compose_bad")
OUTSIDE = "org_s15_compose_outside"                       # due, and not among the orgs asked
#: 02:31 UTC is 08:01 in Kolkata (and 22:31 the day before in New York).
AT = datetime(2026, 10, 6, 2, 31, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the brief is composed on Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    zones = {"org_s15_compose_ist": "Asia/Kolkata", "org_s15_compose_ny": "America/New_York",
             "org_s15_compose_noseat": "Asia/Kolkata", "org_s15_compose_bad": "Asia/Kolkata"}
    zones[OUTSIDE] = "Asia/Kolkata"
    with eng.begin() as c:
        for org in (*ORGS, OUTSIDE):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', :e, :tz)"),
                      {"o": org, "e": f"{org}@example.test", "tz": zones[org]})
            if org != "org_s15_compose_noseat":
                from genios_engine.platform.seats import ensure_owner_seat
                ensure_owner_seat(c, org)
        c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) values (:o, 'seat_member', "
                       "'member@example.test', 'member', true)"), {"o": "org_s15_compose_ist"})
    yield eng
    with eng.begin() as c:
        for org in (*ORGS, OUTSIDE):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def test_an_empty_day_composes_a_brief_that_says_nothing_needs_you(engine):
    brief, wrote = MB.compose(engine, "org_s15_compose_ist", "seat_owner", now=AT)
    assert wrote is True and brief.one_line == "Nothing needs you today." and brief.lines == ()
    assert (brief.local_date, brief.timezone, brief.written_by) == (date(2026, 10, 6), "Asia/Kolkata", B.TEMPLATE_BRIEF)
    again, wrote = MB.compose(engine, "org_s15_compose_ist", "seat_owner", now=AT + timedelta(hours=3))
    assert wrote is False and again == brief                               # one brief a day: the kept one


@pytest.mark.parametrize("now, tz, kept, due", [
    (datetime(2026, 10, 6, 2, 29, tzinfo=timezone.utc), "Asia/Kolkata", False, False),   # 07:59 IST
    (datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc), "Asia/Kolkata", False, True),    # 08:00 IST
    (datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc), "Asia/Kolkata", True, False),    # already kept
    (datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc), "America/New_York", False, True),  # 22:30 the day before
    (datetime(2026, 10, 6, 11, 59, tzinfo=timezone.utc), "America/New_York", False, False),  # 07:59 EDT
    (datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc), "America/New_York", False, True),  # 08:00 EDT
])
def test_a_brief_is_due_past_eight_in_the_orgs_timezone_and_not_kept(now, tz, kept, due):
    assert MB.is_due(now, tz, kept=kept) is due


def test_compose_due_composes_each_owner_once_when_their_hour_has_passed(engine, monkeypatch):
    real = MB.read_day

    def failing(conn, org_id, seat_id, *, now):
        if org_id == "org_s15_compose_bad":
            raise RuntimeError("an unreadable day")
        return real(conn, org_id, seat_id, now=now)
    monkeypatch.setattr(MB, "read_day", failing)
    first = MB.compose_due(engine, now=AT, orgs=ORGS)
    # Kolkata's 6 Oct is due (08:01); New York's 5 Oct still is (22:31, none kept); the failing seat is counted.
    assert first == {"due": 3, "composed": 2, "kept_already": 0, "not_yet": 0, "failed": 1}
    with engine.connect() as c:
        assert morning_store.read(c, "org_s15_compose_ist", "seat_owner", date(2026, 10, 6)) is not None
        assert morning_store.read(c, "org_s15_compose_bad", "seat_owner", date(2026, 10, 6)) is None
        n = c.execute(text("select org_id, local_date::text from morning_briefs where org_id = any(:o) "
                           "order by org_id"), {"o": list(ORGS)}).all()
    assert [tuple(r) for r in n] == [("org_s15_compose_ist", "2026-10-06"), ("org_s15_compose_ny", "2026-10-05")]
    second = MB.compose_due(engine, now=AT + timedelta(minutes=15), orgs=ORGS)
    assert second["composed"] == 0 and second["kept_already"] == 2 and second["failed"] == 1
    later = MB.compose_due(engine, now=datetime(2026, 10, 6, 12, 5, tzinfo=timezone.utc), orgs=["org_s15_compose_ny"])
    assert later["composed"] == 1                                          # New York's 08:00, on a later tick


def test_a_kept_day_is_never_read_again_in_its_own_timezone(engine, monkeypatch):
    first, wrote = MB.compose(engine, "org_s15_compose_ny", "seat_owner", now=AT)       # 22:31 on 5 Oct, New York
    assert wrote and first.local_date == date(2026, 10, 5)

    def unread(*_a, **_k):
        raise AssertionError("the day of a kept brief was read again")
    monkeypatch.setattr(MB, "read_day", unread)
    again, wrote = MB.compose(engine, "org_s15_compose_ny", "seat_owner", now=AT + timedelta(minutes=30))
    assert wrote is False and again == first


def test_only_the_account_owner_and_only_the_orgs_asked(engine):
    MB.compose_due(engine, now=AT, orgs=ORGS)
    with engine.connect() as c:
        rows = c.execute(text("select org_id, seat_id from morning_briefs where org_id = any(:o) order by 1, 2"),
                         {"o": [*ORGS, OUTSIDE]}).all()
    assert ("org_s15_compose_ist", "seat_member") not in [tuple(r) for r in rows]
    assert OUTSIDE not in {r.org_id for r in rows}


def test_a_composer_beaten_to_the_day_counts_it_kept(engine, monkeypatch):
    monkeypatch.setattr(MB, "compose", lambda *_a, **_k: (None, False))
    counts = MB.compose_due(engine, now=AT, orgs=["org_s15_compose_ist"])
    assert counts["kept_already"] == 1 and counts["composed"] == 0


def test_compose_reads_the_day_of_a_golden_tenant():
    """F45, replayed from its cassette (no spend): the brief composed after its last sweep is the day in code's
    words — its decision with your reply time, and the change since the day before."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the golden tenant is replayed on Postgres")
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    case = next(c for c in load_cases() if c.case_id == "F45")
    engine_runner.pin_scratch_database()
    from genios_engine.api import routes
    eng = routes._graph.engine
    run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    try:
        brief, wrote = MB.compose(eng, run.org_id, "seat_owner", now=case.sweeps[-1])
        assert wrote and brief.one_line == "1 thing needs you."
        (today,) = brief.section(B.TODAY)
        assert today.words.startswith("Bluepeak: Introduce Meera Shah") and "(n=6)" in today.words
        assert [l.section for l in brief.lines] == [B.TODAY, B.CHANGED]
    finally:
        engine_runner.remove_tenant(eng, run.org_id)
