"""STEP-04 · whether a condition's actor is one of us is asked of who we are.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_condition_owner_is_one_of_us.py -q

`context/condition_situations._is_owner` (tree `yc2_w27_s04/M22.C2.L-logic.V2.U13`).
`condition.actor_is_us` compared the actor with ONE address — `_mailbox_owner`, the single address
our outbound is sent from. So an actor that is ANOTHER address of ours (the founder's declared
`ceo@thegenios.com`, a co-founder's seat) was stamped "not us", and the moment a second address of
ours sent mail `_mailbox_owner` was None and no address could be answered at all.

An actor that is an address is now asked of `platform/self_identity`. A NAME keeps the existing
match against the mailbox owner's address, as the fallback it is — including its refusal to claim
a bare first name, because this tenant holds two Rohits.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.condition_situations import REVIEW_FIELD
from genios_engine.context.outreach_situations import (
    read_conditions_for_dispatch,
    read_conditions_met_for_dispatch,
)
from genios_engine.platform.self_identity import SelfIdentity

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
FOUNDER = "mrrohitswerashi@gmail.com"
SECOND = "ceo@thegenios.com"                 # declared; another address of the founder
COFOUNDER = "harsh@thegenios.com"            # an active seat
OUTSIDE = "sunil.s@sanchiconnect.tech"
US = SelfIdentity.of(addresses=[FOUNDER, SECOND, COFOUNDER])
ABSENT = "absent"


def _condition(actor: str) -> dict:
    return {"actor": actor, "action": "reply once it's booked", "predicate": None,
            "condition_text": "once it's booked", "condition_id": f"cond_{actor}",
            "stated_at": (NOW - timedelta(days=12)).isoformat(),
            "statement": [{"quote": "I'll reply here once it's booked.", "start_offset": 0,
                           "end_offset": 33}]}


def _satisfied(actor: str) -> dict:
    return {**_condition(actor), "satisfied_at": (NOW - timedelta(days=2)).isoformat(),
            "strength_bp": 8000, "stale": False, "world_key": "booking"}


def _flags(findings) -> dict[str, object]:
    out = {}
    for finding in findings:
        facts = {name: value for name, value, _kind in finding.facts}
        out[facts["condition.actor"]] = facts.get("condition.actor_is_us", ABSENT)
    return out


@pytest.mark.unit
def test_another_address_of_ours_as_the_actor_is_us():
    rows = {"_conditions": {"n_x": {"review": [_condition(a) for a in (
                SECOND, COFOUNDER, "Rohit Swerashi", "Rohit", "Rohit Nallapeta")]}},
            "_mailbox_owner": FOUNDER, "_us": US}
    flags = _flags(read_conditions_for_dispatch(rows, NOW, {}))
    assert flags[SECOND] is True, "the founder's declared address was stamped 'not us'"
    assert flags[COFOUNDER] is True, "a co-founder's seat was stamped 'not us'"
    # THE FALLBACK, KEPT AS IT IS: a name is matched against the mailbox owner's address.
    assert flags["Rohit Swerashi"] is True
    assert flags["Rohit"] == ABSENT, "a bare first name must claim nothing — two Rohits here"
    assert flags["Rohit Nallapeta"] is False


@pytest.mark.unit
def test_two_of_us_sending_mail_does_not_blind_the_address_check():
    """`_mailbox_owner` is None once a second address of ours sends, and every address went
    unanswered. Who we are does not depend on how many of us send."""
    rows = {"_conditions": {"n_x": {"review": [_condition(COFOUNDER), _condition(OUTSIDE)]}},
            "_mailbox_owner": None, "_us": US}
    flags = _flags(read_conditions_for_dispatch(rows, NOW, {}))
    assert flags[COFOUNDER] is True, "with two of us sending, our own seat was left unanswered"
    assert flags[OUTSIDE] is False, "an outside address is confidently not us"


@pytest.mark.unit
def test_a_condition_that_came_true_asks_the_same_identity():
    rows = {"_conditions_met": {"n_x": {"satisfied": [_satisfied(SECOND)]}},
            "_mailbox_owner": FOUNDER, "_us": US}
    flags = _flags(read_conditions_met_for_dispatch(rows, NOW, {}))
    assert flags[SECOND] is True, "the satisfied twin stamped our declared address 'not us'"


@pytest.mark.pg
def test_the_sweep_hands_the_reading_who_we_are():
    """End to end through `_gather`: no outbound is recorded, so `_mailbox_owner` is None, and the
    declared address still resolves as ours."""
    from genios_engine.context.outreach_situations import _gather

    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    org = "condition_owner_org"
    eng = create_engine(url)
    try:
        with eng.begin() as c:
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            # `orgs.email` is UNIQUE: an address no other test file inserts.
            c.execute(text("insert into orgs (id, name, email) "
                           "values (:o, :o, 'founder.conditions@gmail.com')"), {"o": org})
            c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                           "values (:o, 'address', :a, 'test')"), {"o": org, "a": SECOND})
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                           "  display_name) values ('n_cond', :o, 'person', 'x@vendor.io', 'X')"),
                      {"o": org})
            c.execute(text("insert into graph_facts (fact_version_id, fact_id, org_id, "
                           "  subject_node_id, field, value) "
                           "values ('fv_cond', 'f_cond', :o, 'n_cond', :field, cast(:v as jsonb))"),
                      {"o": org, "field": REVIEW_FIELD,
                       "v": json.dumps({"review": [_condition(SECOND)]})})
        held, _counts, employers = _gather(SimpleNamespace(engine=eng), org, now=NOW)
        assert held["_mailbox_owner"] is None
        flags = _flags(read_conditions_for_dispatch(held, NOW, employers))
        assert flags[SECOND] is True, "the sweep did not hand the reading who we are"
    finally:
        with eng.begin() as c:
            c.execute(text("delete from orgs where id = :o"), {"o": org})
        eng.dispose()
