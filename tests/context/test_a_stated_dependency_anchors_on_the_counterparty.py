"""A statement nobody could resolve is anchored on the COUNTERPARTY, chosen by content.

    pytest tests/context/test_a_stated_dependency_anchors_on_the_counterparty.py -q

⛔ WHAT WAS WRONG. `correlation_dependency.event_parties` answers "whose conversation was this said
in" with "sorted and first" — over node ids. Node ids are minted at random (`platform/ids.new_id`),
so "sorted" was a coin toss per tenant: two identical runs of the founder's own sent offer anchored
its stated dependency on two different people, and one of them was the founder himself — the
account holder presented as the counterparty of his own mail ("Stated in the Arjun Rao thread").
Found driving the golden case F25 (yc2_w27/M19): one run's decider saw the candidate's thread, the
next saw the founder's, and a recorded case could not be replayed.

Now: the tenant's own addresses are passed over whenever anyone else is in the thread, and the
remaining parties are ordered by their canonical key — content, never a minted id.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text

from genios_engine.context.correlation_dependency import event_parties


def _conn(parties):
    """An event with the given (node_id, canonical_key) parties, in insertion order."""
    engine = create_engine("sqlite://")
    c = engine.connect()
    for sql in ("create table graph_source_refs (org_id text, event_id text, fact_version_id text)",
                "create table graph_facts (org_id text, fact_version_id text, "
                "subject_node_id text, status text)",
                "create table graph_nodes (org_id text, node_id text, node_type text, "
                "canonical_key text, valid_to text)"):
        c.execute(text(sql))
    for n, (node_id, key) in enumerate(parties):
        c.execute(text("insert into graph_source_refs values ('o','evt_1',:fv)"), {"fv": f"fv{n}"})
        c.execute(text("insert into graph_facts values ('o',:fv,:node,'active')"),
                  {"fv": f"fv{n}", "node": node_id})
        c.execute(text("insert into graph_nodes values ('o',:node,'person',:key,null)"),
                  {"node": node_id, "key": key})
    return c


def test_the_party_is_chosen_by_content_not_by_a_minted_id():
    """Same two people, ids minted the other way round: the same person is chosen."""
    one = event_parties(_conn([("node_aaa", "kavitha@x.test"), ("node_zzz", "ravi@x.test")]), "o")
    two = event_parties(_conn([("node_zzz", "kavitha@x.test"), ("node_aaa", "ravi@x.test")]), "o")
    assert one == {"evt_1": "node_aaa"} and two == {"evt_1": "node_zzz"}, (one, two)


def test_the_tenant_is_never_the_counterparty_when_anyone_else_is_in_the_thread():
    """The founder sorts first by address and by id, and is still passed over."""
    got = event_parties(_conn([("node_aaa", "arjun@nimbuslabs.test"),
                               ("node_bbb", "kavitha@inboxmail.test")]), "o",
                        us=frozenset({"arjun@nimbuslabs.test"}))
    assert got == {"evt_1": "node_bbb"}


def test_a_thread_with_only_the_tenant_keeps_its_anchor():
    """Nobody else to anchor on: the statement keeps the one party it has, as before."""
    got = event_parties(_conn([("node_aaa", "arjun@nimbuslabs.test")]), "o",
                        us=frozenset({"arjun@nimbuslabs.test"}))
    assert got == {"evt_1": "node_aaa"}
