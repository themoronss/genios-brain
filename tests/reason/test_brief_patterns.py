"""STEP-07 · the drafter reads memory PATTERNS — counts, names, domains, dates — never a message.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_brief_patterns.py -q

Tree `yc2_w27_s07 · M25.C3.L-logic.V2.U01`. A chief of staff on day one reads who writes to whom and
how often, which domains are government portals, the day eleven funds were written to, the cohort's
recurring sessions, who keeps introducing people, and which senders carry deadlines. The drafter is
handed exactly that (`reason/brief_patterns.patterns_for`) — and nothing captured privately, no fact
only one seat may see, no thread name (a thread is named by its subject), no single meeting's title.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason.brief_patterns import addresses_in, domains_in, patterns_for

pytestmark = pytest.mark.pg

ORG = "org_s07_patterns"
US = "arjun@nimbus.test"
NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
WAVE_DAY = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
FUNDS = ("fund1.test", "fund2.test", "fund3.test", "fund4.test", "fund5.test")


def _clean(c) -> None:
    for table in ("graph_facts", "graph_edges", "graph_nodes", "source_events"):
        c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        _clean(c)
        c.execute(text("insert into orgs (id, name, company, email) "
                       "values (:o, 'Arjun Rao', 'Nimbus Labs', :e)"), {"o": ORG, "e": US})
    yield eng
    with eng.begin() as c:
        _clean(c)


_n = iter(range(10_000))


def _mail(c, *, sender, recipients=(), at=NOW - timedelta(days=3), name=None, attention=None,
          private=False) -> str:
    key = f"m{next(_n)}"
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        " source_object_id, dedup_key, actor, occurred_at, captured_at, sync_mode, schema_version, "
        " outcome, recipients, attention, visibility_scope) values (:e, :o, 'conn_s07p', 'gmail', "
        " 'email_message', :k, :d, cast(:actor as jsonb), :t, :t, 'backfill', 3, 'emitted', :r, :a, "
        " :v)"),
        {"e": f"evt_{ORG}_{key}", "o": ORG, "k": key, "d": f"gmail:email_message:{ORG}:{key}",
         "actor": json.dumps({"email": sender, **({"name": name} if name else {})}), "t": at,
         "r": list(recipients), "a": attention, "v": "private" if private else None})
    return f"evt_{ORG}_{key}"


def _node(c, node_id, node_type, *, key=None, name=None, event=None) -> str:
    c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name, "
                   " created_by_event_id) values (:n, :o, :t, :k, :d, :e)"),
              {"n": node_id, "o": ORG, "t": node_type, "k": key, "d": name, "e": event})
    return node_id


def _fact(c, node_id, field, value, *, at=NOW - timedelta(days=2), event=None, scope="org") -> None:
    fid = f"f{next(_n)}"
    c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
                   " value, occurred_at, created_by_event_id, visibility_scope) "
                   "values (:v, :f, :o, :n, :field, cast(:val as jsonb), :t, :e, :s)"),
              {"v": f"{fid}_v1", "f": fid, "o": ORG, "n": node_id, "field": field,
               "val": json.dumps(value), "t": at, "e": event, "s": scope})


def _world(engine) -> None:
    with engine.begin() as c:
        for _ in range(3):
            _mail(c, sender="pankaj@fund1.test", recipients=[US], name="Pankaj")
        _mail(c, sender=US, recipients=["pankaj@fund1.test"])
        for d in FUNDS:
            _mail(c, sender=US, recipients=[f"partner@{d}"], at=WAVE_DAY)
        # Boardy introduces two people from other companies; we write to one of them after.
        _mail(c, sender="boardy@boardy.ai", recipients=[US, "silas@fund2.test"],
              at=NOW - timedelta(days=20))
        _mail(c, sender="boardy@boardy.ai", recipients=[US, "ori@labs.test"],
              at=NOW - timedelta(days=10))
        _mail(c, sender=US, recipients=["silas@fund2.test"], at=NOW - timedelta(days=9))
        # A colleague of the sender copied is not an introduction.
        _mail(c, sender="ceo@acme.test", recipients=[US, "cfo@acme.test"])
        _mail(c, sender="ceo@acme.test", recipients=[US, "coo@acme.test"])
        portal = _mail(c, sender="notice@sampark.gov.in", recipients=[US], attention="archive")
        _mail(c, sender="notice@sampark.gov.in", recipients=[US], attention="archive")
        _mail(c, sender="secret@private.test", recipients=[US], private=True)
        _mail(c, sender="old@ancient.test", recipients=[US], at=NOW - timedelta(days=400))

        boardy = _node(c, "n_boardy", "agent", key="boardy@boardy.ai", name="Boardy")
        _fact(c, boardy, "party.role", "introducer")
        for i, day in enumerate((NOW - timedelta(days=14), NOW - timedelta(days=7))):
            m = _node(c, f"n_cohort_{i}", "meeting", name="NSRCEL Cohort Session")
            _fact(c, m, "meeting.start_at", day.isoformat())
        _node(c, "n_coffee", "meeting", name="Coffee with a stranger")
        commitment = _node(c, "n_commit", "commitment", name="file the DPIIT form")
        _fact(c, commitment, "commitment.due_at", (NOW + timedelta(days=5)).isoformat(), event=portal)
        thread = _node(c, "n_thread", "thread", name="Re: Term sheet — confidential subject line")
        _fact(c, thread, "thread.objective", "Close the pre-seed round with Fund One")
        _fact(c, thread, "thread.objective", "A private screen note", scope="private")


def _by_kind(patterns, kind):
    return [i for i in patterns["items"] if i["kind"] == kind]


def test_correspondents_and_domains_are_counted_with_their_dates(engine):
    _world(engine)
    with engine.connect() as c:
        p = patterns_for(c, ORG, now=NOW)
    assert p["company"] == "Nimbus Labs" and p["founder"] == "Arjun Rao" and US in p["us"]
    pankaj = next(i for i in _by_kind(p, "correspondent") if i["address"] == "pankaj@fund1.test")
    assert (pankaj["from_them"], pankaj["to_them"], pankaj["name"]) == (3, 1, "Pankaj")
    portal = next(i for i in _by_kind(p, "domain") if i["domain"] == "sampark.gov.in")
    assert (portal["mail"], portal["archived"], portal["looks"]) == (2, 2, "government")
    assert [i["id"] for i in p["items"]] == [f"p{n}" for n in range(1, len(p["items"]) + 1)]


def test_the_wave_and_the_introducer_are_read_off_the_envelope(engine):
    _world(engine)
    with engine.connect() as c:
        p = patterns_for(c, ORG, now=NOW)
    assert _by_kind(p, "wave") == [{"id": _by_kind(p, "wave")[0]["id"], "kind": "wave",
                                    "day": "2026-08-11", "domains": list(FUNDS)}]
    introducers = _by_kind(p, "introducer")
    assert [i["address"] for i in introducers] == ["boardy@boardy.ai"]
    assert (introducers[0]["intros"], introducers[0]["people"], introducers[0]["followed_up"],
            introducers[0]["called_introducer"]) == (2, 2, 1, 1)


def test_a_recurring_series_and_a_deadline_domain_are_patterns_a_single_meeting_is_not(engine):
    _world(engine)
    with engine.connect() as c:
        p = patterns_for(c, ORG, now=NOW)
    assert [(s["title"], s["meetings"]) for s in _by_kind(p, "meeting_series")] == [
        ("NSRCEL Cohort Session", 2)]
    deadlines = _by_kind(p, "deadlines")
    assert [(d["domain"], d["deadlines"], d["looks"]) for d in deadlines] == [
        ("sampark.gov.in", 1, "government")]


def test_nothing_private_no_subject_and_nothing_outside_the_window(engine):
    _world(engine)
    with engine.connect() as c:
        p = patterns_for(c, ORG, now=NOW)
    rendered = json.dumps(p)
    assert "private.test" not in rendered                     # captured privately
    assert "A private screen note" not in rendered            # a fact one seat may see
    assert "Term sheet" not in rendered                       # a thread's name is its subject
    assert "Coffee with a stranger" not in rendered           # a single meeting is not a series
    assert "ancient.test" not in rendered                     # outside the window
    assert [t["about"] for t in _by_kind(p, "thread")] == ["Close the pre-seed round with Fund One"]


def test_the_patterns_bound_what_a_proposal_may_name(engine):
    _world(engine)
    with engine.connect() as c:
        p = patterns_for(c, ORG, now=NOW)
    assert {"boardy@boardy.ai", "pankaj@fund1.test"} <= addresses_in(p)
    assert {"sampark.gov.in", "boardy.ai", "fund5.test"} <= domains_in(p)
    assert "private.test" not in domains_in(p)


def test_the_same_memory_gives_the_same_patterns(engine):
    _world(engine)
    with engine.connect() as c:
        assert patterns_for(c, ORG, now=NOW) == patterns_for(c, ORG, now=NOW)


def test_an_empty_memory_has_no_patterns(engine):
    with engine.connect() as c:
        p = patterns_for(c, ORG, now=NOW)
    assert p["items"] == [] and p["company"] == "Nimbus Labs"
