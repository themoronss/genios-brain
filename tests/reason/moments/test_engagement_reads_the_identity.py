"""STEP-04 · U11 — "several of us touched one company" never counts our own company.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/moments/test_engagement_reads_the_identity.py -q

`reason/moments/engagement.touches` finds the companies two seats both touched (P-13 duplicate
outreach, the slice's `other_seats`) and drops our own company by its domain. "Our domains" were
every seat's and `orgs.email`'s mail domain, with no public-mail guard: for a Gmail founder and a
Gmail co-founder that is `gmail.com`, while the company's real domain (`thegenios.com`, declared in
`org_self_identities`, migration 0193) was a counterparty both of them "touched".

It reads the DECLARED domains of the one answer now — `platform/self_identity.identity_for(...)
.domains`, which never holds a public mail domain (tree `yc2_w27_s04/M22.C2.L-logic.V2.U11`).
"""
from __future__ import annotations

import ast
import inspect
import itertools
import json
import os
import textwrap
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.reason.moments import engagement

pytestmark = pytest.mark.pg
ORG = "s04_engagement_us"
#: `orgs.email` is UNIQUE across the scratch database: an address no other test seeds.
OWNER = "Founder.S04Engage@gmail.com"
CONNECTION = "conn_s04_engagement_us"           # org-wide: a touch is attributed by its sender
NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
SEATS = {"seat_s04_founder": "founder.s04engage@gmail.com",
         "seat_s04_cofounder": "cofounder.s04engage@gmail.com"}
#: `graph_nodes` is keyed on (node_id, version) across every org: ids no other test seeds.
OUR_COMPANY, THEIR_COMPANY = "nd_s04_engage_our_company", "nd_s04_engage_acme"
_IDS = itertools.count()


@pytest.fixture
def conn():
    """A real-Postgres transaction, rolled back: two Gmail seats who both wrote about their own
    company (`thegenios.com`, declared) and about a counterparty (`acme.test`) this week."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    c = engine.connect()
    tx = c.begin()
    c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
              {"o": ORG, "e": OWNER})
    c.execute(text("insert into connections (connection_id, org_id) values (:c, :o)"),
              {"c": CONNECTION, "o": ORG})
    for seat_id, email in SEATS.items():
        c.execute(text("insert into org_seats (org_id, seat_id, email, active) "
                       "values (:o, :s, :e, true)"), {"o": ORG, "s": seat_id, "e": email})
    c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                   "(:o, 'domain', 'thegenios.com', 'test'), (:o, 'domain', 'gmail.com', 'a mistake')"),
              {"o": ORG})
    for node_id, key, name in ((OUR_COMPANY, "thegenios.com", "GeniOS"),
                               (THEIR_COMPANY, "acme.test", "Acme")):
        c.execute(text("insert into graph_nodes (org_id, node_id, node_type, canonical_key, "
                       "display_name) values (:o, :n, 'company', :k, :d)"),
                  {"o": ORG, "n": node_id, "k": key, "d": name})
    for day, email in enumerate(SEATS.values(), start=1):
        for company in (OUR_COMPANY, THEIR_COMPANY):
            _touch(c, email, company, NOW - timedelta(days=day))
    try:
        yield c
    finally:
        tx.rollback()
        c.close()
        engine.dispose()


def _touch(c, sender: str, company: str, at: datetime) -> None:
    """An org-visible message `sender` wrote, and the observation it left on `company`."""
    n = next(_IDS)
    event_id, observation_id = f"evt_s04_engage_{n}", f"obs_s04_engage_{n}"
    c.execute(text("insert into source_events (event_id, org_id, connection_id, source, "
                   "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                   "(:e, :o, :c, 'gmail', 'email_message', :e, :e, cast(:a as jsonb), :t)"),
              {"e": event_id, "o": ORG, "c": CONNECTION, "a": json.dumps({"email": sender}),
               "t": at})
    c.execute(text("insert into graph_observations (observation_id, org_id, kind, "
                   "subject_node_id) values (:b, :o, 'note', :n)"),
              {"b": observation_id, "o": ORG, "n": company})
    c.execute(text("insert into graph_source_refs (source_ref_id, org_id, event_id, "
                   "observation_id) values (:r, :o, :e, :b)"),
              {"r": f"ref_s04_engage_{n}", "o": ORG, "e": event_id, "b": observation_id})


def test_our_domains_are_the_declared_ones_and_never_a_public_one(conn):
    assert engagement.internal_domains(conn, ORG) == ["thegenios.com"]


def test_several_of_us_touching_our_own_company_is_not_outreach(conn):
    touched = engagement.touches(conn, ORG, now=NOW)
    assert OUR_COMPANY not in touched, (
        "thegenios.com is ours and two seats touching it read as duplicate outreach")


def test_several_of_us_touching_a_counterparty_still_is(conn):
    """The negative control: the witness does see a company two of us touched."""
    touched = engagement.touches(conn, ORG, now=NOW)
    assert set(touched.get(THEIR_COMPANY, {}).get("seats", {})) == set(SEATS), touched


def test_our_domains_are_the_one_answer():
    """`internal_domains` reads `identity_for`; no seat- or org-domain query of its own."""
    fn = ast.parse(textwrap.dedent(inspect.getsource(engagement.internal_domains))).body[0]
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "identity_for" in called, "internal_domains does not ask platform/self_identity"
    # The docstring is prose about the function, not a statement it runs — never measured as SQL.
    first = fn.body[0]
    docstring = first.value if (isinstance(first, ast.Expr)
                                and isinstance(first.value, ast.Constant)) else None
    sql = [n.value for n in ast.walk(fn)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and n is not docstring]
    assert not [s for s in sql if "org_seats" in s or "split_part" in s], (
        "internal_domains still derives our domains from mail addresses itself")
