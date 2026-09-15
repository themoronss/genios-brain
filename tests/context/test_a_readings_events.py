"""M9.C1.L-logic.V0.U01 — which events is one reading's finding actually built from?

    pytest tests/context/test_a_readings_events.py -q

THE QUESTION NOBODY ASKED OF A READING. `_finding_receipts` has always derived this event set —
explicit `event_ids`, else `inputs['events']`, else a walk from the finding's nodes through
`graph_facts` to `graph_source_refs` — and then immediately spent it on `load_event_receipts`,
returning receipts rather than ids. The ids were computed on every finding of every sweep and
thrown away.

WHY THE IDS MATTER ON THEIR OWN. Measured on the pilot 2026-09-15: Layer 3 held 73 of 94
situations at `QES_REQUIRED`, because `gather_l1_signals` joins Layer 1's qualified signals
THROUGH the correlation — and a reading mints a synthetic correlation id (`outreach:{node}`,
`stated:{hash}`, `analytic:{key}`) with no rows in `context_correlation_members`. All 99
correlation-member events carry a qualified signal; only 20 of 94 situations can reach one. The
provenance to fix that already exists on every fact. It just never became membership.

THIS UNIT DOES NOT WRITE ANYTHING. It separates the derivation from the loading, so the next unit
has ids to write and this one has a contract that can be tested without a graph.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import _Finding, _finding_events

pytestmark = pytest.mark.unit

ORG = "org1"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_facts (org_id text, subject_node_id text, "
                       "fact_version_id text, status text, valid_to timestamp)"))
        c.execute(text("create table graph_source_refs (org_id text, fact_version_id text, "
                       "event_id text)"))
        yield c


def fact(conn, node, version, event):
    conn.execute(text("insert into graph_facts values (:o,:n,:v,'active',null)"),
                 {"o": ORG, "n": node, "v": version})
    conn.execute(text("insert into graph_source_refs values (:o,:v,:e)"),
                 {"o": ORG, "v": version, "e": event})


def test_an_explicit_event_list_wins(conn) -> None:
    """A group reading already knows its exact scope — the seven campaign messages, not the two
    people chosen to represent them. Re-deriving would silently enlarge it."""
    f = _Finding(concerns_node="n1", event_ids=("evt_a", "evt_b"))
    assert _finding_events(conn, org_id=ORG, finding=f) == ("evt_a", "evt_b")


def test_the_inputs_block_is_the_second_source(conn) -> None:
    f = _Finding(concerns_node="n1", inputs={"events": ["evt_c"]})
    assert _finding_events(conn, org_id=ORG, finding=f) == ("evt_c",)


def test_otherwise_the_events_come_from_the_facts_themselves(conn) -> None:
    """THE PROVENANCE THAT ALREADY EXISTS. Every fact carries the event it was written from;
    the walk is facts -> source refs, which is how receipts have always been found."""
    fact(conn, "n1", "v1", "evt_x")
    fact(conn, "n1", "v2", "evt_y")
    f = _Finding(concerns_node="n1")
    assert _finding_events(conn, org_id=ORG, finding=f) == ("evt_x", "evt_y")


def test_evidence_nodes_widen_the_walk_beyond_the_anchor(conn) -> None:
    """A group finding concerns one node and rests on several. Walking only the anchor would
    make its membership narrower than its evidence."""
    fact(conn, "n1", "v1", "evt_x")
    fact(conn, "n2", "v2", "evt_y")
    f = _Finding(concerns_node="n1", evidence_nodes=("n1", "n2"))
    assert _finding_events(conn, org_id=ORG, finding=f) == ("evt_x", "evt_y")


def test_the_answer_is_ordered_and_deduplicated(conn) -> None:
    """Membership rows are written from this, so two sweeps over an unchanged graph must produce
    the same set in the same order — otherwise the write is not idempotent."""
    fact(conn, "n1", "v1", "evt_b")
    fact(conn, "n1", "v2", "evt_a")
    fact(conn, "n1", "v3", "evt_a")
    f = _Finding(concerns_node="n1")
    assert _finding_events(conn, org_id=ORG, finding=f) == ("evt_a", "evt_b")


def test_a_finding_resting_on_nothing_has_no_events(conn) -> None:
    """Empty is a real answer and not a failure: the next unit writes no membership for it."""
    assert _finding_events(conn, org_id=ORG, finding=_Finding()) == ()
    assert _finding_events(conn, org_id=ORG, finding=_Finding(concerns_node="n1")) == ()


def test_an_unreadable_graph_answers_none_not_empty(conn) -> None:
    """THE DISTINCTION THE WRITER DEPENDS ON. `()` means "this finding rests on no events" and the
    next unit writes nothing. `None` means "the graph could not be read", and the next unit must
    leave whatever membership already exists alone rather than deleting it as absent — the same
    asymmetry `_finding_receipts` keeps when it preserves the original writer."""
    conn.execute(text("drop table graph_source_refs"))
    assert _finding_events(conn, org_id=ORG, finding=_Finding(concerns_node="n1")) is None


def test_receipts_still_answer_exactly_as_before(conn) -> None:
    """The split must be invisible to the caller that already existed. `_finding_receipts` keeps
    its contract; it now asks this function for the ids instead of deriving them inline."""
    import ast
    import inspect

    from genios_engine.context import outreach_situations

    tree = ast.parse(inspect.getsource(outreach_situations._finding_receipts))
    called = {getattr(n.func, "id", "") for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "_finding_events" in called, "the receipts path still derives its own event set"
