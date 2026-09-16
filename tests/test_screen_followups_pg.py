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


# ── "Already handled": the card was right, the source was invisible ───────────────────────────
def _followup(c, org, seat_id, kind, resolution, *, nudged_before_close, created, topic):
    fid = f"fu_{uuid.uuid4().hex[:12]}"
    nudge = created + timedelta(hours=1)
    closed = nudge + timedelta(hours=1) if nudged_before_close else nudge - timedelta(minutes=30)
    c.execute(text(
        "insert into screen_followups (id, org_id, seat_id, kind, text, who, topic_key, "
        "created_at, updated_at, nudge_at, resolved_at, resolution) "
        "values (:i, :o, :s, :k, 'the revised quote', 'Priya', :t, :c, :c, :n, :r, :res)"),
        {"i": fid, "o": org, "s": seat_id, "k": kind, "t": topic, "c": created, "n": nudge,
         "r": closed, "res": resolution})
    return fid


def test_handled_closes_the_item_like_done(engine, seat):
    org, seat_id = seat
    with engine.begin() as c:
        fid = _followup(c, org, seat_id, "ask", None, nudged_before_close=True,
                        created=NOW - timedelta(hours=3), topic=uuid.uuid4().hex)
        c.execute(text("update screen_followups set resolved_at = null, resolution = null "
                       "where id = :i"), {"i": fid})
    out = F.resolve(engine, org_id=org, seat_id=seat_id, followup_id=fid,
                    resolution="handled", now=NOW)
    assert out["resolution"] == "handled" and out["resolved_at"] is not None
    # idempotent, and the constraint really accepts it
    again = F.resolve(engine, org_id=org, seat_id=seat_id, followup_id=fid,
                      resolution="done", now=NOW)
    assert again["resolution"] == "handled", "an already-closed item keeps its own answer"
    with pytest.raises(ValueError):
        F.resolve(engine, org_id=org, seat_id=seat_id, followup_id=fid, resolution="expired",
                  now=NOW)


def test_the_week_does_not_claim_what_it_did_not_cause(engine, seat):
    org, seat_id = seat
    created = NOW - timedelta(days=1)
    with engine.begin() as c:
        # closed after its nudge, by the product's prompting
        _followup(c, org, seat_id, "ask", "done", nudged_before_close=True, created=created,
                  topic=uuid.uuid4().hex)
        # right card, but the manager had already answered on a channel GeniOS cannot see
        _followup(c, org, seat_id, "ask", "handled", nudged_before_close=True, created=created,
                  topic=uuid.uuid4().hex)
        _followup(c, org, seat_id, "my_promise", "handled", nudged_before_close=True,
                  created=created, topic=uuid.uuid4().hex)
    r = F.weekly_report(engine, org_id=org, seat_id=seat_id, capability_id=CAP, now=NOW)
    assert r["asks_answered"] == 2, "the ask WAS answered — the outcome is real either way"
    assert r["promises_kept"] == 1
    # …but the product only claims the one it caused
    assert r["nudged_then_closed"] == 1, "'you would have missed it' is a causation claim"
    assert r["handled_elsewhere"] == 2, "the source-coverage gap, in one number"
