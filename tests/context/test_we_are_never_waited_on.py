"""STEP-04 · none of us, and no machine, is ever a party someone waits on.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_we_are_never_waited_on.py -q

`context/outreach_situations` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U12`). Production carried an
offer card naming "ceo@thegenios.com and Mr Rohit Swerashi" as waiting longest. `ceo@thegenios.com`
is the founder's second address and only ever RECEIVES his mail, so every outbound to it wrote
`ball_in_court = them` and `thread.days_waiting` — and every waiting reading (per person, cohort,
organization) put it, and the founder, in a counterparty's place. A `service` node — a machine — was
waited on the same way.

And the overdue-commitment reading checked "a promise of ours" against ONE sending address,
`_mailbox_owner`, which is None the moment a second address of ours sends mail: with a co-founder's
seat sending too, a counterparty's promise was carded as ours again. The owner is now ANY of us
(`platform/self_identity`).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import (
    _gather,
    read_awaiting_response,
    read_organization_silence,
    read_overdue_commitments,
    read_outreach_cohorts,
)

pytestmark = pytest.mark.pg

ORG = "never_waited_on_org"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
#: `orgs.email` is UNIQUE, so this file's founder has an address no other test file inserts.
FOUNDER = "founder.waiting@gmail.com"
SECOND = "ceo@thegenios.com"                 # declared; only ever receives the founder's mail
COFOUNDER = "harsh@thegenios.com"            # an active seat, and a second sending address


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'Founder.Waiting@gmail.com')"),
                  {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'address', :a, 'test')"), {"o": ORG, "a": SECOND})
        c.execute(text("insert into org_seats (org_id, seat_id, email, active) "
                       "values (:o, 'seat_cofounder', :a, true)"), {"o": ORG, "a": COFOUNDER})
        for node_id, kind, key, name in (
                ("p_founder", "person", FOUNDER, "Mr Rohit Swerashi"),
                ("p_second", "person", SECOND, "GeniOS CEO"),
                ("p_cofounder", "person", COFOUNDER, "Harsh"),
                ("p_siddhant", "person", "siddhant@neon.fund", "Siddhant Jain"),
                ("p_priya", "person", "priya@neon.fund", "Priya Rao"),
                ("s_noreply", "service", "noreply@notify.vendor.io", "Vendor notifications")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                           "  display_name) values (:n, :o, :t, :k, :d)"),
                      {"n": node_id, "o": ORG, "t": kind, "k": key, "d": name})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})       # cascades
    eng.dispose()


def _fact(c, node_id: str, field: str, value, *, event: str | None = None) -> str:
    version = f"fv_{node_id}_{field}"
    c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                   "  field, value, created_by_event_id) "
                   "values (:v, :f, :o, :n, :field, cast(:value as jsonb), :e)"),
              {"v": version, "f": f"f_{node_id}_{field}", "o": ORG, "n": node_id, "field": field,
               "value": json.dumps(value), "e": event})
    return version


def _edge(c, edge_type: str, frm: str, to: str) -> None:
    c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                   "  from_node_id, to_node_id) values (:v, :e, :o, :t, :f, :to)"),
              {"v": f"ev_{edge_type}_{frm}_{to}", "e": f"e_{edge_type}_{frm}_{to}", "o": ORG,
               "t": edge_type, "f": frm, "to": to})


def _waiting(c, node_id: str, days: int, objective: str | None = None) -> None:
    """What `waiting.py` writes on a counterparty whose last message was ours."""
    _fact(c, node_id, "thread.days_waiting", days)
    _fact(c, node_id, "thread.ball_in_court", "them")
    if objective:
        _fact(c, node_id, "thread.objective", objective)


def _held(eng) -> tuple[dict, dict]:
    held, _counts, employers = _gather(SimpleNamespace(engine=eng), ORG, now=NOW)
    return held, employers


def test_neither_address_of_the_founder_is_awaited_and_an_outside_person_is(engine):
    with engine.begin() as c:
        _waiting(c, "p_second", 30)
        _waiting(c, "p_founder", 25)
        _waiting(c, "p_siddhant", 12)
    held, employers = _held(engine)
    awaited = {f.concerns_node for f in read_awaiting_response(held, NOW, employers)}
    assert "p_second" not in awaited, "the founder's own second address was put on an awaiting line"
    assert "p_founder" not in awaited, "the founder himself was put on an awaiting line"
    assert "p_siddhant" in awaited, "a real outside person stopped being awaited"


def test_a_service_is_never_awaited(engine):
    with engine.begin() as c:
        _waiting(c, "s_noreply", 20)
    held, employers = _held(engine)
    awaited = {f.concerns_node for f in read_awaiting_response(held, NOW, employers)}
    assert "s_noreply" not in awaited, "a machine was put on an awaiting line"


def test_nobody_of_ours_is_on_a_waiting_longest_line(engine):
    """The production line: a campaign whose longest-waiting names were the founder's own."""
    with engine.begin() as c:
        _waiting(c, "p_second", 30, objective="fundraising")
        _waiting(c, "p_siddhant", 12, objective="fundraising")
        _waiting(c, "p_priya", 9, objective="fundraising")
    held, employers = _held(engine)
    [cohort] = read_outreach_cohorts(held, NOW, employers)
    facts = {name: value for name, value, _kind in cohort.facts}
    assert "GeniOS CEO" not in facts["cohort.waiting_longest"], facts["cohort.waiting_longest"]
    assert facts["cohort.waiting_longest"] == "Siddhant Jain, Priya Rao"
    assert cohort.concerns_node != "p_second", "the cohort card's subject is one of us"


