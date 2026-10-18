"""STEP-04 · a screen recall knows when its subject is one of us — by the one answer.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/moments/test_recall_knows_who_we_are.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U25`, found while writing the guard (U19): `api/moment_routes`
read the seats' addresses (`_seat_emails`) and `reason/moments/recall.read` marked a subject internal
only when one of its addresses was a seat's. So the founder's declared second address, or a colleague
at the company's declared domain, was an outsider to recall facts about. Now the route reads
`platform/self_identity.identity_for` once and the read asks `is_us`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform.self_identity import identity_for
from genios_engine.reason.moments import recall as R

pytestmark = pytest.mark.pg

ORG = "recall_knows_who_we_are_org"
NOW = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
FOUNDER = "founder.recall@gmail.com"
SECOND = "ceo@kiterecall.test"            # declared address
COLLEAGUE = "ops@kiterecall.test"         # at the declared domain
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
                       "(:o, 'address', :a, 'test'), (:o, 'domain', 'kiterecall.test', 'test')"),
                  {"o": ORG, "a": SECOND})
    yield pg_store
    _reset(pg_store)


def _internal(store, key: str) -> bool:
    with store.engine.begin() as c:
        node = store.find_or_create_node(c, org_id=ORG, node_type="person", canonical_key=key,
                                         display_name=key, event_id="evt_u25")
    with store.engine.connect() as c:
        out = R.read(c, org_id=ORG, subject=R.Subject(node_id=node, node_type="person", name=key),
                     me=None, viewer=None, us=identity_for(c, ORG), now=NOW)
    return out.internal


@pytest.mark.parametrize("ours", [SECOND, COLLEAGUE, FOUNDER])
def test_one_of_us_is_never_a_subject_to_recall(store, ours):
    assert _internal(store, ours) is True, f"{ours} is ours and was read as an outsider"


def test_an_outside_person_still_is(store):
    assert _internal(store, INVESTOR) is False
