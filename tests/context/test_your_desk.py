"""STEP-15 · your desk, measured: your last mail out across every mailbox of ours, and who waits on you since when.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_your_desk.py

`context/your_desk.desk_for` (tree `yc2_w27_s15` M44.C2.L-data.V0.U03; `03` s15-F15). F55: *"you have sent nothing for
28 days while three people wait"*. Your last mail is the newest mail ANY address of ours sent — the owner's, a
second address the tenant declared — from ANY connected mailbox, as of the instant asked about; its age a count of
whole days. The silence may be said only where every mailbox's receipt reads back past that mail and a completed
sync has looked since. Who waits on you is every file with an open ask owed by us — the person who asked, by name,
since their oldest such ask — oldest first.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context import your_desk as D
from genios_engine.context.workstreams import Ask

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s15_desk", "org_s15_desk_other"
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
FOUNDER, ALSO = "arjun@nimbuslabs.test", "arjun.rao@gmail.test"


@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the desk reads Postgres")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)

    def _drop():
        with engine.begin() as c:
            c.execute(text("delete from orgs where id in (:o, :x)"), {"o": ORG, "x": OTHER})
    _drop()
    with engine.begin() as c:
        for org, email in ((ORG, FOUNDER), (OTHER, "someone@other.test")):
            c.execute(text("insert into orgs (id, name, email) values (:o, 'Arjun Rao', :e)"), {"o": org, "e": email})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'address', :a, 'test')"), {"o": ORG, "a": ALSO})
    yield engine
    _drop()


def _mailbox(engine, cid, *, days=None, org=ORG, finished=NOW - timedelta(hours=1), exhausted=True):
    with engine.begin() as c:
        c.execute(text("insert into connections (connection_id, org_id, source_type, capture_scope, status) "
                       "values (:c, :o, 'gmail', cast(:s as jsonb), 'connected')"),
                  {"c": cid, "o": org, "s": json.dumps({"backfill_days": days} if days else {})})
        c.execute(text("insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, scanned, "
                       "claimed_total, cursor_exhausted, error, started_at, finished_at) values (:r, :o, :c, "
                       "'gmail', 'incremental', 1, 1, :x, null, :f, :f)"),
                  {"r": f"run_{cid}", "o": org, "c": cid, "x": exhausted, "f": finished})


def _mail(engine, eid, sender, at, *, cid="conn_a", org=ORG, source="gmail"):
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
            "dedup_key, actor, occurred_at) values (:e, :o, :c, :s, 'email_message', :e, :e, "
            "cast(:a as jsonb), :at)"),
            {"e": eid, "o": org, "c": cid, "s": source, "a": json.dumps({"email": sender}), "at": at})


def _person(engine, node, name, key):
    with engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                       "values (:n, :o, 'person', :k, :d)"), {"n": node, "o": ORG, "k": key, "d": name})


def _file(file_id, *asks, move="ours"):
    return SimpleNamespace(file_id=file_id, open_asks=tuple(asks), whose_move=move)


def _ask(loop, by, owed, at):
    return Ask(loop_id=loop, kind="question", asked_by=by, owed_by=owed, thread_id=None, opened_at=at)


def _desk(engine, files=(), now=NOW):
    with engine.connect() as c:
        return D.desk_for(c, ORG, files, now=now)


def test_your_last_mail_is_the_newest_of_any_address_of_ours_in_any_mailbox(pg):
    _mailbox(pg, "conn_a")
    _mailbox(pg, "conn_b")
    _mail(pg, "e_old", FOUNDER, NOW - timedelta(days=35))
    _mail(pg, "e_also", ALSO.upper(), NOW - timedelta(days=28, hours=6), cid="conn_b")
    _mail(pg, "e_theirs", "dev@tanglewood.test", NOW - timedelta(days=2))          # not ours
    _mail(pg, "e_cal", FOUNDER, NOW - timedelta(days=1), source="gcal")            # a calendar is no mail
    _mail(pg, "e_later", FOUNDER, NOW + timedelta(hours=2))                        # not yet sent
    _mail(pg, "e_other", "someone@other.test", NOW - timedelta(days=1), org=OTHER)
    desk = _desk(pg)
    assert desk.last_out_event == "e_also" and desk.last_out == NOW - timedelta(days=28, hours=6)
    assert desk.days_since.says() == "28 days" and desk.days_since.n == 28 and desk.days_since.basis == "you"
    assert desk.silence_can_be_said is True and len(desk.mailboxes) == 2


def test_the_silence_is_unsayable_where_a_mailbox_cannot_vouch_for_it(pg):
    _mailbox(pg, "conn_a")
    _mailbox(pg, "conn_b", days=7)                                                 # reads back a week only
    _mail(pg, "e1", FOUNDER, NOW - timedelta(days=28))
    desk = _desk(pg)
    assert desk.days_since.n == 28 and desk.silence_can_be_said is False


def test_a_mailbox_whose_last_sync_did_not_complete_vouches_for_nothing(pg):
    _mailbox(pg, "conn_a", exhausted=False)
    _mail(pg, "e1", FOUNDER, NOW - timedelta(days=28))
    assert _desk(pg).silence_can_be_said is False


def test_no_mailbox_and_no_mail_of_ours_say_nothing(pg):
    _mail(pg, "e1", FOUNDER, NOW - timedelta(days=3))
    desk = _desk(pg)
    assert desk.mailboxes == () and desk.silence_can_be_said is False and desk.days_since.n == 3
    _mailbox(pg, "conn_a")
    with pg.begin() as c:
        c.execute(text("delete from source_events where org_id = :o"), {"o": ORG})
    _mail(pg, "e2", "dev@tanglewood.test", NOW - timedelta(days=3))
    desk = _desk(pg)
    assert desk.last_out is None and desk.days_since is None and desk.silence_can_be_said is False


def test_who_waits_on_you_by_name_since_their_oldest_ask_oldest_first(pg):
    _person(pg, "n_dev", "Dev Malhotra", "dev@tanglewood.test")
    _person(pg, "n_kavya", "kavya@ferrypay.test", "kavya@ferrypay.test")
    _person(pg, "n_events", "events@bluebayhub.test", "events@bluebayhub.test")
    files = [
        _file("f_dev", _ask("l_dev2", "n_dev", "us", NOW - timedelta(days=20)),
              _ask("l_dev1", "n_dev", "us", NOW - timedelta(days=26, hours=7))),
        _file("f_kavya", _ask("l_kav", "n_kavya", "us", NOW - timedelta(days=17))),
        _file("f_events", _ask("l_ev", "n_events", "us", NOW - timedelta(days=22))),
        _file("f_theirs", _ask("l_th", "n_dev", "them", NOW - timedelta(days=40))),  # we wait on them
        _file("f_undated", _ask("l_un", "n_dev", "us", None)),
        _file("f_their_turn", _ask("l_tt", "n_dev", "us", NOW - timedelta(days=42)), move="theirs"),
        _file("f_no_turn", _ask("l_nt", "n_dev", "us", NOW - timedelta(days=42)), move=None),
        _file("f_quiet"),
    ]
    desk = _desk(pg, files)
    assert [(w.file_id, w.who, w.days.n, w.loop_id) for w in desk.waiting] == [
        ("f_dev", "Dev Malhotra", 26, "l_dev1"), ("f_events", None, 22, "l_ev"), ("f_kavya", "Kavya", 17, "l_kav")]
    assert desk.waiting[0].since == NOW - timedelta(days=26, hours=7)
    assert desk.waiting[0].days.says() == "26 days"
    assert desk.waiting_count.n == 3 and desk.waiting_count.says() == "3 people"
    assert _desk(pg).waiting == () and _desk(pg).waiting_count.says() == "none"
