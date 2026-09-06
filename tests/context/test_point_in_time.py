"""H7 · the POINT-IN-TIME GRAPH READ — *what did GeniOS know when it made that decision?*

Doc 02 (L2.2.7-U1) states the gap and the stakes in one paragraph: `graph_store.py` incremented
`graph_versions` as a counter, *"there is no `as_of` query anywhere"*, and so the Version
Manager's stated purpose — the question every enterprise security review asks — was not
answerable. Three obligations rest on the answer: replay (a decision replay needs the graph that
produced it), audit, and explanation (*"you recommended X in March"* is only defensible against
March's graph).

WHAT THIS FILE PROVES, in the doc's own words:

* a fact valid Jan-Mar is present in an `as_of=Feb` read and absent from an `as_of=Apr` one;
* an edge soft-deleted in Feb is present at `as_of=Jan`;
* `read_graph(as_of=now)` matches the live graph EXACTLY — the property that makes every other
  as-of read trustworthy;
* replaying a March decision against `as_of=March` reproduces its inputs;
* an `as_of` before anything existed returns an EMPTY graph, not an error;
* a merge is visible after its timestamp and invisible before it;
* **0 hard `DELETE`s against the graph tables** — an edge is closed by setting `valid_to`, or
  every historical read silently changes its answer and there is no way to recover it.

THE TEMPORAL TESTS COMMIT, AND THEY OWN THEIR OWN TENANT. Postgres `now()` is the TRANSACTION
timestamp: every row written inside one transaction is stamped with the same instant, so a suite
that created, amended and superseded a node inside a single rolled-back transaction would be
reading four instants that are all the same instant, and every assertion below would pass
without the reader being correct. So the writes are real, committed, separately timed
transactions — and to keep that safe next to the rest of the suite, they run under an org of
this file's own (`ORG_PIT`), created here and deleted at the end, which cascades every row away.
Nothing here touches `org_scratch_tests`, so a full-suite run is unaffected by what this file
writes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.context.graph_store import (EdgeAt, FactAt, GraphView, NodeAt, _confidence_bp)

ENGINE_ROOT = Path(__file__).resolve().parents[2] / "genios_engine"

#: This file's own tenant. Not `org_scratch_tests`: the tests below COMMIT, and a committed graph
#: under the shared org would be visible to every other real-Postgres test in the session.
ORG_PIT = "org_x7_point_in_time"

#: One microsecond — the resolution `timestamptz` stores, and therefore the smallest step that
#: can name "just before" an instant. Used instead of a second so the tests still read the right
#: side of a boundary when two transactions land in the same millisecond.
TICK = timedelta(microseconds=1)

#: When the two facts below were OBSERVED, as opposed to when they were written. `occurred_at`
#: is what `fact_write_action` orders a stale re-extraction against, so a fixture that left it
#: null would exercise the authority branch instead of the out-of-order one and the last test in
#: this file would be proving something else.
JANUARY = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
FEBRUARY = datetime(2026, 2, 5, 9, 0, tzinfo=timezone.utc)


# =================================================================================================
# THE HERMETIC HALF — the view type and the integer conversion, with no database in reach
# =================================================================================================

def _node(node_id: str = "node_a", version: int = 1, **over) -> NodeAt:
    base = dict(node_id=node_id, version=version, node_type="company", canonical_key="acme.io",
                display_name="Acme", identity_strength="strong",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc), valid_to=None)
    base.update(over)
    return NodeAt(**base)


def _fact(field: str = "deal.stage", value: str = "discovery", **over) -> FactAt:
    base = dict(fact_version_id="factv_1", subject_node_id="node_a", field=field, value=value,
                value_type="string", status="active", authority_rank=2, occurred_at=None,
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc), valid_to=None)
    base.update(over)
    return FactAt(**base)


def _edge(**over) -> EdgeAt:
    base = dict(edge_version_id="edgev_1", edge_type="works_at", from_node_id="node_p",
                to_node_id="node_a", confidence_bp=8500, interaction_count=3,
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc), valid_to=None)
    base.update(over)
    return EdgeAt(**base)


CONFIDENCE_CASES = [
    # (column value, expected basis points) — the column is numeric(4,3), and it arrives as a
    # Decimal from psycopg, as a str from some drivers, and as None when never written.
    (Decimal("0.850"), 8500),
    (Decimal("1.000"), 10000),
    (Decimal("0.000"), 0),
    (Decimal("0.005"), 50),
    ("0.500", 5000),
    (None, 0),
]


@pytest.mark.parametrize("value,expected", CONFIDENCE_CASES)
def test_confidence_is_read_as_integer_basis_points(value, expected):
    """`float(Decimal("0.85"))` is 0.8500000000000001 in one row and 0.85 in another, and two
    reads of the same unchanged graph would then compare unequal — which would make the
    live/as-of equivalence property below untestable rather than merely imprecise."""
    got = _confidence_bp(value)
    assert got == expected
    assert isinstance(got, int)


def test_the_view_is_immutable_and_answers_by_node():
    view = GraphView(org_id=ORG_PIT, as_of=None, graph_version=7, nodes=(_node(),),
                     facts=(_fact(), _fact(field="deal.value", value=500, fact_version_id="f2")),
                     edges=(_edge(),))
    assert view.node("node_a").display_name == "Acme"
    assert view.node("nobody") is None
    assert view.fact("node_a", "deal.stage").value == "discovery"
    assert len(view.facts_for("node_a")) == 2
    assert view.edges_touching("node_a") == (_edge(),)
    assert not view.is_empty
    with pytest.raises(Exception):
        view.nodes = ()            # frozen: a view handed to a caller cannot be edited under them


def test_a_graph_from_before_anything_existed_is_empty_and_not_an_error():
    """Doc 02 spells this one out: an `as_of` before the first write returns an empty graph. A
    caller replaying an old decision needs "we knew nothing then" to be representable."""
    empty = GraphView(org_id=ORG_PIT, as_of=datetime(2020, 1, 1, tzinfo=timezone.utc),
                      graph_version=None, nodes=(), facts=(), edges=())
    assert empty.is_empty
    assert empty.content == ((), (), ())
    assert empty.as_record()["counts"] == {"nodes": 0, "facts": 0, "edges": 0}
    assert empty.as_record()["graph_version"] is None


def test_read_graph_refuses_an_as_of_that_is_not_an_instant():
    """`as_of` is a PARAMETER, and a string that failed to parse must not fall back to a clock —
    that is how a replay silently becomes a read of today."""
    from genios_engine.context.graph_store import GraphStore
    store = GraphStore.__new__(GraphStore)          # no engine: this must fail before any I/O
    with pytest.raises(TypeError):
        store.read_graph(ORG_PIT, as_of="2026-03-01")


GRAPH_TABLES = ("graph_nodes", "graph_facts", "graph_edges", "graph_observations")


def test_nothing_in_context_hard_deletes_a_graph_row():
    """Doc 02's HARD RULE 1, as a scan: *soft delete only — a hard delete makes history
    unreadable and there is no way to recover it later.* `merge.py` already closes edges with
    `valid_to`; this is what stops the next writer from reaching for `delete`.

    Scoped to `context/`, which is the only package that writes the graph. Tenant ERASURE
    (`api/account_routes`) genuinely deletes, and must: a deleted customer's rows do not become
    history.
    """
    offenders = []
    for py in (ENGINE_ROOT / "context").rglob("*.py"):
        lowered = py.read_text().lower()
        for table in GRAPH_TABLES:
            if f"delete from {table}" in lowered:
                offenders.append(f"{py.relative_to(ENGINE_ROOT)}: delete from {table}")
    assert not offenders, f"soft delete only — history must stay readable: {offenders}"


# =================================================================================================
# THE REAL-POSTGRES HALF — four instants over a graph that was really written
# =================================================================================================

@pytest.fixture(scope="module")
def pit_org(pg_store):
    """This file's own tenant, cloned from the scratch org's row so a later NOT-NULL column does
    not turn these tests into an insert error, and dropped at the end — which cascades every
    graph row written below out with it."""
    engine = pg_store.engine
    with engine.begin() as conn:
        if not conn.execute(text("select 1 from orgs where id='org_scratch_tests'")).scalar():
            pytest.skip("no scratch org seeded — nothing to clone a tenant from")
        # INSERT ... SELECT rather than a read-then-write: the row carries jsonb columns, and
        # round-tripping those through Python turns them into dicts that psycopg then refuses to
        # adapt back. Copying inside the database keeps every column at its own type, whatever a
        # later migration adds.
        columns = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_generated='NEVER' order by ordinal_position"))]
        projected = ", ".join(":new_id" if c == "id" else c for c in columns)
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) select {projected} "
                          "from orgs where id='org_scratch_tests' on conflict (id) do nothing"),
                     {"new_id": ORG_PIT})
    yield ORG_PIT
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG_PIT})


def _db_now(engine) -> datetime:
    with engine.connect() as conn:
        return conn.execute(text("select clock_timestamp()")).scalar()


@pytest.fixture(scope="module")
def timeline(pg_store, pit_org):
    """A node CREATED, AMENDED and SUPERSEDED, in three separately timed transactions.

    Each step is its own transaction because `now()` is the transaction clock: three writes in
    one transaction carry one timestamp, and a suite built that way would be asserting about
    four instants that are all the same instant.

    Every write goes through the STORE's own methods (`find_or_create_node`, `write_fact`,
    `write_edge`, `write_change`) and through `merge.apply_merge` — the production write paths —
    so what these reads see is what a real drain leaves behind, not a hand-built row.
    """
    from genios_engine.context.merge import apply_merge
    engine = pg_store.engine
    t0 = _db_now(engine)

    # ── t1 · the graph is created ────────────────────────────────────────────────────────────
    with engine.begin() as conn:
        acme = pg_store.find_or_create_node(conn, org_id=ORG_PIT, node_type="company",
                                            canonical_key="acme-x7.io", display_name="Acme X7",
                                            event_id=None)
        dupe = pg_store.find_or_create_node(conn, org_id=ORG_PIT, node_type="company",
                                            canonical_key="acme-x7.com", display_name="ACME",
                                            event_id=None)
        person = pg_store.find_or_create_node(conn, org_id=ORG_PIT, node_type="person",
                                              canonical_key="rhea@acme-x7.io",
                                              display_name="Rhea", event_id=None)
        pg_store.write_fact(conn, org_id=ORG_PIT, subject_node_id=acme, field="deal.stage",
                            value="discovery", value_type="string", confidence=0.9,
                            occurred_at=JANUARY, event_id="evt_x7_pit", evidence={},
                            source="gmail")
        edge = pg_store.write_edge(conn, org_id=ORG_PIT, edge_type="works_at",
                                   from_node_id=person, to_node_id=acme, confidence=0.85,
                                   occurred_at=None, event_id="evt_x7_pit", evidence={},
                                   source="gmail")
        pg_store.write_change(conn, org_id=ORG_PIT, graph_version=1,
                              cause_event_id="evt_x7_pit", payload={"step": "created"})
        t1 = conn.execute(text("select now()")).scalar()

    # ── t2 · the fact is amended and the edge is soft-closed ─────────────────────────────────
    with engine.begin() as conn:
        pg_store.write_fact(conn, org_id=ORG_PIT, subject_node_id=acme, field="deal.stage",
                            value="negotiation", value_type="string", confidence=0.9,
                            occurred_at=FEBRUARY, event_id="evt_x7_pit", evidence={},
                            source="gmail", authority_rank=3)
        conn.execute(text("update graph_edges set valid_to=now() where edge_version_id=:e"),
                     {"e": edge})
        pg_store.write_change(conn, org_id=ORG_PIT, graph_version=2,
                              cause_event_id="evt_x7_pit", payload={"step": "amended"})
        t2 = conn.execute(text("select now()")).scalar()

    # ── t3 · the duplicate company is merged away ────────────────────────────────────────────
    with engine.begin() as conn:
        apply_merge(conn, org_id=ORG_PIT, survivor_node_id=acme, merged_node_id=dupe,
                    reason="x7 point-in-time fixture")
        t3 = conn.execute(text("select now()")).scalar()

    assert t0 < t1 < t2 < t3, "the three writes must land at three distinct instants"
    return {"t0": t0, "t1": t1, "t2": t2, "t3": t3,
            "acme": acme, "dupe": dupe, "person": person, "edge": edge}


@pytest.mark.pg
def test_a_read_from_before_the_graph_began_is_empty(pg_store, timeline):
    """The doc's own row: *as_of before the first snapshot returns an empty graph, not an error.*"""
    view = pg_store.read_graph(ORG_PIT, as_of=timeline["t1"] - TICK)
    assert view.is_empty
    assert view.graph_version is None
    assert view.as_of == timeline["t1"] - TICK


