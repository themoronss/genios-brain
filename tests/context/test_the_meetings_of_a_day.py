"""STEP-15 · the meetings of a day, for a seat — today's and tomorrow's in the org's timezone, and the external meetings
nobody followed up.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_the_meetings_of_a_day.py

`context/meeting_days.meetings_of_day` (tree `yc2_w27_s15` M44.C2.L-data.V0.U04; `03` s15-F11). The day is the seat's
day in the org's timezone — a meeting at 01:30 IST belongs to that IST day whatever its UTC date. Cancelled meetings
and meetings the seat does not attend (or attends only through an event it may not read) are not its. A meeting of the
last fourteen days whose follow-up week has passed with no mail of ours to anyone on it is owed a follow-up (F54) —
unless it was internal, a gathering of more than ten, or a session of a series (F31).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import meeting_days as M

pytestmark = pytest.mark.pg

ORG = "org_s15_meetings"
TZ = "Asia/Kolkata"
NOW = datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc)          # 08:00 in Kolkata, 6 Oct
ME = "arjun@nimbuslabs.test"


@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the meetings are read from Postgres")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Arjun Rao', :e)"), {"o": ORG, "e": ME})
    _person(engine, "n_me", "Arjun Rao", ME)
    yield engine
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _person(engine, node, name, email):
    with engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                       "values (:n, :o, 'person', :k, :d)"), {"n": node, "o": ORG, "k": email, "d": name})
        c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id) "
                       "values (:o, 'email', :k, :n)"), {"o": ORG, "k": email, "n": node})


def _event(engine, eid, *, at=NOW - timedelta(days=30), sender=ME, to=(), private_to=None, source="gcal"):
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
            "dedup_key, actor, occurred_at, recipients, visibility_scope, visibility_principals) values (:e, :o, "
            "'conn', :s, 'x', :e, :e, cast(:a as jsonb), :at, :to, :scope, :p)"),
            {"e": eid, "o": ORG, "s": source, "a": json.dumps({"email": sender}), "at": at, "to": list(to),
             "scope": "private" if private_to else "participants", "p": list(private_to or ()) or None})


def _meeting(engine, node, title, start, *, people=("n_me",), status="confirmed", private_to=None):
    _event(engine, f"ev_{node}", private_to=private_to)
    with engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                       "values (:n, :o, 'meeting', :k, :t)"), {"n": node, "o": ORG, "k": f"gcal:{node}", "t": title})
        for field, value in (("meeting.title", title), ("meeting.start_at", start.isoformat()),
                             ("meeting.end_at", (start + timedelta(hours=1)).isoformat()),
                             ("meeting.status", status)):
            c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
                           "value, value_type, valid_from) values (:f, :f, :o, :n, :fld, cast(:v as jsonb), "
                           "'string', :at)"),
                      {"f": f"fv_{node}_{field}", "o": ORG, "n": node, "fld": field, "v": json.dumps(value),
                       "at": NOW - timedelta(days=30)})
        for p in people:
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
                           "to_node_id, created_by_event_id) values (:e, :e, :o, 'attended', :f, :t, :ev)"),
                      {"e": f"ed_{node}_{p}", "o": ORG, "f": p, "t": node, "ev": f"ev_{node}"})


def _day(engine, emails=(ME,), now=NOW):
    with engine.connect() as c:
        return M.meetings_of_day(c, ORG, emails=emails, now=now, tz=TZ)


def test_today_and_tomorrow_are_the_seats_days_in_the_orgs_timezone(pg):
    _person(pg, "n_neel", "Neel Shah", "neel@insight.test")
    _meeting(pg, "m_today", "Insight call", NOW + timedelta(hours=6), people=("n_me", "n_neel"))
    _meeting(pg, "m_early", "Early standup", datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc))   # 01:30 IST, 6 Oct
    _meeting(pg, "m_tomorrow", "Late call", datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc))    # 01:30 IST, 7 Oct
    _meeting(pg, "m_later", "Next week", NOW + timedelta(days=3))
    _meeting(pg, "m_cancelled", "Called off", NOW + timedelta(hours=3), status="cancelled")
    _meeting(pg, "m_not_mine", "Not mine", NOW + timedelta(hours=2), people=("n_neel",))
    _meeting(pg, "m_private", "Hidden", NOW + timedelta(hours=4), private_to=("someone@else.test",))
    with pg.begin() as c:                      # another seat's private retitle of a meeting the seat attends
        c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, "
                       "occurred_at, visibility_scope, visibility_principals) values ('fv_priv', 'fv_priv', :o, "
                       "'m_today', 'meeting.title', '\"Their private note\"', :at, 'private', :p)"),
                  {"o": ORG, "at": NOW, "p": ["someone@else.test"]})
    day = _day(pg)
    assert day.local_date == date(2026, 10, 6)
    assert [m.meeting_id for m in day.today] == ["m_early", "m_today"]
    assert [m.meeting_id for m in day.tomorrow] == ["m_tomorrow"]
    today = day.today[1]
    assert (today.title, today.attendees, today.unnamed, today.size, today.external) == \
        ("Insight call", ("Neel Shah",), 0, 2, True)
    assert today.start_at == NOW + timedelta(hours=6)


def test_the_viewer_is_the_seats_own_address_given_first(pg):
    _person(pg, "n_also", "Arjun Rao", "a.rao@nimbuslabs.test")
    _meeting(pg, "m_mine", "Private 1:1", NOW + timedelta(hours=5), private_to=(ME,))
    assert [m.meeting_id for m in _day(pg, emails=(ME, "a.rao@nimbuslabs.test")).today] == ["m_mine"]
    assert _day(pg, emails=("a.rao@nimbuslabs.test", ME)).today == ()     # another address of ours is not this seat


def test_a_seat_with_no_address_has_no_meetings(pg):
    _meeting(pg, "m_today", "Insight call", NOW + timedelta(hours=6))
    assert _day(pg, emails=()).today == ()


def test_an_external_meeting_with_no_follow_up_in_a_week_is_owed_one(pg):
    _person(pg, "n_kavya", "kavya@ferrypay.test", "kavya@ferrypay.test")
    _person(pg, "n_rhea", "rhea@tallowfin.test", "rhea@tallowfin.test")
    _person(pg, "n_org", "events@bluebayhub.test", "events@bluebayhub.test")
    mixer = NOW - timedelta(days=8)
    _meeting(pg, "m_mixer", "Fintech founders mixer - Bluebay", mixer, people=("n_me", "n_kavya", "n_rhea", "n_org"))
    _event(pg, "mail_theirs", at=mixer + timedelta(days=2), sender="kavya@ferrypay.test",
           to=(ME, "rhea@tallowfin.test"), source="gmail")                      # theirs is no follow-up of ours
    _event(pg, "mail_elsewhere", at=mixer + timedelta(days=1), to=("investor@else.test",), source="gmail")
    _event(pg, "mail_late", at=mixer + timedelta(days=7, hours=1), to=("rhea@tallowfin.test",), source="gmail")
    day = _day(pg)
    (owed,) = day.no_follow_up
    assert owed.meeting_id == "m_mixer" and owed.attendees == ("Kavya", "Rhea") and owed.unnamed == 1
    assert "events@bluebayhub.test" not in " ".join(owed.attendees)


def test_a_follow_up_inside_the_week_to_anyone_on_it_settles_it(pg):
    _person(pg, "n_kavya", "Kavya Iyer", "kavya@ferrypay.test")
    met = NOW - timedelta(days=9)
    _meeting(pg, "m_met", "Coffee", met, people=("n_me", "n_kavya"))
    _event(pg, "mail_ours", at=met + timedelta(days=3), to=("kavya@ferrypay.test",), source="gmail")
    assert _day(pg).no_follow_up == ()


def test_a_mail_before_a_meeting_is_no_follow_up_of_it(pg):
    _person(pg, "n_kavya", "Kavya Iyer", "kavya@ferrypay.test")
    first, second = NOW - timedelta(days=13), NOW - timedelta(days=9)
    _meeting(pg, "m_first", "Coffee", first, people=("n_me", "n_kavya"))
    _meeting(pg, "m_second", "Demo", second, people=("n_me", "n_kavya"))
    _event(pg, "mail_between", at=NOW - timedelta(days=11), to=("kavya@ferrypay.test",), source="gmail")
    assert [m.meeting_id for m in _day(pg).no_follow_up] == ["m_second"]


def test_a_follow_up_settles_only_the_meeting_its_person_was_on(pg):
    _person(pg, "n_kavya", "Kavya Iyer", "kavya@ferrypay.test")
    _person(pg, "n_omar", "Omar Haddad", "omar@tidewell.test")
    _meeting(pg, "m_kavya", "Coffee", NOW - timedelta(days=10), people=("n_me", "n_kavya"))
    _meeting(pg, "m_omar", "Demo", NOW - timedelta(days=10, hours=2), people=("n_me", "n_omar"))
    _event(pg, "mail_kavya", at=NOW - timedelta(days=8), to=("kavya@ferrypay.test",), source="gmail")
    assert [m.meeting_id for m in _day(pg).no_follow_up] == ["m_omar"]


@pytest.mark.parametrize("days_ago, people, also, why", [
    (3, 2, None, "its follow-up week has not passed"),
    (20, 2, None, "past the fourteen days looked back"),
    (8, 12, None, "a gathering of more than ten"),
    (8, 2, "series", "a session of a series"),
    (8, 0, None, "internal: nobody on it is not us"),
])
def test_what_is_never_owed_a_follow_up(pg, days_ago, people, also, why):
    for i in range(people):
        _person(pg, f"n_p{i}", f"Person {i}", f"p{i}@guest.test")
    _person(pg, "n_mine2", "Arjun Rao", "arjun.rao@nimbuslabs.test")
    with pg.begin() as c:
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'domain', 'nimbuslabs.test', 't')"), {"o": ORG})
    at = NOW - timedelta(days=days_ago)
    who = ("n_me", *(f"n_p{i}" for i in range(people))) if people else ("n_me", "n_mine2")
    _meeting(pg, "m_x", "Weekly pricing session", at, people=who)
    if also == "series":
        _meeting(pg, "m_x_prev", "Weekly pricing session", at - timedelta(days=7), people=who)
    assert _day(pg).no_follow_up == (), why
