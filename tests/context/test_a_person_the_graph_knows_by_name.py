"""76 people in the graph, 41 of them carrying a human name, and 4 reachable by it.

    pytest tests/context/test_a_person_the_graph_knows_by_name.py -q

MEASURED READ-ONLY ON THE PILOT, 2026-09-15. `graph_aliases` held 76 `email` keys and **4**
`person_name` keys. Every name-based lookup in Layer 2 — `resolve_person_name`, and through it
`graph_endpoint_resolver`, which both correlators use as their identity cascade — reads that
index and nothing else. So a graph that could print "Aditya Dwivedi" on a card could not answer
the question "who is Aditya Dwivedi".

WHAT IT COST, measured the same day: the timeline correlator examined 214 commitments and dropped
**49 conditional promises** at `unresolved_subject`. Their endpoints are not obscure — "Keshav",
"Joey Catanzaro", "Aditya Dwivedi", "Julika" — they are people the graph already holds nodes for,
named in prose by the name the node itself displays.

THE MECHANISM. `alias_keys_for_node` leaves person names out of the ANCHOR keys deliberately, and
correctly: an anchor key raises a merge proposal against whoever already holds it, and two people
sharing a name is ordinary rather than a duplicate. The OBSERVED alias exists for exactly this
case — `observe_person_name` never creates a node and never proposes a merge. It simply had one
caller, in the extractor's entity loop, which fires only when a single message carries a person
type AND an email AND a name together. The header/participant path that actually creates most
people never called it.

THE SECOND DEFECT, WHICH HAD TO BE FIXED FIRST. `graph_aliases` is keyed on
(org_id, alias_type, alias_key), and `observe_person_name` inserted `on conflict do nothing`. So
a second live "John" never got a row, the first kept the name for ever, and `resolve_alias`'s
"ambiguity is not a match" guard — which returns None when two rows answer to a key — could never
fire for names, because a second row could not exist. Indexing 37 more names on top of that would
have multiplied a wrong-person bug rather than fixed a lookup. Contention is now recorded on the
row via `origin`, and a contended key resolves to nobody.

NOTHING HERE IS A RULE ABOUT A CUSTOMER. No name list, no threshold, no heuristic match: a person
is findable by the name the graph already displays for them, and stops being findable the moment
two living people share it.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.identity import (ALIAS_ORIGIN_CONTENDED, ALIAS_PERSON_NAME,
                                            observe_person_name, register_node_identity,
                                            resolve_alias, resolve_person_name)

pytestmark = pytest.mark.unit

ORG = "org1"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_aliases (org_id text, alias_type text, "
                       "alias_key text, node_id text, origin text, created_by_event_id text, "
                       "primary key (org_id, alias_type, alias_key))"))
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "canonical_key text, display_name text, valid_to timestamp)"))
        c.execute(text("create table graph_merge_proposals (org_id text, proposal_id text, "
                       "left_node_id text, right_node_id text, node_type text, reason text, "
                       "evidence text, status text, created_at timestamp)"))
        yield c


def person(conn, node_id: str, *, email: str, name: str | None, dead: bool = False) -> None:
    conn.execute(text("insert into graph_nodes values (:o,:n,'person',:k,:d,:v)"),
                 {"o": ORG, "n": node_id, "k": email, "d": name or email,
                  "v": "2020-01-01" if dead else None})


def register(conn, node_id: str, *, email: str, name: str | None) -> None:
    """The choke point every sighting goes through — creation and re-sighting alike."""
    register_node_identity(conn, org_id=ORG, node_id=node_id, node_type="person",
                           canonical_key=email, display_name=name, event_id="evt_1")


def names(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(text(
        "select alias_key, node_id, coalesce(origin,'') from graph_aliases "
        "where alias_type=:t order by alias_key"), {"t": ALIAS_PERSON_NAME}).fetchall()]


# =================================================================================================
# THE 37. A name the graph displays is a name the graph can be asked about.
# =================================================================================================

def test_a_person_becomes_findable_by_the_name_their_node_displays(conn) -> None:
    """THE WHOLE DEFECT IN ONE ASSERTION. Before this, the node existed, the card printed the
    name, and the lookup returned None."""
    person(conn, "node_a", email="keshav@rocketsdr.ai", name="Keshav")
    register(conn, "node_a", email="keshav@rocketsdr.ai", name="Keshav")
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") == "node_a"


def test_the_name_is_matched_through_its_key_not_by_its_spelling(conn) -> None:
    """`person_name_key` normalises punctuation and whitespace, so the name as written in prose
    reaches the name as written in a header. That is a DERIVATION of a key; the comparison itself
    stays exact, which is the module's standing law."""
    person(conn, "node_a", email="a@x.com", name="Aditya  Dwivedi")
    register(conn, "node_a", email="a@x.com", name="Aditya  Dwivedi")
    assert resolve_person_name(conn, org_id=ORG, name="aditya dwivedi") == "node_a"