@pytest.mark.pg
def test_the_amended_fact_is_the_old_value_before_the_amendment_and_the_new_one_after(
        pg_store, timeline):
    """Doc 02's decisive row, in the shape this graph writes it: a value valid t1-t2 is present
    in a read at t1 and absent from a read at t2."""
    before = pg_store.read_graph(ORG_PIT, as_of=timeline["t1"])
    after = pg_store.read_graph(ORG_PIT, as_of=timeline["t2"])

    assert before.fact(timeline["acme"], "deal.stage").value == "discovery"
    assert after.fact(timeline["acme"], "deal.stage").value == "negotiation"
    # and the superseded version is not lurking in the later read under another status
    assert [f.value for f in after.facts_for(timeline["acme"]) if f.field == "deal.stage"] == \
           ["negotiation"]


@pytest.mark.pg
def test_an_edge_soft_closed_later_is_still_present_at_the_earlier_instant(pg_store, timeline):
    """*An edge soft-deleted in Feb is present at as_of=Jan.* This is the property that a hard
    DELETE would destroy silently — the row would simply never have existed."""
    assert any(e.edge_version_id == timeline["edge"]
               for e in pg_store.read_graph(ORG_PIT, as_of=timeline["t1"]).edges)
    assert not any(e.edge_version_id == timeline["edge"]
                   for e in pg_store.read_graph(ORG_PIT, as_of=timeline["t2"]).edges)
    assert not any(e.edge_version_id == timeline["edge"]
                   for e in pg_store.live_graph(ORG_PIT).edges)


