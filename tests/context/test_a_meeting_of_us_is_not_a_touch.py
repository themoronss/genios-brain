"""STEP-04 · a meeting of only us is not a channel touch.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_meeting_of_us_is_not_a_touch.py -q

`context/meeting_touch` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U03`). Its meetings query decided who
was "us" with its own inline SQL — the active seats, `orgs.email` and the connected accounts — so
an address of ours that is none of those was an outside attendee. Production's shape is exactly
that: the founder writes from Gmail, and `ceo@thegenios.com` only ever RECEIVES his mail. A
meeting of the two of them was minted as a `channel_touch` with "ceo@thegenios.com" as the
counterparty, and the same rows feed Admin's `meeting_follow_through`.

Who is us is now asked of `platform/self_identity.identity_for`: the declared address, and any
address at a declared domain, are us. A meeting with someone outside in it is still a touch, and
names only them.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.meeting_touch import refresh_channel_touch_situations

pytestmark = pytest.mark.pg

ORG = "meeting_of_us_org"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
#: `orgs.email` is UNIQUE, so this file's founder has an address no other test file inserts.
FOUNDER = "founder.meeting.touch@gmail.com"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        # conftest's own words: tests/contracts/test_h0_gate.py reads any other
        # skip in tests/context as a placeholder that names no gate.
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L2 tests skipped")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        # The founder signs up with his Gmail address: `orgs.email`, the one source the old
        # query and the new answer share.
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'Founder.Meeting.Touch@gmail.com')"),
                  {"o": ORG})
        # The address the old query could not see: not a seat, not `orgs.email`, not a connected
        # account — declared by the tenant (migration 0193).
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'address', 'ceo@thegenios.com', 'test')"), {"o": ORG})
        _person(c, "p_founder", FOUNDER, "Mr Rohit Swerashi")
        _person(c, "p_ceo", "ceo@thegenios.com", "GeniOS CEO")
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})      # cascades to the graph
    eng.dispose()


def _person(c, node_id: str, email: str, name: str) -> None:
    c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                   "values (:n, :o, 'person', :k, :d)"), {"n": node_id, "o": ORG, "k": email, "d": name})


def _meeting(c, node_id: str, title: str, attendees: list[str]) -> None:
    """A confirmed meeting three days before `NOW`, attended by the given person nodes."""
    c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
                   "values (:n, :o, 'meeting', :k, :d)"),
              {"n": node_id, "o": ORG, "k": f"cal:{node_id}", "d": title})
    for field, value in (("meeting.start_at", (NOW - timedelta(days=3)).isoformat()),
                         ("meeting.status", "confirmed")):
        c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                       "  field, value) values (:v, :f, :o, :n, :field, cast(:value as jsonb))"),
                  {"v": f"fv_{node_id}_{field}", "f": f"f_{node_id}_{field}", "o": ORG, "n": node_id,
                   "field": field, "value": json.dumps(value)})
    for person in attendees:
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                       "  from_node_id, to_node_id) values (:v, :e, :o, 'attended', :p, :m)"),
                  {"v": f"ev_{person}_{node_id}", "e": f"e_{person}_{node_id}", "o": ORG,
                   "p": person, "m": node_id})


def _touches(eng) -> dict[str, dict]:
    """Every situation the sweep wrote, by `(domain, anchor)` -> its `inputs`."""
    refresh_channel_touch_situations(SimpleNamespace(engine=eng), ORG, now=NOW)
    with eng.connect() as c:
        rows = c.execute(text("select domain, anchor_node_id, inputs from context_situations "
                              "where org_id = :o and status = 'active'"), {"o": ORG}).fetchall()
    return {(r.domain, r.anchor_node_id): r.inputs for r in rows}


def test_a_meeting_of_the_founder_and_his_declared_address_is_not_a_touch(engine):
    with engine.begin() as c:
        _meeting(c, "m_us", "Founder sync", ["p_founder", "p_ceo"])
    touches = _touches(engine)
    assert not [key for key in touches if key[1] == "m_us"], (
        f"a meeting of the founder and his own declared address was minted as an outside touch: "
        f"{ {k: v.get('counterparties') for k, v in touches.items()} }")


def test_a_colleague_at_a_declared_domain_is_one_of_us_in_a_meeting(engine):
    """Not a seat, not a declared address — an address at the company's declared domain."""
    with engine.begin() as c:
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'domain', 'thegenios.com', 'test')"), {"o": ORG})
        _person(c, "p_harsh", "harsh@thegenios.com", "Harsh")
        _meeting(c, "m_team", "Weekly team call", ["p_founder", "p_harsh"])
    touches = _touches(engine)
    assert not [key for key in touches if key[1] == "m_team"], (
        f"a meeting with a colleague at our declared domain was minted as an outside touch: "
        f"{ {k: v.get('counterparties') for k, v in touches.items()} }")


def test_a_meeting_with_someone_outside_is_a_touch_that_names_only_them(engine):
    """The positive control, and the counterparty list: every outside attendee, none of us."""
    with engine.begin() as c:
        _person(c, "p_siddhant", "siddhant@neon.fund", "Siddhant Jain")
        _person(c, "p_priya", "priya@neon.fund", "Priya Rao")
        _meeting(c, "m_neon", "Intro: Neon Fund",
                 ["p_founder", "p_ceo", "p_siddhant", "p_priya"])
    touches = _touches(engine)
    assert ("sales", "m_neon") in touches, f"a real outside meeting stopped being a touch: {touches}"
    assert touches[("sales", "m_neon")]["counterparties"] == ["Priya Rao", "Siddhant Jain"], (
        "the touch must name every outside attendee and none of us")


def test_the_follow_through_reading_is_handed_the_same_meetings(engine):
    """Admin's `meeting_follow_through` reads these meetings through the outreach gather. It must
    see the same answer: the meeting of us is not there, the outside one names only them."""
    from genios_engine.context.outreach_situations import _gather

    with engine.begin() as c:
        _person(c, "p_siddhant", "siddhant@neon.fund", "Siddhant Jain")
        _meeting(c, "m_us", "Founder sync", ["p_founder", "p_ceo"])
        _meeting(c, "m_neon", "Intro: Neon Fund", ["p_founder", "p_ceo", "p_siddhant"])
    held, _counts, _employers = _gather(SimpleNamespace(engine=engine), ORG, now=NOW)
    meetings = {m["node_id"]: m for m in held["_meetings"]}
    assert "m_us" not in meetings, f"the follow-through reading was handed a meeting of us: {meetings}"
    assert meetings["m_neon"]["counterparties"] == ["Siddhant Jain"], meetings
