"""236 conversations, and the cards anchored on them were headlined by a hex fragment.

    pytest tests/context/test_a_conversation_nobody_could_tell_apart.py -q

MEASURED READ-ONLY ON THE PILOT, 2026-09-15. `_thread_node` labels a conversation
`"Thread with <counterparty>"` when it is handed one and `"Thread <id[:12]>"` when it is not, and
two of its four callers pass none. Result: **151 of 236 threads named after a hex fragment**, and
31 live cards — every `first_response_overdue` in the deck — anchored on one of them.

THE OTHER 85 WERE NO BETTER, and this is the half that makes the problem structural rather than
cosmetic. One counterparty is in FIFTEEN separate conversations, and all fifteen nodes read
`"Thread with boardy@boardy.ai"`. The node identity is exactly right — fifteen distinct key spaces,
which is the entire reason thread nodes exist, since `graph_facts` keys on (org, subject, field)
and one person otherwise holds ONE `thread.ball_in_court` across every conversation they are in.
The IDs are correct and the names distinguish nothing.

WHAT NAMES A CONVERSATION IS WHAT IT IS FOR. `thread.objective` is L1's one-line statement of
that, carried on 210 of the 236 threads. The counterparty leads the label because that is what a
reader scans for; the objective says which of their conversations this is.

NO RULE ABOUT WHAT A CONVERSATION IS. The objective travels in L1's own words and the counterparty
is resolved from an edge the pipeline already wrote. Mapping sentences to categories with a
keyword table here would be tuned on one tenant's vocabulary and wrong for the next.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.graph_store import GraphStore, thread_label

pytestmark = pytest.mark.unit

ORG = "org1"


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_nodes (node_id text primary key, version integer, "
                       "org_id text, node_type text, canonical_key text, display_name text, "
                       "identity_strength text, created_by_event_id text, valid_to timestamp)"))
        c.execute(text("create table graph_facts (org_id text, subject_node_id text, field text, "
                       "value text, status text, valid_to timestamp)"))
        c.execute(text("create table graph_edges (org_id text, from_node_id text, "
                       "to_node_id text, edge_type text, created_at text, valid_to timestamp)"))
    return GraphStore(engine=engine)


def thread(store, node_id="t1", name="Thread 1a07a6e0ca77"):
    with store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id,version,org_id,node_type,"
                       "canonical_key,display_name) values (:n,1,:o,'thread',:k,:d)"),
                  {"n": node_id, "o": ORG, "k": f"thread:{node_id}", "d": name})
    return node_id


def label_of(store, node_id="t1") -> str:
    with store.engine.connect() as c:
        return c.execute(text("select display_name from graph_nodes where node_id=:n"),
                         {"n": node_id}).scalar()


# =================================================================================================
# THE CASCADE
# =================================================================================================

def test_the_name_leads_with_who_and_says_which_conversation() -> None:
    assert thread_label(objective="intro call about the paid sales motion",
                        counterparty="Boardy Boardman") == \
        "Boardy Boardman — intro call about the paid sales motion"


def test_each_rung_answers_when_the_one_above_cannot() -> None:
    """A lane that only names what it fully understands leaves everything else unreadable. The raw
    id survives as the last resort: it is a poor name and it is never a wrong one."""
    assert thread_label(objective="discuss the raise") == "discuss the raise"
    assert thread_label(counterparty="Boardy Boardman") == "Thread with Boardy Boardman"
    assert thread_label(thread_id="1a07a6e0ca7799ff") == "Thread 1a07a6e0ca77"
    assert thread_label() == ""


def test_fifteen_conversations_with_one_person_read_differently(store) -> None:
    """THE DEFECT THAT MAKES THIS STRUCTURAL. Same counterparty, same label, fifteen times over —
    so a reader could not tell which of Boardy's conversations a card was about."""
    labels = {thread_label(objective=o, counterparty="Boardy Boardman")
              for o in ("intro to a design partner", "the paid sales motion",
                        "reconnect after the demo")}
    assert len(labels) == 3