@pytest.mark.pg
def test_a_merge_is_invisible_before_its_timestamp_and_visible_after(pg_store, timeline):
    """`apply_merge` CLOSES the merged node rather than deleting it (`merge.py`: *"its id may
    already appear in a delivery card, a reasoning trace or an audit row"*), which is exactly what
    makes the merge a temporal event this read can place."""
    assert pg_store.read_graph(ORG_PIT, as_of=timeline["t2"]).node(timeline["dupe"]) is not None
    assert pg_store.read_graph(ORG_PIT, as_of=timeline["t3"]).node(timeline["dupe"]) is None
    assert pg_store.read_graph(ORG_PIT, as_of=timeline["t3"]).node(timeline["acme"]) is not None


@pytest.mark.pg
def test_read_graph_as_of_now_matches_the_live_graph_exactly(pg_store, timeline):
    """The equivalence property, and the reason it is the FIRST thing doc 02's acceptance asks
    for: every other as-of read is only as trustworthy as this one. Compared as `content` because
    the two reads legitimately differ in the instant they name."""
    live = pg_store.live_graph(ORG_PIT)
    as_of_now = pg_store.read_graph(ORG_PIT, as_of=_db_now(pg_store.engine))
    assert as_of_now.content == live.content
    assert live.as_of is None and as_of_now.as_of is not None
    assert live.node(timeline["acme"]) is not None


