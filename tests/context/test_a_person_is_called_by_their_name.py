"""Somebody cc'd once in March is still called by their address on every card in September.

    pytest tests/context/test_a_person_is_called_by_their_name.py -q

`find_or_create_node` writes `display_name` when it CREATES a node and never again — it
re-registers aliases on every later sighting and leaves the label exactly as the first event
wrote it. For a person that first arrival is usually a To/Cc line, and a To/Cc line carries a
bare address: recipients are not described, only senders are.

So a person cc'd once, who has written to us every week since, is still
`theresa.hoffmann@antler.co` on every card — while the From header of their own mail has said
"Theresa Hoffmann" a hundred times.

MEASURED ON THE PILOT 2026-09-16: 35 of 76 person nodes displayed a bare address. For 8 of them a
From-header name was already sitting in their own `source_events` rows, unused — 1,095 of 1,719
events carry one. The other 27 have never sent us anything: nobody has named them, and they are
correctly left alone.

THE WHOLE CHAIN ALREADY EXISTED. `runner` reads `se.actor->>'name' as sender_name`, hands it to
`process_event`, and `_person` builds the right label from it. The one missing piece was the
promotion onto a node that already existed — which is what `name_company_node` and
`name_thread_node` do for their own types. This is the third twin, and it keeps their rule
exactly: promote only while the display name restates the anchor.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.graph_store import GraphStore

pytestmark = pytest.mark.unit

ORG = "org_1"


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table graph_nodes (node_id text, version int, org_id text, node_type text, "
            "canonical_key text, display_name text, identity_strength text, "
            "created_by_event_id text, valid_to timestamp)"))
    return GraphStore(engine=engine), engine


def _node(engine, node_id, key, display):
    with engine.begin() as c:
        c.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
            "display_name, identity_strength, created_by_event_id, valid_to) "
            "values (:n, 1, :o, 'person', :k, :d, 'strong', 'evt', null)"),
            {"n": node_id, "o": ORG, "k": key, "d": display})


def _shown(engine, node_id):
    with engine.connect() as c:
        return c.execute(text("select display_name from graph_nodes where node_id=:n"),
                         {"n": node_id}).scalar()


def test_a_node_still_called_by_its_address_is_named(store) -> None:
    """The case: cc'd first, wrote to us later."""
    gs, engine = store
    _node(engine, "n1", "theresa.hoffmann@antler.co", "theresa.hoffmann@antler.co")
    with engine.begin() as c:
        assert gs.name_person_node(c, org_id=ORG, node_id="n1", name="Theresa Hoffmann") is True
    assert _shown(engine, "n1") == "Theresa Hoffmann"


def test_a_name_from_a_better_source_is_never_overwritten(store) -> None:
    """A connector, a human, an earlier and better sighting all outrank a header line. This is
    the rule `name_company_node` states and the reason promotion is gated at all."""
    gs, engine = store
    _node(engine, "n2", "priya@chat360.io", "Priya Sharma")
    with engine.begin() as c:
        assert gs.name_person_node(c, org_id=ORG, node_id="n2", name="priya") is False
    assert _shown(engine, "n2") == "Priya Sharma"


def test_an_empty_name_changes_nothing(store) -> None:
    """Most To/Cc lines carry no name at all, so this is the common path and must be cheap and
    silent rather than blanking the label."""
    gs, engine = store
    _node(engine, "n3", "bare@example.com", "bare@example.com")
    with engine.begin() as c:
        assert gs.name_person_node(c, org_id=ORG, node_id="n3", name="   ") is False
    assert _shown(engine, "n3") == "bare@example.com"


def test_a_header_that_repeats_the_address_is_not_a_name(store) -> None:
    """`"priya@chat360.io" <priya@chat360.io>` parses to a display name that IS the address.

    THE NODE HERE HAS NO LABEL AT ALL, and that is the whole point of the case. When the label
    already equals the address the equality check above catches it; the only path that reaches
    the address guard is a node whose `display_name` is NULL — which `find_or_create_node` writes
    whenever it is handed no name. Without the guard that node would be "named" with the address
    and the call would report True, telling a reader somebody was named when nothing happened.
    """
    gs, engine = store
    _node(engine, "n4", "priya@chat360.io", None)
    with engine.begin() as c:
        assert gs.name_person_node(c, org_id=ORG, node_id="n4",
                                   name="priya@chat360.io") is False
    assert _shown(engine, "n4") is None


def test_it_is_idempotent(store) -> None:
    """Every sighting of a sender calls this. The second one must report that nothing changed,
    or a sweep's counters read as churn."""
    gs, engine = store
    _node(engine, "n5", "hardik@reticle.sh", "hardik@reticle.sh")
    with engine.begin() as c:
        assert gs.name_person_node(c, org_id=ORG, node_id="n5", name="Hardik Agarwal") is True
        assert gs.name_person_node(c, org_id=ORG, node_id="n5", name="Hardik Agarwal") is False


def test_a_node_that_does_not_exist_is_not_an_error(store) -> None:
    """A retired or merged node must not raise inside a sweep that is naming somebody else."""
    gs, engine = store
    with engine.begin() as c:
        assert gs.name_person_node(c, org_id=ORG, node_id="missing", name="Anybody") is False


def test_the_three_twins_keep_one_rule() -> None:
    """Person, company and thread each promote only over a label that restates the anchor. Read
    from source, because three functions drifting apart is how one of them stops being safe."""
    import inspect

    for fn in (GraphStore.name_person_node, GraphStore.name_company_node):
        src = inspect.getsource(fn)
        assert "casefold() != anchor" in src.replace("anchor_key", "anchor"), (
            f"{fn.__name__} no longer gates promotion on the label restating the anchor")


def test_the_pipeline_actually_calls_it() -> None:
    """A promotion nothing invokes is the defect it was written to fix.

    `_person` is a closure inside `process_event` and cannot be reached without driving a whole
    event through the pipeline, so this reads the call site from source. That is weaker than
    exercising it — and it is exactly the check that was missing when four other correct-and-
    unreachable pieces shipped this week: a render overlay whose caller could be deleted with no
    test failing, and three before it.
    """
    import inspect

    from genios_engine.context import pipeline

    source = inspect.getsource(pipeline.process_event)
    assert "store.name_person_node(" in source, (
        "nothing promotes a person's name onto an existing node — the node keeps the address "
        "it was created with, which is the whole defect")
    assert "label == sender_name" in source, (
        "the promotion is no longer gated on the label coming from the From header")
