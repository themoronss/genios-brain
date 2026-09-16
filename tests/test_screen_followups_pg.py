"""The screen lane's merged reads, against real Postgres.

`any_muted` and `taught_notes` each replaced two round trips with one, and both are hand-written
SQL — a lateral join, a `group by` inside it, and a dynamic `or` over the thread keys. Hermetic
tests cannot see a Postgres syntax or planner difference, and this lane runs on a session pooler
where every statement is a round trip a person is waiting on.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_scratch \\
        pytest tests/test_screen_followups_pg.py -q
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason.moments import followups as F

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

NOW = datetime.now(timezone.utc)
CAP = "moment.screen_insight"


@pytest.fixture(scope="module")
def engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture()
def seat(engine):
    org, seat_id = f"org_{uuid.uuid4().hex[:10]}", f"seat_{uuid.uuid4().hex[:10]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'Muted test')"), {"o": org})
    yield org, seat_id
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _verdict(c, org, seat_id, thread, muted_until):
    c.execute(text(
        "insert into screen_thread_verdicts (org_id, seat_id, thread_key, work, judged_at, "
        "muted_until) values (:o, :s, :t, true, :now, :m)"),
        {"o": org, "s": seat_id, "t": thread, "now": NOW, "m": muted_until})


def _note(c, org, seat_id, headline, action, at):
    mid = f"mom_{uuid.uuid4().hex[:12]}"
    c.execute(text(
        "insert into moments (moment_id, org_id, seat_id, origin, kind, priority, headline, "
        "capability_id, capability_version, display, created_at, expires_at) "
        "values (:m, :o, :s, 'server', 'advice', 'normal', :h, :cap, '4', true, :at, "
        ":at + interval '10 minutes')"),
        {"m": mid, "o": org, "s": seat_id, "h": headline, "cap": CAP, "at": at})
    c.execute(text(
        "insert into moment_feedback (moment_id, org_id, seat_id, capability_id, action, at) "
        "values (:m, :o, :s, :cap, :a, :at)"),
        {"m": mid, "o": org, "s": seat_id, "cap": CAP, "a": action, "at": at})


def test_one_statement_answers_both_of_a_screen_s_keys(engine, seat):
    org, seat_id = seat
    thread = "doc:com.google.Chrome:mail.google.com/mail/u/0#inbox/FMfc"
    site = "site:naukri.com"
    with engine.begin() as c:
        _verdict(c, org, seat_id, site, NOW + timedelta(days=3))          # the SITE is muted
        _verdict(c, org, seat_id, thread, NOW - timedelta(days=1))        # the thread's mute expired
    with engine.connect() as c:
        assert F.any_muted(c, org_id=org, seat_id=seat_id, thread_keys=[thread, site], now=NOW)
        assert not F.any_muted(c, org_id=org, seat_id=seat_id, thread_keys=[thread], now=NOW)
        assert not F.any_muted(c, org_id=org, seat_id=seat_id, thread_keys=[None, ""], now=NOW)
        assert not F.any_muted(c, org_id=org, seat_id=seat_id, thread_keys=[], now=NOW)
        # the one-key wrapper still answers the same question
        assert F.is_muted(c, org_id=org, seat_id=seat_id, thread_key=site, now=NOW)
        assert not F.is_muted(c, org_id=org, seat_id=seat_id, thread_key=None, now=NOW)


def test_what_the_seat_kept_and_what_it_refused_come_back_together(engine, seat):
    org, seat_id = seat
    with engine.begin() as c:
        _note(c, org, seat_id, "Priya asked for this quote on 6 Sep too", "useful",
              NOW - timedelta(hours=1))
        _note(c, org, seat_id, "Reply to the Naukri alert", F.NOT_USEFUL_ACTION,
              NOW - timedelta(hours=2))
        _note(c, org, seat_id, "You owe Neha the deck", "useful", NOW - timedelta(hours=3))
        _note(c, org, seat_id, "Nobody acted on this one", "shown", NOW - timedelta(minutes=5))
    with engine.connect() as c:
        out = F.taught_notes(c, org_id=org, seat_id=seat_id, capability_id=CAP)
        assert out["useful"] == ["Priya asked for this quote on 6 Sep too", "You owe Neha the deck"]
        assert out["not_useful"] == ["Reply to the Naukri alert"]
        # the two old entry points read the same rows
        assert F.useful_notes(c, org_id=org, seat_id=seat_id, capability_id=CAP) == out["useful"]
        assert F.not_useful_notes(c, org_id=org, seat_id=seat_id,
                                  capability_id=CAP) == out["not_useful"]
        # another capability's feedback never leaks in, and limit 0 asks nothing
        assert F.taught_notes(c, org_id=org, seat_id=seat_id,
                              capability_id="moment.meeting_prep")["useful"] == []
        assert F.taught_notes(c, org_id=org, seat_id=seat_id, capability_id=CAP,
                              limit=0) == {"useful": [], "not_useful": []}


def test_the_newest_of_each_kind_wins_when_a_note_was_judged_twice(engine, seat):
    org, seat_id = seat
    with engine.begin() as c:
        for i in range(7):
            _note(c, org, seat_id, f"note {i}", "useful", NOW - timedelta(minutes=i))
    with engine.connect() as c:
        out = F.taught_notes(c, org_id=org, seat_id=seat_id, capability_id=CAP)
    assert out["useful"] == [f"note {i}" for i in range(F.NOT_USEFUL_NOTES)], "newest first, capped"


def test_a_refused_note_older_than_every_kept_one_still_comes_back(engine, seat):
    # The skew that a single `limit` over both actions would lose — and the refused note is the
    # example the model most needs, because it is the kind it must stop writing.
    org, seat_id = seat
    with engine.begin() as c:
        _note(c, org, seat_id, "the one they refused", F.NOT_USEFUL_ACTION, NOW - timedelta(days=9))
        for i in range(10):
            _note(c, org, seat_id, f"kept {i}", "useful", NOW - timedelta(minutes=i))
    with engine.connect() as c:
        out = F.taught_notes(c, org_id=org, seat_id=seat_id, capability_id=CAP)
    assert out["not_useful"] == ["the one they refused"]
    assert out["useful"] == [f"kept {i}" for i in range(F.NOT_USEFUL_NOTES)]
