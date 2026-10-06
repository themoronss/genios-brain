"""STEP-04 · a meeting prep knows which attendees are us — by the one answer.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/meetings/test_prep_knows_who_we_are.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U24`, found while writing the guard (U19): `reason/meetings/
prep.read` marked an attendee internal when one of their addresses was a SEAT's — any seat, active or
not — and asked nothing else. So the founder's own declared second address (`ceo@thegenios.com`), and
a colleague at the company's declared domain, were people he was meeting. Now it is
`platform/self_identity.identity_for(...).is_us`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason.meetings import prep

pytestmark = pytest.mark.pg

ORG = "prep_knows_who_we_are_org"
NOW = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
FOUNDER = "founder.prep@gmail.com"
SECOND = "ceo@kiteprep.test"              # declared address
COLLEAGUE = "ops@kiteprep.test"           # at the declared domain, neither seat nor declared address
INVESTOR = "ira@northwind.test"


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": ORG, "e": FOUNDER})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', :a, 'test'), (:o, 'domain', 'kiteprep.test', 'test')"),
                  {"o": ORG, "a": SECOND})
    yield pg_store
    _reset(pg_store)


def test_our_own_addresses_are_never_people_we_are_meeting(store):
    with store.engine.begin() as c:
        node = {key: store.find_or_create_node(c, org_id=ORG, node_type=kind, canonical_key=key,
                                               display_name=key, event_id="evt_u24")
                for kind, key in (("meeting", "meeting:u24"), ("person", FOUNDER),
                                  ("person", SECOND), ("person", COLLEAGUE),
                                  ("person", INVESTOR))}
    att = prep.Attendance(meeting_node_id=node["meeting:u24"], me=node[FOUNDER],
                          attendees=(node[SECOND], node[COLLEAGUE], node[INVESTOR]))
    with store.engine.connect() as c:
        out = prep.read(c, org_id=ORG, att=att, email=FOUNDER, now=NOW)
    assert node[INVESTOR] not in out.internal, "the investor was read as one of us"
    assert out.internal == {node[SECOND], node[COLLEAGUE]}, (
        f"one of us is someone the founder is meeting: {sorted(out.internal)}")
