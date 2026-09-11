"""The alias table pointed at a graph that no longer existed, and nothing could resolve a name.

    pytest tests/context/test_an_alias_may_outlive_the_node_it_named.py -q

MEASURED READ-ONLY ON THE PILOT, 2026-09-11. Of 364 aliases, **309 resolved to a node with no row
at any version**:

    email         116 total, 107 dangling
    person_name    89 total,  87 dangling
    company_name  107 total,  78 dangling
    domain         52 total,  37 dangling

THE MECHANISM, in three parts that are each individually reasonable. `node_id` is minted per node
(`graph_store` calls `new_id("node")`). The account erasure list clears `graph_nodes`,
`graph_facts`, `graph_edges`, `graph_observations` and `graph_source_refs` — and did not clear
`graph_aliases`. And `record_alias` inserted `on conflict … do nothing`, so a key already present
was never revisited. Rebuild a tenant's graph once and the alias table is frozen against the
first graph that ever existed.

WHAT IT COST. `resolve_company_mention("Antler")` returned `node_8f37…`; the caller's type check
found no live node of that id and dropped the claim. `_business_subject` is deliberately strict —
*"Exact existing typed subject only. The old sender fallback misfiled all nine nouns"* — so a dead
holder is silently fatal to every business noun about a named person or company. That is why
`party.role` holds ONE fact across the whole graph and `company.industry` none: not an extractor
that cannot read them, a subject that cannot resolve.

THE FIX IS A DISTINCTION, NOT A LOOSENING. A key held by a node that no longer exists is
UNOWNED — there is no claimant to overwrite. A key held by a LIVE node is a real duplicate and
still refuses, because picking one silently moves every fact written from that mention onto the
wrong person. Both halves are pinned below.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.identity import record_alias, resolve_alias

pytestmark = pytest.mark.unit

ORG = "org1"
KEY = ("company_name", "antler")


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_aliases (org_id text, alias_type text, "
                       "alias_key text, node_id text, origin text, created_by_event_id text, "
                       "primary key (org_id, alias_type, alias_key))"))
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "canonical_key text, display_name text, valid_to timestamp)"))
        yield c


def live(conn, node_id: str, *, node_type: str = "company") -> None:
    conn.execute(text("insert into graph_nodes values (:o,:n,:t,:n,:n,null)"),
                 {"o": ORG, "n": node_id, "t": node_type})


def claim(conn, node_id: str) -> str | None:
    return record_alias(conn, org_id=ORG, node_id=node_id,
                        alias_type=KEY[0], alias_key=KEY[1], origin="anchor")


# =============================================================================================
# The correction: a key whose holder is gone is unowned.
# =============================================================================================
def test_a_key_held_by_a_node_that_no_longer_exists_is_taken_over():
    """THE 309. The graph was rebuilt, the aliases survived it, and every name pointed at a
    node id nothing had minted since."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_aliases (org_id text, alias_type text, "
                       "alias_key text, node_id text, origin text, created_by_event_id text, "
                       "primary key (org_id, alias_type, alias_key))"))
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "canonical_key text, display_name text, valid_to timestamp)"))
        c.execute(text("insert into graph_aliases values (:o,:t,:k,'node_dead','anchor',null)"),
                  {"o": ORG, "t": KEY[0], "k": KEY[1]})
        live(c, "node_new")

        assert claim(c, "node_new") is None, "an unowned key is claimed, not refused"
        assert resolve_alias(c, org_id=ORG, alias_type=KEY[0], alias_key=KEY[1]) == "node_new"


def test_a_live_holder_still_refuses_a_second_claimant(conn):
    """THE GUARD, UNTOUCHED. Two live nodes called the same thing is a real collision — two
    "John"s at different companies is ordinary — and picking one moves every fact written from
    that mention onto the wrong person."""
    live(conn, "node_first")
    live(conn, "node_second")
    assert claim(conn, "node_first") is None

    assert claim(conn, "node_second") == "node_first", "the duplicate is reported, not merged"
    assert resolve_alias(conn, org_id=ORG, alias_type=KEY[0], alias_key=KEY[1]) == "node_first"


def test_the_same_node_claiming_twice_is_still_a_no_op(conn):
    live(conn, "node_a")

    assert claim(conn, "node_a") is None
    assert claim(conn, "node_a") is None
    assert resolve_alias(conn, org_id=ORG, alias_type=KEY[0], alias_key=KEY[1]) == "node_a"


def test_a_free_key_is_claimed(conn):
    live(conn, "node_a")

    assert claim(conn, "node_a") is None


