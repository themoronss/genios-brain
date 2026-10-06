"""STEP-04 · U05 — quote attribution counts every address of ours.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_quote_attribution_reads_the_identity.py -q

`deliver/card_builder.load_evidence_quotes` marks a quote `from_counterparty` unless its author is
one of the tenant's own addresses — and the addresses it is handed are `deliver/pipeline.
_tenant_identities`. That read `orgs` and the active seats only, so a sentence the founder wrote
from his connected mailbox, or from the address he declared his own (`ceo@thegenios.com`,
`org_self_identities`, migration 0193), was printed on a card as the COUNTERPARTY's words.

It reads the one answer now — `platform/self_identity.identity_for(...).addresses` (tree
`yc2_w27_s04/M22.C2.L-logic.V2.U05`); the names it adds for the render's grounding corpus stay.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import textwrap
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver import pipeline
from genios_engine.deliver.card_builder import load_evidence_quotes

pytestmark = pytest.mark.pg
ORG = "s04_quote_attribution"
OURS = {"founder.s04quotes@gmail.com",     # orgs.email (stored as Founder.S04Quotes@gmail.com)
        "harsh@thegenios.com",             # an active seat
        "founder.mailbox@gmail.com",       # a connected account
        "ceo@thegenios.com"}               # a declared address
QUOTE = "Can you send the signed term sheet by Friday?"


@pytest.fixture
def graph():
    """The tenant on real Postgres: every source "who is us" is read from, and a deactivated seat."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        # `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
        c.execute(text("insert into orgs (id, name, first_name, last_name, email, company) values "
                       "(:o, 'GeniOS', 'Rohit', 'Swerashi', 'Founder.S04Quotes@gmail.com', "
                       "'GeniOS Labs')"), {"o": ORG})
        c.execute(text("insert into org_seats (org_id, seat_id, email, active) values "
                       "(:o, 'seat_s04_harsh', 'harsh@thegenios.com', true), "
                       "(:o, 'seat_s04_gone', 'left@oldco.test', false)"), {"o": ORG})
        c.execute(text("insert into connections (connection_id, org_id, external_account_id) "
                       "values ('conn_s04_quote_attribution', :o, 'Founder.Mailbox@gmail.com')"),
                  {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', 'ceo@thegenios.com', 'test'), "
                       "(:o, 'domain', 'thegenios.com', 'test')"), {"o": ORG})
    yield SimpleNamespace(engine=engine)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    engine.dispose()


def _quote_by(author: str):
    """One verified quote on a person node, written by `author` — the loader's own tables."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for sql in (
            "create table graph_nodes (org_id text,node_id text,node_type text,canonical_key text,"
            "valid_to text)",
            "create table graph_edges (org_id text,from_node_id text,to_node_id text,"
            "edge_type text,valid_to text)",
            "create table graph_observations (org_id text,observation_id text,"
            "subject_node_id text,created_by_event_id text,kind text,occurred_at text,status text)",
            "create table graph_source_refs (org_id text,observation_id text,event_id text,"
            "evidence text)",
            "create table source_events (org_id text,event_id text,parent_object_id text,"
            "actor text,visibility_scope text,visibility_principals text)",
            "create table prepared_content (org_id text,event_id text,clean_text text)",
        ):
            c.execute(text(sql))
        c.execute(text("insert into graph_nodes values ('o','p','person','priya@acme.test',null)"))
        c.execute(text("insert into graph_observations values "
                       "('o','obs','p','e','request','2026-10-01T12:00:00+00:00','active')"))
        c.execute(text("insert into graph_source_refs values ('o','obs','e',:evidence)"),
                  {"evidence": json.dumps({"text": QUOTE})})
        c.execute(text("insert into source_events values ('o','e',null,:actor,'org','[]')"),
                  {"actor": json.dumps({"email": author})})
        c.execute(text("insert into prepared_content values ('o','e',:body)"),
                  {"body": "Subject: terms\n" + QUOTE})
    return SimpleNamespace(engine=engine)


def _addresses(identities) -> set[str]:
    return {str(i).strip().lower() for i in identities if "@" in str(i)}


def test_every_address_of_ours_is_an_identity(graph):
    assert OURS <= _addresses(pipeline._tenant_identities(graph, ORG))


def test_a_deactivated_seat_is_not_an_identity(graph):
    assert "left@oldco.test" not in _addresses(pipeline._tenant_identities(graph, ORG))


def test_the_names_it_adds_stay(graph):
    """The render's grounding corpus still knows the founder's own names ("Best, Rohit")."""
    assert {"GeniOS", "Rohit", "Swerashi", "GeniOS Labs"} <= set(
        pipeline._tenant_identities(graph, ORG))


@pytest.mark.parametrize("author", ["ceo@thegenios.com", "founder.mailbox@gmail.com"])
def test_a_quote_we_wrote_is_never_the_counterpartys(graph, author):
    """A declared address and the connected mailbox wrote it: the card may not say they did."""
    [quote] = load_evidence_quotes(_quote_by(author), "o", "p",
                                   identities=pipeline._tenant_identities(graph, ORG))
    assert quote["from_counterparty"] is False, f"{author} is ours and was quoted as the other side"


def test_a_quote_the_counterparty_wrote_is_still_theirs(graph):
    [quote] = load_evidence_quotes(_quote_by("priya@acme.test"), "o", "p",
                                   identities=pipeline._tenant_identities(graph, ORG))
    assert quote["from_counterparty"] is True


def test_an_unreadable_identity_is_no_identity_not_a_failure():
    """Grounding is an enrichment, never a reason to fail the build."""
    assert pipeline._tenant_identities(SimpleNamespace(engine=create_engine("sqlite://")),
                                       ORG) == ()


def test_the_addresses_are_the_one_answer():
    """`_tenant_identities` reads `identity_for`; it keeps no seats query of its own."""
    fn = ast.parse(textwrap.dedent(inspect.getsource(pipeline._tenant_identities))).body[0]
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "identity_for" in called, "_tenant_identities does not ask platform/self_identity"
    # The docstring is prose about the function, not a statement it runs — never measured as SQL.
    first = fn.body[0]
    docstring = first.value if (isinstance(first, ast.Expr)
                                and isinstance(first.value, ast.Constant)) else None
    sql = [n.value for n in ast.walk(fn)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and n is not docstring]
    assert not [s for s in sql if "org_seats" in s], (
        "_tenant_identities still carries its own copy of the tenant identity SQL")