def test_a_name_is_not_invented_from_the_sentence(store) -> None:
    """NO KEYWORD TABLE. Whatever L1 said the exchange was for travels verbatim; nothing here
    classifies it into a category this engine made up."""
    import ast
    import inspect

    from genios_engine.context import graph_store

    fn = ast.parse(inspect.getsource(graph_store.thread_label)).body[0]
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    literals = {n.value for stmt in body for n in ast.walk(stmt)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    # The only strings the builder may hold are the joiners of its own template. Anything else
    # here would be a word this engine decided a conversation is about.
    assert literals <= {"", " ", " — ", "Thread ", "Thread with "}, \
        f"thread_label carries vocabulary of its own: {sorted(literals - {chr(32), chr(0)})}"


# =================================================================================================
# PROMOTION — only over a label this module wrote
# =================================================================================================

def test_a_hex_named_thread_is_renamed(store) -> None:
    node = thread(store)
    with store.engine.begin() as c:
        assert store.name_thread_node(c, org_id=ORG, node_id=node,
                                      objective="intro call", counterparty="Boardy") is True
    assert label_of(store) == "Boardy — intro call"


def test_the_shared_counterparty_label_is_also_improved(store) -> None:
    """The 85 that looked fine. `Thread with boardy@boardy.ai` is a label this module generated,
    so it may be replaced by one that distinguishes the conversation."""
    node = thread(store, name="Thread with boardy@boardy.ai")
    with store.engine.begin() as c:
        store.name_thread_node(c, org_id=ORG, node_id=node,
                               objective="the paid sales motion", counterparty="Boardy Boardman")
    assert label_of(store) == "Boardy Boardman — the paid sales motion"


def test_a_name_from_anywhere_better_is_never_overwritten(store) -> None:
    """The rule `name_company_node` states and this one inherits: a name from a connector, a human
    or an earlier and better mention outranks anything derived here."""
    node = thread(store, name="Q3 board pack review")
    with store.engine.begin() as c:
        assert store.name_thread_node(c, org_id=ORG, node_id=node,
                                      objective="something else", counterparty="Boardy") is False
    assert label_of(store) == "Q3 board pack review"


def test_renaming_to_the_same_label_writes_nothing(store) -> None:
    node = thread(store)
    with store.engine.begin() as c:
        assert store.name_thread_node(c, org_id=ORG, node_id=node,
                                      objective="intro call", counterparty="Boardy") is True
        assert store.name_thread_node(c, org_id=ORG, node_id=node,
                                      objective="intro call", counterparty="Boardy") is False


def test_nothing_known_means_nothing_written(store) -> None:
    node = thread(store)
    with store.engine.begin() as c:
        assert store.name_thread_node(c, org_id=ORG, node_id=node) is False
    assert label_of(store) == "Thread 1a07a6e0ca77"


# =================================================================================================
# THE SWEEP — the threads nobody has written in for months
# =================================================================================================

def _wire(store, *, node="t1", party="Boardy Boardman", objective="intro call",
          party_node="p1", created="2026-01-01"):
    with store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id,version,org_id,node_type,canonical_key,"
                       "display_name) values (:n,1,:o,'person',:k,:d)"),
                  {"n": party_node, "o": ORG, "k": f"{party_node}@x.com", "d": party})
        c.execute(text("insert into graph_edges (org_id,from_node_id,to_node_id,edge_type,"
                       "created_at) values (:o,:p,:t,'corresponded_with',:c)"),
                  {"o": ORG, "p": party_node, "t": node, "c": created})
        if objective:
            c.execute(text("insert into graph_facts (org_id,subject_node_id,field,value,status) "
                           "values (:o,:n,'thread.objective',:v,'active')"),
                      {"o": ORG, "n": node, "v": objective})


def test_the_sweep_reaches_a_thread_nobody_has_written_in(store) -> None:
    """THE SET THE WRITE PATH CANNOT REACH. A card saying "nobody answered this in 185 hours" is
    by definition about a conversation that went quiet, so naming only on extraction repairs
    precisely the wrong threads."""
    from genios_engine.context.backfill import name_thread_nodes

    node = thread(store)
    _wire(store, node=node)
    assert name_thread_nodes(store, ORG) == 1
    assert label_of(store) == "Boardy Boardman — intro call"


def test_the_sweep_is_idempotent(store) -> None:
    from genios_engine.context.backfill import name_thread_nodes

    _wire(store, node=thread(store))
    assert name_thread_nodes(store, ORG) == 1
    assert name_thread_nodes(store, ORG) == 0


def test_the_conversation_is_named_after_who_it_started_with(store) -> None:
    """Not after whoever wrote most recently — that would rename the card on every sweep, and a
    headline that moves is a headline nobody trusts."""
    from genios_engine.context.backfill import name_thread_nodes

    node = thread(store)
    _wire(store, node=node, party="First Person", party_node="p1", created="2026-01-01")
    _wire(store, node=node, party="Later Person", party_node="p2", created="2026-06-01",
          objective=None)
    name_thread_nodes(store, ORG)
    assert label_of(store).startswith("First Person")


def test_a_thread_with_no_objective_still_gets_the_counterparty(store) -> None:
    from genios_engine.context.backfill import name_thread_nodes

    node = thread(store)
    _wire(store, node=node, objective=None)
    assert name_thread_nodes(store, ORG) == 1
    assert label_of(store) == "Thread with Boardy Boardman"


def test_the_sweep_is_bounded(store) -> None:
    from genios_engine.context.backfill import name_thread_nodes

    for i in range(5):
        _wire(store, node=thread(store, node_id=f"t{i}"), party_node=f"p{i}",
              objective=f"objective {i}")
    assert name_thread_nodes(store, ORG, limit=2) == 2