def test_a_superseded_holder_counts_as_gone(conn):
    """`valid_to` is how this graph retires a version. A retired holder owns nothing: the live
    read every consumer performs would find no node, so leaving the key with it is leaving it
    unresolvable."""
    conn.execute(text("insert into graph_nodes values (:o,'node_old','company','x','x',"
                      "'2026-01-01')"), {"o": ORG})
    conn.execute(text("insert into graph_aliases values (:o,:t,:k,'node_old','anchor',null)"),
                 {"o": ORG, "t": KEY[0], "k": KEY[1]})
    live(conn, "node_current")

    assert claim(conn, "node_current") is None
    assert resolve_alias(conn, org_id=ORG, alias_type=KEY[0], alias_key=KEY[1]) == "node_current"


def test_taking_over_a_dead_key_does_not_disturb_another(conn):
    """One key, one decision. A takeover must not touch a neighbouring alias."""
    conn.execute(text("insert into graph_aliases values (:o,:t,:k,'node_dead','anchor',null)"),
                 {"o": ORG, "t": KEY[0], "k": KEY[1]})
    conn.execute(text("insert into graph_aliases values (:o,'company_name','peakxv',"
                      "'node_peak','anchor',null)"), {"o": ORG})
    live(conn, "node_new")
    live(conn, "node_peak")

    claim(conn, "node_new")

    assert resolve_alias(conn, org_id=ORG, alias_type="company_name",
                         alias_key="peakxv") == "node_peak"


# =============================================================================================
# The sweep, because the takeover is lazy by nature.
# =============================================================================================
def test_the_sweep_removes_a_key_whose_node_is_gone(conn):
    """`record_alias` repairs a key the moment something mentions it again — which never comes
    for a person nobody writes about twice. 309 of 364 live aliases were in that state."""
    from genios_engine.context.identity import prune_dead_aliases

    live(conn, "node_live")
    conn.execute(text("insert into graph_aliases values (:o,'company_name','dead',"
                      "'node_gone','anchor',null)"), {"o": ORG})
    conn.execute(text("insert into graph_aliases values (:o,'company_name','alive',"
                      "'node_live','anchor',null)"), {"o": ORG})

    assert prune_dead_aliases(conn) == 1
    assert resolve_alias(conn, org_id=ORG, alias_type="company_name", alias_key="dead") is None
    assert resolve_alias(conn, org_id=ORG, alias_type="company_name",
                         alias_key="alive") == "node_live"


def test_the_sweep_is_idempotent(conn):
    """It rides the heartbeat, so it runs on every tick for every tenant and must be free on one
    with nothing to clean."""
    from genios_engine.context.identity import prune_dead_aliases

    live(conn, "node_live")
    conn.execute(text("insert into graph_aliases values (:o,'company_name','dead',"
                      "'node_gone','anchor',null)"), {"o": ORG})

    assert prune_dead_aliases(conn) == 1
    assert prune_dead_aliases(conn) == 0


def test_the_sweep_deletes_rather_than_guessing_a_new_owner(conn):
    """Repointing would be exactly the silent re-attribution `resolve_person_name` refuses — "a
    name shared by several anchored people resolves to NOBODY, not to the first claimant".
    Removal leaves the key free, and the next real observation claims it with evidence."""
    from genios_engine.context.identity import prune_dead_aliases

    live(conn, "node_a", node_type="person")
    live(conn, "node_b", node_type="person")
    conn.execute(text("insert into graph_aliases values (:o,'person_name','john',"
                      "'node_gone','anchor',null)"), {"o": ORG})

    prune_dead_aliases(conn)

    assert resolve_alias(conn, org_id=ORG, alias_type="person_name", alias_key="john") is None


def test_the_sweep_rides_the_heartbeat():
    import inspect

    from genios_engine.api import routes

    src = inspect.getsource(routes.run_maintenance_sweep)

    assert "prune_dead_aliases" in src


# =============================================================================================
# And the state stops being created.
# =============================================================================================
def test_the_erasure_list_clears_aliases_with_the_graph_they_describe():
    """`node_id` is minted per node, so clearing `graph_nodes` and leaving `graph_aliases`
    standing leaves every key pointing at a graph that no longer exists. The self-heal above
    repairs an existing tenant; this stops the state being made again."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "graph_aliases" in _ORG_SCOPED_TABLES
    assert _ORG_SCOPED_TABLES.index("graph_aliases") < _ORG_SCOPED_TABLES.index("graph_nodes"), (
        "aliases reference nodes, so they are cleared before the rows they point at")