def test_our_own_company_has_not_gone_quiet_and_an_outside_firm_has(engine):
    with engine.begin() as c:
        for node_id, name in (("c_genios", "GeniOS"), ("c_neon", "Neon Fund")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                           "  display_name) values (:n, :o, 'company', :k, :d)"),
                      {"n": node_id, "o": ORG, "k": name.lower().replace(" ", ""), "d": name})
        for person, company in (("p_second", "c_genios"), ("p_cofounder", "c_genios"),
                                ("p_siddhant", "c_neon"), ("p_priya", "c_neon")):
            _edge(c, "works_at", person, company)
            _waiting(c, person, 15)
    held, employers = _held(engine)
    quiet = {f.correlation_id for f in read_organization_silence(held, NOW, employers)}
    assert "organization:c_genios" not in quiet, "our own company was reported as gone quiet"
    assert "organization:c_neon" in quiet, "an outside firm that went quiet stopped being reported"


def test_a_promise_any_of_us_made_is_ours_and_a_counterpartys_is_not(engine):
    """Two of us send mail — the founder and the co-founder's seat — so the single sending
    address the old check needed does not exist. The owner is still known to be us, or not."""
    overdue = (NOW - timedelta(days=6)).isoformat()
    with engine.begin() as c:
        for n, sender in ((1, FOUNDER), (2, COFOUNDER)):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "  source_object_id, parent_object_id, dedup_key, actor, occurred_at) "
                "values (:e, :o, 'conn_waited', 'gmail', 'message', :e, :t, :e, "
                "  cast(:actor as jsonb), :at)"),
                {"e": f"ev_waited_{n}", "o": ORG, "t": f"th_waited_{n}",
                 "actor": json.dumps({"email": sender}), "at": NOW - timedelta(days=10)})
            # our outbound, as the pipeline records it: `thread.last_outbound`, traced to the event
            person = "p_siddhant" if n == 1 else "p_priya"
            version = _fact(c, person, "thread.last_outbound",
                            (NOW - timedelta(days=10)).isoformat(), event=f"ev_waited_{n}")
            c.execute(text("insert into graph_source_refs (source_ref_id, org_id, fact_version_id, "
                           "  event_id) values (:r, :o, :v, :e)"),
                      {"r": f"ref_waited_{n}", "o": ORG, "v": version, "e": f"ev_waited_{n}"})
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                       "  display_name) values ('p_sunil', :o, 'person', "
                       "  'sunil.s@sanchiconnect.tech', 'Sunil')"), {"o": ORG})
        for node_id, owner, action in (("c_theirs", "p_sunil", "provide fundraising opportunities"),
                                       ("c_ours", "p_cofounder", "send the deck")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                           "  display_name) values (:n, :o, 'commitment', :k, :d)"),
                      {"n": node_id, "o": ORG, "k": f"commitment:{node_id}", "d": action})
            _fact(c, node_id, "commitment.due_at", overdue, event="ev_waited_1")
            _fact(c, node_id, "commitment.action", action, event="ev_waited_1")
            _edge(c, "owns", owner, node_id)
    held, employers = _held(engine)
    carded = {f.concerns_node for f in read_overdue_commitments(held, NOW, employers)}
    assert "c_theirs" not in carded, (
        "a counterparty's promise was carded as ours because two of us send mail")
    assert "c_ours" in carded, "a promise the co-founder made is ours and must stay a card"