def test_a_person_known_only_by_their_address_is_not_indexed_as_a_name(conn) -> None:
    """A node created from an address alone displays that address. Indexing it as a NAME would
    put the same string in two namespaces and buy nothing — the email alias already answers."""
    person(conn, "node_a", email="keshav@rocketsdr.ai", name=None)
    register(conn, "node_a", email="keshav@rocketsdr.ai", name="keshav@rocketsdr.ai")
    assert names(conn) == []


def test_a_later_sighting_that_finally_carries_a_name_indexes_it(conn) -> None:
    """Anchors arrive before names — an address on Monday, the human name on Thursday. The choke
    point runs on EVERY sighting precisely so the later one still lands."""
    person(conn, "node_a", email="j@x.com", name=None)
    register(conn, "node_a", email="j@x.com", name="j@x.com")
    assert names(conn) == []
    conn.execute(text("update graph_nodes set display_name='Joey Catanzaro' where node_id='node_a'"))
    register(conn, "node_a", email="j@x.com", name="Joey Catanzaro")
    assert resolve_person_name(conn, org_id=ORG, name="Joey Catanzaro") == "node_a"


def test_only_people_are_indexed_this_way(conn) -> None:
    """Companies have their own name namespace and their own anchor rules. Crossing them would
    let a project called "Acme" collide with the customer called "Acme"."""
    conn.execute(text("insert into graph_nodes values (:o,'node_c','company','acme.io',"
                      "'Acme Technologies',null)"), {"o": ORG})
    register_node_identity(conn, org_id=ORG, node_id="node_c", node_type="company",
                           canonical_key="acme.io", display_name="Acme Technologies",
                           event_id="evt_1")
    assert names(conn) == []


# =================================================================================================
# THE GUARD THAT HAD TO EXIST FIRST — two live people by one name identify nobody
# =================================================================================================

def test_a_second_living_person_by_the_same_name_makes_it_resolve_to_nobody(conn) -> None:
    """THE BUG THAT INDEXING ALONE WOULD HAVE MULTIPLIED. Two colleagues called John is ordinary.
    Handing the name to whichever was inserted first silently moves every fact, commitment and
    thread state written from that mention onto the wrong person — a merge nobody proposed and
    nothing records."""
    person(conn, "node_a", email="john@acme.io", name="John Smith")
    person(conn, "node_b", email="john@other.io", name="John Smith")
    register(conn, "node_a", email="john@acme.io", name="John Smith")
    assert resolve_person_name(conn, org_id=ORG, name="John Smith") == "node_a"

    register(conn, "node_b", email="john@other.io", name="John Smith")
    assert resolve_person_name(conn, org_id=ORG, name="John Smith") is None, (
        "a name two living people answer to was awarded to whoever was inserted first")


def test_contention_is_recorded_rather_than_deleted(conn) -> None:
    """Nothing is removed. The row still says the name was seen and who saw it first; the only
    thing that changed is that it stops identifying anybody, which is recoverable."""
    person(conn, "node_a", email="john@acme.io", name="John Smith")
    person(conn, "node_b", email="john@other.io", name="John Smith")
    register(conn, "node_a", email="john@acme.io", name="John Smith")
    register(conn, "node_b", email="john@other.io", name="John Smith")
    rows = names(conn)
    assert len(rows) == 1 and rows[0][2] == ALIAS_ORIGIN_CONTENDED


def test_contention_does_not_reverse_when_the_name_is_seen_again(conn) -> None:
    """A third sighting of either person must not quietly restore the name to one of them."""
    person(conn, "node_a", email="john@acme.io", name="John Smith")
    person(conn, "node_b", email="john@other.io", name="John Smith")
    register(conn, "node_a", email="john@acme.io", name="John Smith")
    register(conn, "node_b", email="john@other.io", name="John Smith")
    register(conn, "node_a", email="john@acme.io", name="John Smith")
    assert resolve_person_name(conn, org_id=ORG, name="John Smith") is None


def test_the_same_person_sighted_twice_is_not_contention(conn) -> None:
    """The ordinary case: every mail from the same person re-registers the same name. That must
    stay a no-op, not degrade into an ambiguity."""
    person(conn, "node_a", email="k@x.com", name="Keshav")
    for _ in range(3):
        register(conn, "node_a", email="k@x.com", name="Keshav")
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") == "node_a"
    assert len(names(conn)) == 1