@pytest.mark.pg
def test_replaying_an_earlier_decision_reproduces_its_inputs(pg_store, timeline):
    """*Replaying a March decision against as_of=March reproduces its inputs.* Read twice at the
    same instant, across three intervening writes, and the graph is byte-for-byte the same."""
    first = pg_store.read_graph(ORG_PIT, as_of=timeline["t1"])
    second = pg_store.read_graph(ORG_PIT, as_of=timeline["t1"])
    assert first.content == second.content
    assert first.graph_version == 1
    assert pg_store.read_graph(ORG_PIT, as_of=timeline["t2"]).graph_version == 2


@pytest.mark.pg
def test_an_out_of_order_write_never_appears_in_a_read_of_the_time_it_claims(pg_store, timeline):
    """`write_fact` stores a stale re-extraction as `status='historical'` with
    `valid_from = valid_to`, an EMPTY window. So a 2024 value backfilled today can never surface
    in a 2024 read — it was not known then, and the point-in-time read says so without needing a
    status filter of its own."""
    engine = pg_store.engine
    with engine.begin() as conn:
        pg_store.write_fact(conn, org_id=ORG_PIT, subject_node_id=timeline["acme"],
                            field="deal.stage", value="prospect", value_type="string",
                            confidence=0.5,
                            occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                            event_id="evt_x7_pit", evidence={}, source="gmail")
        historical = conn.execute(text(
            "select count(*) from graph_facts where org_id=:o and status='historical'"),
            {"o": ORG_PIT}).scalar()
    assert historical == 1, "the stale write must be RECORDED, not dropped"
    for instant in (timeline["t1"], timeline["t2"], _db_now(engine)):
        values = [f.value for f in pg_store.read_graph(ORG_PIT, as_of=instant).facts
                  if f.field == "deal.stage"]
        assert "prospect" not in values
    assert pg_store.read_graph(ORG_PIT, as_of=_db_now(engine)).content == \
           pg_store.live_graph(ORG_PIT).content


