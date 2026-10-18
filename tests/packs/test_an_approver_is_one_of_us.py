"""STEP-04 · U04 — an approver bound by name must be one of us, and "us" is the one answer.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/packs/test_an_approver_is_one_of_us.py -q

`packs/brains/org_discovery.resolve_approver_node` binds a policy's bare name ("approval from
Arjun") to a person node only when that node is one of the tenant's own people — PP-1: the only
Arjun the mailbox had seen was a buyer at the largest customer. `_names_one_of_us` decided "own"
with its own copy of the tenant SQL (active seats, `orgs.email`, `connections.external_account_id`),
so an address the tenant DECLARED its own (`org_self_identities`, migration 0193) and every address
at the domain it declared were strangers: the rule went to human review although its approver works
here. It asks `platform/self_identity.identity_for` now (tree `yc2_w27_s04/M22.C2.L-logic.V2.U04`).
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest
from sqlalchemy import create_engine, text

from genios_engine.packs.brains import org_discovery as og
from genios_engine.platform import self_identity
from genios_engine.platform.identity import person_name_key

pytestmark = pytest.mark.pg
ORG = "s04_approver_is_us"


@pytest.fixture
def conn():
    """A real-Postgres transaction on this file's own tenant — a Gmail founder — rolled back."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    c = engine.connect()
    tx = c.begin()
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    # `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
    c.execute(text("insert into orgs (id, name, email) values "
                   "(:o, :o, 'maya.s04approver@gmail.com')"), {"o": ORG})
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _person(c, node_id: str, email: str, name: str) -> None:
    """A person node and the observed name alias the middle rung reads."""
    c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
                   "display_name) values (:n, 1, :o, 'person', :e, :d)"),
              {"n": node_id, "o": ORG, "e": email, "d": name})
    c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin) "
                   "values (:o, 'person_name', :k, :n, 'observed')"),
              {"o": ORG, "k": person_name_key(name), "n": node_id})


def _declare(c, kind: str, value: str) -> None:
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                   "values (:o, :k, :v, 'test')"), {"o": ORG, "k": kind, "v": value})


def _seat(c, seat_id: str, email: str, *, active: bool) -> None:
    c.execute(text("insert into org_seats (org_id, seat_id, email, active) values (:o, :s, :e, :a)"),
              {"o": ORG, "s": seat_id, "e": email, "a": active})


def test_a_declared_address_is_one_of_us(conn):
    _declare(conn, "address", "arjun@acme.test")
    _person(conn, "n_s04_arjun_ours", "arjun@acme.test", "Arjun")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Arjun") == "n_s04_arjun_ours", (
        "arjun@acme.test is declared ours, and the policy's Arjun was refused as a stranger")


def test_an_address_at_our_declared_domain_is_one_of_us(conn):
    _declare(conn, "domain", "thegenios.com")
    _person(conn, "n_s04_priya", "priya@thegenios.com", "Priya Raman")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Priya Raman") == "n_s04_priya"


def test_an_active_seat_is_still_one_of_us(conn):
    _seat(conn, "seat_s04_rohit", "rohit@acme.test", active=True)
    _person(conn, "n_s04_rohit", "rohit@acme.test", "Rohit Sharma")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Rohit Sharma") == "n_s04_rohit"


def test_a_buyer_at_a_customer_is_still_refused(conn):
    """PP-1, the failure the rung exists to refuse — unchanged by a declared domain of ours."""
    _declare(conn, "domain", "acme.test")
    _person(conn, "n_s04_arjun_buyer", "arjun@bigcustomer.com", "Arjun")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Arjun") is None


def test_a_gmail_founder_does_not_make_every_gmail_user_ours(conn):
    """The founder's own mail host is never our domain, even when somebody declared it."""
    _declare(conn, "domain", "gmail.com")
    _person(conn, "n_s04_arjun_gmail", "arjun@gmail.com", "Arjun")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Arjun") is None


def test_a_deactivated_seat_is_no_longer_one_of_us(conn):
    _seat(conn, "seat_s04_gone", "left@acme.test", active=False)
    _person(conn, "n_s04_gone", "left@acme.test", "Lena Ford")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Lena Ford") is None


def test_an_unreadable_identity_binds_nobody(conn, monkeypatch):
    """FAILS CLOSED: if who-is-us cannot be read, the name rung grants no approval right."""
    def _unreadable(*_args, **_kwargs):
        raise RuntimeError("the identity could not be read")

    monkeypatch.setattr(self_identity, "identity_for", _unreadable)
    monkeypatch.setattr(og, "identity_for", _unreadable, raising=False)
    _seat(conn, "seat_s04_rohit", "rohit@acme.test", active=True)
    _person(conn, "n_s04_rohit", "rohit@acme.test", "Rohit Sharma")
    assert og.resolve_approver_node(conn, org_id=ORG, name="Rohit Sharma") is None


def test_the_name_rung_asks_the_one_answer():
    """`_names_one_of_us` reads `identity_for` and keeps no copy of the tenant identity SQL."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(og.resolve_approver_node)))
    rung = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_names_one_of_us")
    called = {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
              for n in ast.walk(rung) if isinstance(n, ast.Call)}
    assert "identity_for" in called, "the name rung does not ask platform/self_identity"
    # The docstring is prose about the rung, not a statement it runs — never measured as SQL.
    first = rung.body[0] if rung.body else None
    docstring = first.value if (isinstance(first, ast.Expr)
                                and isinstance(first.value, ast.Constant)) else None
    sql = [n.value for n in ast.walk(rung)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and n is not docstring]
    assert not [s for s in sql if "org_seats" in s or "external_account_id" in s], (
        "the name rung still carries its own copy of the tenant identity SQL")