def test_a_contended_key_is_refused_for_every_alias_type(conn) -> None:
    """The guard lives in `resolve_alias`, so it holds for any key marked contended rather than
    only for the one path that sets it today."""
    conn.execute(text("insert into graph_aliases values (:o,'email','x@y.com','node_a',"
                      ":c,'evt')"), {"o": ORG, "c": ALIAS_ORIGIN_CONTENDED})
    assert resolve_alias(conn, org_id=ORG, alias_type="email", alias_key="x@y.com") is None


def test_a_name_held_by_a_node_that_no_longer_exists_is_taken_over(conn) -> None:
    """THE 87. A rebuilt graph left `person_name` keys pointing at the first graph that ever
    existed — 87 of 89 dangling on the pilot. `record_alias` makes this correction for anchor
    keys and this path never did, so the live person stayed unreachable behind a dead claimant.
    Taking the key over is not a merge: there is nothing on the other side to merge with."""
    person(conn, "node_old", email="k@x.com", name="Keshav", dead=True)
    observe_person_name(conn, org_id=ORG, node_id="node_old", name="Keshav")
    conn.execute(text("delete from graph_nodes where node_id='node_old'"))

    person(conn, "node_new", email="k@x.com", name="Keshav")
    register(conn, "node_new", email="k@x.com", name="Keshav")
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") == "node_new"


def test_a_superseded_holder_counts_as_gone(conn) -> None:
    """`valid_to is not null` is how this graph retires a node — the row survives. A retired
    holder is as absent as a deleted one."""
    person(conn, "node_old", email="k@x.com", name="Keshav", dead=True)
    observe_person_name(conn, org_id=ORG, node_id="node_old", name="Keshav")
    person(conn, "node_new", email="k2@x.com", name="Keshav")
    register(conn, "node_new", email="k2@x.com", name="Keshav")
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") == "node_new"


# =================================================================================================
# WHAT THIS MUST NOT HAVE BECOME
# =================================================================================================

def test_a_name_never_creates_a_node_and_never_proposes_a_merge(conn) -> None:
    """The line `alias_keys_for_node` holds, restated at the level that could break it: two
    people sharing a name is ordinary, so it must raise nothing for a human to review."""
    person(conn, "node_a", email="john@acme.io", name="John Smith")
    person(conn, "node_b", email="john@other.io", name="John Smith")
    register(conn, "node_a", email="john@acme.io", name="John Smith")
    register(conn, "node_b", email="john@other.io", name="John Smith")
    assert conn.execute(text("select count(*) from graph_merge_proposals")).scalar() == 0
    assert conn.execute(text("select count(*) from graph_nodes")).scalar() == 2


def test_the_index_holds_no_opinion_about_which_names_are_real(conn) -> None:
    """NO NAME LIST, NO SHAPE TEST, NO THRESHOLD. Whatever the graph displays for a person is
    what that person answers to. A rule here — minimum length, must contain a space, must look
    Western — would be tuned on one tenant's mail and wrong for the next."""
    import ast
    import inspect

    from genios_engine.context import identity

    tree = ast.parse(inspect.getsource(identity.register_node_identity))
    compares = [c for c in ast.walk(tree) if isinstance(c, ast.Compare)
                and any(isinstance(x, ast.Constant) and isinstance(x.value, (int, float))
                        and not isinstance(x.value, bool) for x in c.comparators)]
    assert compares == [], "a rule about which names count has appeared here"

    for odd in ("arvind raja", "Aum", "errorcore dev", "Chandrashekhar, Deepthi"):
        conn.execute(text("delete from graph_aliases"))
        conn.execute(text("delete from graph_nodes"))
        person(conn, "node_a", email="x@y.com", name=odd)
        register(conn, "node_a", email="x@y.com", name=odd)
        assert resolve_person_name(conn, org_id=ORG, name=odd) == "node_a", odd


# =================================================================================================
# THE BACKFILL — the people who most need the lookup are the ones nobody writes to any more
# =================================================================================================

def test_a_person_nobody_has_written_to_since_is_indexed_by_the_sweep(conn) -> None:
    """THE 37, REACHED. The choke point repairs a node the moment something mentions it again,
    and a promise made in May that says "once Keshav confirms" is read in September — by which
    time that node may not have been touched for months. Without the sweep the fix only helps
    people who are already active, which is close to the opposite of who needs it."""
    from genios_engine.context.identity import index_person_names

    person(conn, "node_a", email="k@x.com", name="Keshav")
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") is None
    assert index_person_names(conn) == 1
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") == "node_a"


