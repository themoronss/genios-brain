"""Who a card reaches — the owner was recorded, and the router could not see it.

    pytest tests/context/test_the_owner_was_in_the_graph_and_unreadable.py -q

`executive/assignment.resolve_owner` is the three-rule cascade that decides who a commitment
reaches, and its own comment records what it was doing:

    "Every input above is structurally absent in production … So this returned `None` for
     every card ever built — all 43 carry `assignee = NULL`."

Measured against the checkout, all three of its named inputs are genuinely absent:
`deal.owner` is read by two config sites and written by none, `relationship.owner` appears
nowhere at all, and `graph_nodes.attributes` has no writer.

BUT THE OWNERSHIP WAS NEVER MISSING. `context/pipeline.py` writes an `owns` EDGE — this person
made this promise — at the same moment it mints the commitment node. `resolve_owner` takes
`facts` and `attrs` and CANNOT SEE EDGES. The information sat in the graph, one hop from the
function that needed it, for every card ever built. Same shape this branch has now found
twelve times: a capability exists and nothing consumes it at the point that needs it.

AND THE TWO LAYERS SPELLED IT DIFFERENTLY. The engine looked for `commitment.actor`, a name
that appears nowhere in the corpus vocabulary; the corpus tracked `commitment.owner` in
`planned_substrate`, its list of declared-but-unwritten asks. Neither had a writer.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.executive.assignment import (
    ACTOR_FIELDS,
    OWNER_FIELDS,
    AudienceClass,
    StaticSeatDirectory,
    resolve_owner,
)

pytestmark = pytest.mark.unit

SEATS = StaticSeatDirectory(seats={
    "seat-anamika": {"email": "anamika@acme.test", "active": True, "role": "member"},
    "seat-admin": {"email": "ops@acme.test", "active": True, "role": "admin"},
})


def fact(value):
    return {"value": value, "confidence": 0.9}


# =============================================================================================
# The routing that could not happen.
# =============================================================================================
def test_a_commitments_owner_now_reaches_the_assignment():
    """THE WHOLE POINT. Anamika promised the document; the card is hers."""
    got = resolve_owner(facts={"commitment.owner": fact("anamika@acme.test")},
                        attrs=None, directory=SEATS)

    assert got.seat_id == "seat-anamika"
    assert got.audience is AudienceClass.OWNER
    assert got.reason_code == "rule2_actor"


def test_the_old_spelling_still_answers():
    """A tenant whose pipeline predates the change has no `commitment.owner` on rows already in
    the graph. Both names are read; neither is invented."""
    got = resolve_owner(facts={"commitment.actor": fact("anamika@acme.test")},
                        attrs=None, directory=SEATS)

    assert got.seat_id == "seat-anamika"


def test_the_declared_name_is_preferred():
    """`commitment.owner` is the corpus's name and the one with a writer."""
    assert ACTOR_FIELDS[0] == "commitment.owner"


def test_nobody_named_still_falls_to_the_admin_queue():
    """The guard may not become "route everything somewhere". A card nobody is named on belongs
    to whoever runs the account — deliberately, and unchanged."""
    got = resolve_owner(facts={}, attrs=None, directory=SEATS)

    assert got.audience is AudienceClass.ADMIN_QUEUE
    assert got.seat_id is None


def test_an_owner_who_is_off_seat_is_not_force_matched():
    """Pushing to a dead seat looks identical to delivering successfully, which is the worst
    possible failure for a commitment."""
    got = resolve_owner(facts={"commitment.owner": fact("someone@nowhere.test")},
                        attrs=None, directory=SEATS)

    assert got.audience is AudienceClass.ADMIN_QUEUE


# =============================================================================================
# The write, at the point the edge is written.
# =============================================================================================
def test_the_pipeline_writes_the_owner_beside_the_owns_edge():
    from genios_engine.context import pipeline

    source = inspect.getsource(pipeline)

    assert '("commitment.owner", owner_email, "string")' in source
    assert "node_email[nid] = email" in source


def test_the_value_is_an_address_not_a_node_id():
    """`active_seat` resolves a seat id or an EMAIL. A node id would resolve to nobody —
    silently, which is how the original gap survived."""
    from genios_engine.context import pipeline

    source = inspect.getsource(pipeline)

    assert "owner_email = node_email.get(subj)" in source


def test_no_owner_address_writes_no_owner_fact():
    """A commitment whose actor could not be anchored to an address has no owner to state.
    Writing the node id anyway would put a value in the field that resolves to nobody, which
    reads as "we know who owns this" and is worse than the honest gap."""
    from genios_engine.context import pipeline

    source = inspect.getsource(pipeline)

    assert "if owner_email else ()" in source


# =============================================================================================
# The three inputs that really are absent.
# =============================================================================================
@pytest.mark.parametrize("field", OWNER_FIELDS)
def test_rule_one_still_has_no_producer(field):
    """Recorded, not repaired. `deal.owner` and `relationship.owner` remain read-only names —
    Rule 1 cannot fire, and a test that pretended otherwise would hide it."""
    import pathlib

    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "genios_engine"
    # A WRITER, not a mention. `deal.owner` appears as a config default in two reasoning units
    # and as the value of an `owner_field` key in a capability manifest — both READ it. Only a
    # `write_fact(... field="deal.owner" ...)` would make Rule 1 reachable, and the point of
    # this test is that none exists.
    pattern = re.compile(r"write_fact\([^)]*" + re.escape(field), re.S)
    writers = sorted(path.name for path in root.rglob("*.py")
                     if pattern.search(path.read_text()))

    assert writers == [], f"{field} gained a writer — move it out of this test"


def test_the_corpus_and_the_engine_agree_on_the_name():
    """Two names for one thing is how a fact comes to have a writer on one side and a reader on
    the other that never meet."""
    import pathlib

    import yaml

    corpus = pathlib.Path(__file__).resolve().parents[2] / "Domain Expertise"
    vocab = yaml.safe_load((corpus / "_schema/vocabulary.yaml").read_text())

    assert "commitment.owner" in vocab["substrate"]["fact_paths"]
    assert "commitment.owner" not in (vocab["planned_substrate"]["fact_paths"] or [])
