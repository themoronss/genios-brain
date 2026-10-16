"""STEP-15 · your promises due — each open promise of ours overdue or due within a week, with the mail it was made in
and the person it is owed to.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_your_promises_due.py

`context/promises_due.promises_due` (tree `yc2_w27_s15` M44.C2.L-data.V0.U05). F30: *"I'll send the pilot proposal by
Friday"*, from the founder's own sent mail to Gaurav, is a commitment node of memory and was in no brief. A promise is
OURS by STEP-04's one identity: its written owner is an address of ours; else the node that owns it is ours; else —
no owner at all — its mail was sent by us. Open, and overdue or due within seven days. Owed to the people its mail
went to, by name, never an address; never us.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import promises_due as P

pytestmark = pytest.mark.pg

ORG = "org_s15_promises"
NOW = datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc)
ME, GAURAV = "arjun@nimbuslabs.test", "gaurav@stackfield.test"


@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — promises are read from Postgres")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Arjun Rao', :e)"), {"o": ORG, "e": ME})
        for node, name, email in (("n_me", "Arjun Rao", ME), ("n_gaurav", GAURAV, GAURAV),
                                  ("n_tara", "Tara Bose", "tara@fjordvp.test")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                           "values (:n, :o, 'person', :k, :d)"), {"n": node, "o": ORG, "k": email, "d": name})
            c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id) "
                           "values (:o, 'email', :k, :n)"), {"o": ORG, "k": email, "n": node})
    yield engine
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _promise(engine, node, words, *, due=NOW + timedelta(days=4), maker="n_me", sender=ME, to=(GAURAV,),
             owner=None, status="open", private=False):
    eid = f"ev_{node}"
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
            "dedup_key, actor, occurred_at, recipients) values (:e, :o, 'conn', 'gmail', 'email_message', :e, :e, "
            "cast(:a as jsonb), :at, :to)"),
            {"e": eid, "o": ORG, "a": json.dumps({"email": sender}), "at": NOW - timedelta(days=1), "to": list(to)})
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                       "values (:n, :o, 'commitment', :n, :w)"), {"n": node, "o": ORG, "w": words})
        facts = [("commitment.text", words), ("commitment.status", status)]
        if due is not None:
            facts.append(("commitment.due_at", due.isoformat()))
        if owner is not None:
            facts.append(("commitment.owner", owner))
        for field, value in facts:
            c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
                           "value, created_by_event_id, visibility_scope) values (:f, :f, :o, :n, :fld, "
                           "cast(:v as jsonb), :e, :vis)"),
                      {"f": f"fv_{node}_{field}", "o": ORG, "n": node, "fld": field, "v": json.dumps(value),
                       "e": eid, "vis": "private" if private else "org"})
        if maker:
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
                           "to_node_id, created_by_event_id) values (:x, :x, :o, 'owns', :f, :t, :e)"),
                      {"x": f"ed_{node}", "o": ORG, "f": maker, "t": node, "e": eid})


def _due(engine, now=NOW):
    with engine.connect() as c:
        return P.promises_due(c, ORG, now=now)


def test_your_promise_from_your_own_mail_is_due_with_whom_and_where(pg):
    _promise(pg, "c_pilot", "send the pilot proposal", to=(GAURAV, ME.upper()))
    (p,) = _due(pg)
    assert (p.promise_id, p.words, p.overdue, p.event_id) == ("c_pilot", "send the pilot proposal", False, "ev_c_pilot")
    assert p.due_at == NOW + timedelta(days=4)
    assert [(o.name, o.key, o.node_id) for o in p.owed_to] == [("Gaurav", GAURAV, "n_gaurav")]


def test_overdue_first_then_soonest_and_a_week_is_the_horizon(pg):
    _promise(pg, "c_soon", "send the deck", due=NOW + timedelta(days=2))
    _promise(pg, "c_late", "share the numbers", due=NOW - timedelta(days=2))
    _promise(pg, "c_far", "write the update", due=NOW + timedelta(days=8))
    _promise(pg, "c_edge", "book the call", due=NOW + timedelta(days=7))
    assert [(p.promise_id, p.overdue) for p in _due(pg)] == [("c_late", True), ("c_soon", False),
                                                            ("c_edge", False)]


@pytest.mark.parametrize("over", [
    {"maker": "n_gaurav", "sender": GAURAV, "to": (ME,)},           # their promise, in their mail
    {"status": "done"},                                              # kept already
    {"due": None},                                                   # undated: nothing to be due by
    {"private": True},                                               # a private fact is no org reader's
    {"owner": GAURAV},                                               # the written owner is theirs, whoever the edge says
    {"maker": None, "sender": GAURAV, "to": (ME,)},                  # no owner at all, and the mail was theirs
])
def test_what_is_not_a_promise_of_yours_due(pg, over):
    _promise(pg, "c_x", "send the deck", **over)
    assert _due(pg) == ()


def test_the_written_owner_decides_and_without_one_the_maker_then_the_mail(pg):
    _promise(pg, "c_owner", "send the deck", maker="n_gaurav", owner=ME.upper())
    _promise(pg, "c_mail", "share the plan", maker=None, sender=ME, to=("tara@fjordvp.test",))
    got = {p.promise_id: p for p in _due(pg)}
    assert set(got) == {"c_owner", "c_mail"}
    assert [o.name for o in got["c_mail"].owed_to] == ["Tara Bose"]


def test_a_promise_made_in_their_mail_is_owed_to_nobody_named(pg):
    _promise(pg, "c_said", "send the deck", maker="n_me", sender=GAURAV, to=(ME, "tara@fjordvp.test"))
    (p,) = _due(pg)
    assert p.owed_to == ()


def test_someone_memory_holds_no_node_for_is_named_from_their_address(pg):
    _promise(pg, "c_rhea", "send the times", to=("rhea@tallowfin.test",))
    (p,) = _due(pg)
    assert [(o.name, o.key, o.node_id) for o in p.owed_to] == [("Rhea", "rhea@tallowfin.test", None)]


def test_a_due_date_without_its_zone_is_utc_and_an_unreadable_one_is_no_date(pg):
    _promise(pg, "c_naive", "send the deck")
    _promise(pg, "c_bad", "share the plan")
    with pg.begin() as c:
        c.execute(text("update graph_facts set value = cast(:v as jsonb) where fact_version_id = :f"),
                  {"v": json.dumps("2026-09-22T10:00:00"), "f": "fv_c_naive_commitment.due_at"})
        c.execute(text("update graph_facts set value = cast(:v as jsonb) where fact_version_id = :f"),
                  {"v": json.dumps("by Friday"), "f": "fv_c_bad_commitment.due_at"})
    (p,) = _due(pg)
    assert p.promise_id == "c_naive" and p.due_at == datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