def test_the_sweep_is_idempotent(conn) -> None:
    """It rides a heartbeat, so it runs for ever. A second pass over an indexed org must write
    nothing rather than re-observe every name on every tick."""
    from genios_engine.context.identity import index_person_names

    person(conn, "node_a", email="k@x.com", name="Keshav")
    assert index_person_names(conn) == 1
    assert index_person_names(conn) == 0


def test_the_sweep_is_bounded(conn) -> None:
    """One tick must stay short on a tenant with a large graph."""
    from genios_engine.context.identity import index_person_names

    for i in range(7):
        person(conn, f"node_{i}", email=f"p{i}@x.com", name=f"Person {i}")
    assert index_person_names(conn, limit=3) == 3
    assert index_person_names(conn, limit=3) == 3
    assert index_person_names(conn, limit=3) == 1


def test_the_sweep_skips_a_retired_person(conn) -> None:
    """A node this graph has retired is not someone to make findable again."""
    from genios_engine.context.identity import index_person_names

    person(conn, "node_old", email="k@x.com", name="Keshav", dead=True)
    assert index_person_names(conn) == 0


def test_the_sweep_stays_inside_one_tenant_when_asked(conn) -> None:
    from genios_engine.context.identity import index_person_names

    person(conn, "node_a", email="k@x.com", name="Keshav")
    conn.execute(text("insert into graph_nodes values ('org2','node_b','person','j@y.com',"
                      "'Julika',null)"))
    assert index_person_names(conn, org_id="org2") == 1
    assert resolve_person_name(conn, org_id=ORG, name="Keshav") is None
    assert resolve_person_name(conn, org_id="org2", name="Julika") == "node_b"


def test_the_sweep_contends_rather_than_awarding_a_shared_name(conn) -> None:
    """THE REASON THIS GOES ONE NAME AT A TIME. A bulk `insert … on conflict do nothing` is
    exactly the shape that hands a shared name to whichever row sorted first — the bug the
    contention rule exists to prevent, reintroduced by the repair for it."""
    from genios_engine.context.identity import index_person_names

    person(conn, "node_a", email="john@acme.io", name="John Smith")
    person(conn, "node_b", email="john@other.io", name="John Smith")
    index_person_names(conn)
    assert resolve_person_name(conn, org_id=ORG, name="John Smith") is None


def test_the_sweep_rides_the_heartbeat(conn) -> None:
    """A repair nothing calls is not a repair. Checked at the seam, and it must be REPORTED —
    `alias_prune` was computed and dropped on the floor, which is indistinguishable from a pass
    that never ran."""
    import ast
    import inspect

    from genios_engine.api import routes

    tree = ast.parse(inspect.getsource(routes))
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name)}
    assert "index_person_names" in called, "the name index is not wired to the heartbeat"

    reported = {k.value for d in ast.walk(tree) if isinstance(d, ast.Dict)
                for k in d.keys if isinstance(k, ast.Constant)}
    assert {"name_index", "alias_prune"} <= reported, "a maintenance pass nobody can see"


def test_a_contended_name_does_not_make_the_sweep_report_work_for_ever(conn) -> None:
    """CAUGHT ON THE LIVE GRAPH, NOT HERE. The first production run indexed 52 names and the
    second reported 1 — because the LOSER of a contention never gets a row of its own, so the
    `not exists` filter selects that node on every tick for ever. It writes nothing, but a
    heartbeat that reports one unit of work every tick is a heartbeat nobody can read. The count
    is of work DONE, not rows looked at."""
    from genios_engine.context.identity import index_person_names

    person(conn, "node_a", email="john@acme.io", name="John Smith")
    person(conn, "node_b", email="john@other.io", name="John Smith")
    assert index_person_names(conn) == 2          # one indexed, one contended it
    assert index_person_names(conn) == 0
    assert index_person_names(conn) == 0
    assert resolve_person_name(conn, org_id=ORG, name="John Smith") is None


def test_the_sweep_reports_the_pass_that_did_the_work(conn) -> None:
    """The mirror: the count must not be silent about a real indexing either. A re-read of the
    row cannot tell "we just created this" from "we already owned it", which is why the insert's
    own rowcount is the authority."""
    from genios_engine.context.identity import index_person_names

    person(conn, "node_a", email="k@x.com", name="Keshav")
    assert index_person_names(conn) == 1
    assert index_person_names(conn) == 0
