"""STEP-04 · `identity_for` reads who we are from every place it is written — once.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_identity_for.py -q

`platform/self_identity.identity_for` (tree `yc2_w27_s04/M22.C1.L-data.V1.U03`). Four sources, one
statement: the active seats, `orgs.email`, the connected accounts (`connections.external_account_id`,
empty in production today and read so the day it is written it counts), and what the tenant declared
(`org_self_identities`). A deactivated seat is no longer us. A declared public mail domain is refused,
never applied — the failure it prevents is a Gmail founder making every Gmail sender one of us.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from genios_engine.platform.self_identity import SelfIdentity, identity_for

pytestmark = pytest.mark.pg
ORG = "identity_for_org"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'MrRohitSwerashi@gmail.com')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _seed(c) -> None:
    c.execute(text("insert into org_seats (org_id, seat_id, email, active) values "
                   "(:o, 'seat_owner', 'mrrohitswerashi@gmail.com', true), "
                   "(:o, 'seat_cofounder', 'harsh@thegenios.com', true), "
                   "(:o, 'seat_gone', 'left@oldco.test', false)"), {"o": ORG})
    c.execute(text("insert into connections (connection_id, org_id, external_account_id) "
                   "values ('conn_identity_for', :o, 'Founder.Mailbox@gmail.com')"), {"o": ORG})
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                   "(:o, 'address', 'ceo@thegenios.com', 'D6'), (:o, 'domain', 'thegenios.com', 'D6'), "
                   "(:o, 'domain', 'gmail.com', 'a mistake')"), {"o": ORG})


def test_every_source_is_read_once(engine):
    with engine.begin() as c:
        _seed(c)
    with engine.connect() as c:
        us = identity_for(c, ORG)
    assert isinstance(us, SelfIdentity)
    assert us.addresses == frozenset({"mrrohitswerashi@gmail.com", "harsh@thegenios.com",
                                      "founder.mailbox@gmail.com", "ceo@thegenios.com"})
    assert us.domains == frozenset({"thegenios.com"})


def test_a_deactivated_seat_is_no_longer_us(engine):
    with engine.begin() as c:
        _seed(c)
    with engine.connect() as c:
        assert not identity_for(c, ORG).is_us("left@oldco.test")


def test_a_declared_public_domain_is_refused_not_applied(engine, caplog):
    with engine.begin() as c:
        _seed(c)
    with engine.connect() as c:
        us = identity_for(c, ORG)
    assert not us.is_us("investor@gmail.com")
    assert "gmail.com" in caplog.text, "a refused declaration is said, not swallowed"


def test_an_engine_or_a_store_is_accepted_as_well_as_a_connection(engine):
    with engine.begin() as c:
        _seed(c)

    class _Store:
        def __init__(self, e):
            self.engine = e

    assert identity_for(engine, ORG) == identity_for(_Store(engine), ORG)


def test_an_org_that_declared_nothing_is_still_its_owner(engine):
    with engine.connect() as c:
        us = identity_for(c, ORG)
    assert us.addresses == frozenset({"mrrohitswerashi@gmail.com"}) and us.domains == frozenset()


def test_one_statement_reads_it(engine, monkeypatch):
    """Every caller pays one round trip, not four."""
    calls = []
    with engine.connect() as c:
        original = c.execute

        def counting(*a, **kw):
            calls.append(a[0])
            return original(*a, **kw)

        monkeypatch.setattr(c, "execute", counting)
        identity_for(c, ORG)
    assert len(calls) == 1