def test_the_sweep_rides_the_heartbeat() -> None:
    """A repair nothing calls is not a repair, and one nobody can see is indistinguishable from
    one that never ran."""
    import ast
    import inspect

    from genios_engine.api import routes

    tree = ast.parse(inspect.getsource(routes))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "name_thread_nodes" in called
    reported = {k.value for d in ast.walk(tree) if isinstance(d, ast.Dict)
                for k in d.keys if isinstance(k, ast.Constant)}
    assert "thread_names" in reported


# =================================================================================================
# THE COMPANY HALF OF THE SAME DEFECT
# =================================================================================================

def test_what_l1_calls_an_organization_reaches_the_company_branch() -> None:
    """ALL 48 company nodes on the pilot display a hostname, and the cause is one word. L1's
    entity vocabulary says `organization` — 337 mentions across 147 distinct names — and every
    branch was written against `company`, so `name_company_node`, the only thing that gives a
    company a human name, never fired once. 33 of the 48 have a real name waiting: "Antler",
    "Titan Capital", "PeakXV", "DevDash Labs"."""
    from genios_engine.context.pipeline import _company_type

    assert _company_type("organization") == "company"
    assert _company_type("organisation") == "company"
    assert _company_type("company") == "company"
    assert _company_type("person") == "person", "widening this must not swallow other types"
    assert _company_type("product") == "product"


def test_widening_it_still_mints_no_company() -> None:
    """Safe only because the branch RESOLVES an existing node by exact key equality and refuses
    otherwise. If it could create one, feeding it a looser vocabulary would invent companies out
    of every product and project L1 names."""
    import ast
    import inspect

    from genios_engine.context import pipeline

    # Located as an AST node, not by slicing source text: an earlier cut cut the branch mid
    # walrus expression and failed to parse, which says nothing about the anchor rule.
    tree = ast.parse(inspect.getsource(pipeline))
    branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                and any(isinstance(c, ast.Constant) and c.value == "company"
                        for c in ast.walk(n.test))
                and any(getattr(x, "id", "") == "etype" for x in ast.walk(n.test))]
    assert branches, "the company mention branch is gone"
    for branch in branches:
        made = [n for stmt in branch.body for n in ast.walk(stmt)
                if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "find_or_create_node"]
        assert made == [], "the company branch now creates nodes; the anchor rule is broken"


# =================================================================================================
# A READING MUST BE ABLE TO CORRECT ITS OWN HEADLINE
# =================================================================================================

def test_a_reading_anchor_takes_the_sentence_the_reading_composes_today(store) -> None:
    """MEASURED ON THE PILOT: six commitment anchors reading "makeportals.com — promise past due —
    promise past due", carrying the suffix twice from a build that composed it differently, on
    nodes still typed `commitment` from before migration 0166 gave reading anchors their own type.
    `find_or_create_node` matches on the canonical key alone, so those nodes are still the anchors
    today — wearing a sentence no current code path produces, and which nothing could repair
    because that function sets `display_name` only when it CREATES a node."""
    with store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id,version,org_id,node_type,canonical_key,"
                       "display_name) values ('c1',1,:o,'commitment','commitment:x',"
                       "'boardy.ai — promise past due — promise past due')"), {"o": ORG})
        assert store.rename_reading_anchor(
            c, org_id=ORG, node_id="c1", canonical_key="commitment:x",
            display_name="boardy.ai — promise past due") is True
    assert label_of(store, "c1") == "boardy.ai — promise past due"


def test_the_key_is_the_permission(store) -> None:
    """THE GUARD THAT KEEPS THIS OUT OF EVERY OTHER NAMESPACE. A reading anchor's key is minted by
    that reading and written to by nothing else, so the rename can reach only its own output — a
    person, a company or a thread is unreachable from here even with a matching node id."""
    with store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id,version,org_id,node_type,canonical_key,"
                       "display_name) values ('p1',1,:o,'person','boardy@boardy.ai',"
                       "'Boardy Boardman')"), {"o": ORG})
        assert store.rename_reading_anchor(
            c, org_id=ORG, node_id="p1", canonical_key="commitment:x",
            display_name="something else") is False
    assert label_of(store, "p1") == "Boardy Boardman"


def test_an_unchanged_headline_writes_nothing(store) -> None:
    """It runs on every finding on every sweep, so the no-op case must not churn the table — a
    write here bumps the node and announces a change to every live seat watching it."""
    with store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id,version,org_id,node_type,canonical_key,"
                       "display_name) values ('c2',1,:o,'reading:commitment','commitment:y',"
                       "'boardy.ai — promise past due')"), {"o": ORG})
        assert store.rename_reading_anchor(
            c, org_id=ORG, node_id="c2", canonical_key="commitment:y",
            display_name="boardy.ai — promise past due") is False


def test_the_readings_persistence_calls_it(store) -> None:
    """Wired at the seam, so a reading that composes a better sentence actually delivers it."""
    import ast
    import inspect

    from genios_engine.context import outreach_situations

    tree = ast.parse(inspect.getsource(outreach_situations))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "rename_reading_anchor"]
    assert calls, "findings persist a label they can never correct"
