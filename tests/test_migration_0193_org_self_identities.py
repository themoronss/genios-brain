"""STEP-04 · what a tenant declares is its own — one row per address or domain.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_migration_0193_org_self_identities.py -q

`migrations/0193_org_self_identities.sql` (tree `yc2_w27_s04/M22.C1.L-contract.V0.U01`). "Who is us"
was decided in eighteen places from `orgs.email`, the seats and a connections column nothing writes
(`speedrun008/YC-II W27/` STEP-04 §8.2). An address of ours that is neither — `ceo@thegenios.com`, which
only ever receives the founder's own mail — and the company's own domain had nowhere to be said. This
table is where the tenant says it: closed kinds, lowercase values, one row per value, and gone with
the account.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.pg
ORG = "m0193_org"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'm0193@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _declare(c, kind: str, value: str, by: str = "test") -> None:
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                   "values (:o, :k, :v, :b)"), {"o": ORG, "k": kind, "v": value, "b": by})


def test_an_address_and_a_domain_are_declared(engine):
    with engine.begin() as c:
        _declare(c, "address", "ceo@thegenios.com")
        _declare(c, "domain", "thegenios.com")
    with engine.connect() as c:
        rows = c.execute(text("select kind, value, declared_by, declared_at from org_self_identities "
                              "where org_id = :o order by kind"), {"o": ORG}).fetchall()
    assert [(r.kind, r.value) for r in rows] == [("address", "ceo@thegenios.com"),
                                                ("domain", "thegenios.com")]
    assert all(r.declared_at is not None for r in rows)


@pytest.mark.parametrize("kind, value", [("person", "x@y.test"), ("address", "CEO@TheGenios.com"),
                                         ("domain", "")])
def test_a_kind_outside_the_vocabulary_or_an_unnormalised_value_is_refused(engine, kind, value):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _declare(c, kind, value)


def test_one_row_per_value(engine):
    with engine.begin() as c:
        _declare(c, "address", "ceo@thegenios.com")
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _declare(c, "address", "ceo@thegenios.com")


def test_the_declaration_goes_with_the_account(engine):
    with engine.begin() as c:
        _declare(c, "domain", "thegenios.com")
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    with engine.connect() as c:
        assert c.execute(text("select count(*) from org_self_identities where org_id = :o"),
                         {"o": ORG}).scalar() == 0
