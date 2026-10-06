"""STEP-04 · the naming sweep's party is never one of us.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_the_naming_sweep_skips_us.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U18`. `context/backfill.name_thread_nodes` — the heartbeat's
pass over every tenant's threads (`api/routes` calls it with no org) — names a conversation after the
person on its OLDEST `corresponded_with` edge, filtered on `node_type = 'person'` and nothing else.
The pipeline writes those edges only for addresses outside the self set AT WRITE TIME, so an address
declared later, or a colleague known only by a declared domain, is a correspondent, and the sweep
named the conversation after us — a label nothing ever renames.

Now the party is the oldest correspondent who is not one of us, by the identity of the thread's own
tenant (`platform/self_identity.identity_for`); a conversation with nobody else in it is named by
what it is for alone.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.backfill import name_thread_nodes

pytestmark = pytest.mark.pg

ORG = "naming_sweep_skips_us_org"
OTHER = "naming_sweep_other_org"             # a second tenant, for whom DECLARED is a stranger
FOUNDER = "founder.sweep@gmail.com"
DECLARED, DECLARED_NAME = "ceo@nimbussweep.test", "Mr Founder Second"
COLLEAGUE, COLLEAGUE_NAME = "ops@nimbussweep.test", "Ops Colleague"   # at the declared domain only
INVESTOR, INVESTOR_NAME = "priya@northwind.test", "Priya Sharma"
EARLY = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATE = datetime(2026, 6, 1, tzinfo=timezone.utc)
GENERATED = "Thread 1a07a6e0ca77"            # a label the engine wrote, so the sweep may improve it


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        for org in (ORG, OTHER):
            _wipe(c, org)
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e), (:x, :x, :y)"),
                  {"o": ORG, "e": FOUNDER, "x": OTHER, "y": "someone.else@gmail.com"})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'address', :a, 'test'), (:o, 'domain', 'nimbussweep.test', 'test')"),
                  {"o": ORG, "a": DECLARED})
    yield pg_store
    _reset(pg_store)


def _thread(store, *, org: str, node_id: str, objective: str | None,
            parties: list[tuple[str, str, datetime]]) -> str:
    """A thread the pipeline would have left behind: a generated label, the objective L1 stated,
    and a `corresponded_with` edge from each party, oldest first."""
    with store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key, "
                       "display_name) values (:n, :o, 'thread', :k, :d)"),
                  {"n": node_id, "o": org, "k": f"thread:{node_id}", "d": GENERATED})
        for i, (key, name, at) in enumerate(parties):
            person = c.execute(text("select node_id from graph_nodes where org_id = :o "
                                    "and canonical_key = :k and valid_to is null"),
                               {"o": org, "k": key}).scalar()
            if person is None:
                person = f"{node_id}_p{i}"
                c.execute(text("insert into graph_nodes (node_id, org_id, node_type, "
                               "canonical_key, display_name) values (:n, :o, 'person', :k, :d)"),
                          {"n": person, "o": org, "k": key, "d": name})
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                           "from_node_id, to_node_id, created_at) "
                           "values (:v, :v, :o, 'corresponded_with', :p, :t, :at)"),
                      {"v": f"{node_id}_e{i}", "o": org, "p": person, "t": node_id, "at": at})
        if objective:
            store.write_fact(c, org_id=org, subject_node_id=node_id, field="thread.objective",
                             value=objective, value_type="string", confidence=0.9,
                             occurred_at=EARLY, event_id=f"evt_{node_id}",
                             evidence={"text": objective}, source="gmail", authority_rank=1)
    return node_id


def _label(store, node_id: str) -> str:
    with store.engine.connect() as c:
        return c.execute(text("select display_name from graph_nodes where node_id = :n "
                              "and valid_to is null"), {"n": node_id}).scalar()


def test_the_oldest_correspondent_who_is_not_us_names_it(store):
    """Our declared second address wrote first; the investor is the other side."""
    node = _thread(store, org=ORG, node_id="u18_declared_first", objective="intro call",
                   parties=[(DECLARED, DECLARED_NAME, EARLY), (INVESTOR, INVESTOR_NAME, LATE)])
    name_thread_nodes(store, ORG)
    assert _label(store, node) == f"{INVESTOR_NAME} — intro call", "named after us"


def test_a_colleague_at_our_domain_is_us_too(store):
    """Known only by the declared domain, and still one of us."""
    node = _thread(store, org=ORG, node_id="u18_colleague_first", objective="intro call",
                   parties=[(COLLEAGUE, COLLEAGUE_NAME, EARLY), (INVESTOR, INVESTOR_NAME, LATE)])
    name_thread_nodes(store, ORG)
    assert _label(store, node) == f"{INVESTOR_NAME} — intro call", "named after us"


def test_a_thread_with_nobody_else_is_named_by_what_it_is_for(store):
    node = _thread(store, org=ORG, node_id="u18_only_us", objective="board prep",
                   parties=[(DECLARED, DECLARED_NAME, EARLY)])
    name_thread_nodes(store, ORG)
    assert _label(store, node) == "board prep", "named after us"


def test_each_tenant_is_asked_about_itself(store):
    """The heartbeat sweeps every tenant at once. `ceo@nimbussweep.test` is ours for ORG and a
    stranger for OTHER — each thread is judged by its own tenant's identity. (Node ids sort first,
    so the bounded all-tenant sweep reaches exactly these two.)"""
    ours = _thread(store, org=ORG, node_id="0u18_sweep_a", objective="intro call",
                   parties=[(DECLARED, DECLARED_NAME, EARLY), (INVESTOR, INVESTOR_NAME, LATE)])
    theirs = _thread(store, org=OTHER, node_id="0u18_sweep_b", objective="intro call",
                     parties=[(DECLARED, DECLARED_NAME, EARLY)])
    assert name_thread_nodes(store, limit=2) == 2
    assert _label(store, ours) == f"{INVESTOR_NAME} — intro call"
    assert _label(store, theirs) == f"{DECLARED_NAME} — intro call"