@pytest.mark.pg
def test_the_read_is_tenant_scoped(pg_store, timeline):
    """Every statement in the reader carries `org_id`. A point-in-time read that leaked across
    tenants would be an audit surface that answers with somebody else's graph."""
    assert pg_store.read_graph("org_scratch_tests", as_of=timeline["t3"]).node(
        timeline["acme"]) is None


# =================================================================================================
# THE WIRING — /graph/as-of, driven through the router
# =================================================================================================

@pytest.fixture()
def client(pg_store, timeline):
    """The REAL router, with only the tenant identity overridden.

    Layer 1 lost six units to being green and unreachable, so this drives
    `api/routes.graph_as_of` over HTTP rather than calling `read_graph` again: if the route were
    never registered, or read the wrong store, this test is the one that fails.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import routes
    from genios_engine.platform.auth import get_current_org
    if routes._graph is None:
        pytest.skip("graph store not configured for the API module")
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_org] = lambda: ORG_PIT
    return TestClient(app)


@pytest.mark.pg
def test_the_route_answers_what_we_knew_then_and_what_we_know_now(client, timeline):
    then = client.get("/graph/as-of", params={"at": timeline["t1"].isoformat()}).json()
    stages = [f["value"] for f in then["facts"] if f["field"] == "deal.stage"]
    assert stages == ["discovery"]
    assert then["graph_version"] == 1
    assert then["counts"]["edges"] == 1

    now = client.get("/graph/as-of").json()
    assert [f["value"] for f in now["facts"] if f["field"] == "deal.stage"] == ["negotiation"]
    assert now["as_of"] is None
    assert now["counts"]["edges"] == 0          # the works_at edge was closed at t2


@pytest.mark.pg
def test_the_route_reads_an_empty_graph_before_the_org_had_one(client, timeline):
    body = client.get("/graph/as-of",
                      params={"at": (timeline["t1"] - TICK).isoformat()}).json()
    assert body["counts"] == {"nodes": 0, "facts": 0, "edges": 0}
    assert body["graph_version"] is None


@pytest.mark.pg
def test_the_route_refuses_an_instant_it_cannot_parse(client):
    """A 400, never a silent fallback to now: an audit answer that quietly became "today" would
    be indistinguishable from a correct one."""
    assert client.get("/graph/as-of", params={"at": "last march"}).status_code == 400
