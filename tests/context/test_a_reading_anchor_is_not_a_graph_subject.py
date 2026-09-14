"""A reading's own anchor and the graph's real subjects stopped sharing a node type.

THE TESTS THAT DID NOT CATCH THIS. Every existing test of `read_overdue_commitments` calls it with
a hand-built `rows` dict and never runs `_gather`'s SQL, so they were green the whole time
`_owner_key` was unreachable in production. These run the real queries against a real graph, which
is the only way the defect was visible at all:

    `_WAITING_ROWS` excluded `node_type = 'commitment'` to stop a reading reading back the facts it
    projects onto its own anchor. The pipeline mints a GENUINE promise under the same type, so the
    exclusion took those too. `_COMMITMENT_OWNERS` joins on a commitment node id, `_WAITING_ROWS`
    could never return one, and `_owner_name` / `_owner_key` were therefore always None — the owner
    filter written for "six of fifteen cards were somebody else's promise" never fired once.
"""
import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import (READING_ANCHOR_PREFIX, _COMMITMENT_OWNERS,
                                                       _WAITING_ROWS, anchor_node_type)

ORG = "o"
DUE = "2026-09-01T00:00:00+00:00"


def _graph():
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text("create table graph_facts (org_id text, subject_node_id text, field text, "
                       "value text, valid_to text, status text)"))
        c.execute(text("create table graph_nodes (org_id text, node_id text, node_type text, "
                       "display_name text, canonical_key text, valid_to text)"))
        c.execute(text("create table graph_edges (org_id text, edge_type text, "
                       "from_node_id text, to_node_id text, valid_to text)"))
    return e


def _node(c, node_id, node_type, key, name=None):
    c.execute(text("insert into graph_nodes values (:o,:i,:t,:n,:k,null)"),
              {"o": ORG, "i": node_id, "t": node_type, "n": name, "k": key})


def _fact(c, node_id, field, value):
    c.execute(text("insert into graph_facts values (:o,:n,:f,:v,null,'active')"),
              {"o": ORG, "n": node_id, "f": field, "v": value})


def _gathered(e):
    """What `_gather` would hand the reading, from the real query."""
    held: dict[str, dict] = {}
    with e.connect() as c:
        for r in c.execute(text(_WAITING_ROWS), {"o": ORG}):
            held.setdefault(str(r[0]), {})[str(r[1])] = r[2]
        for row in c.execute(text(_COMMITMENT_OWNERS), {"o": ORG}):
            entry = held.get(str(row.commitment))
            if entry is not None:
                entry["_owner_key"] = str(row.owner_key or "") or None
                entry["_owner_name"] = str(row.owner_name or "") or None
    return held


# ── the mapping ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("anchor", ["commitment", "meeting"])
def test_an_anchor_that_collides_with_a_graph_type_is_namespaced(anchor: str) -> None:
    assert anchor_node_type(anchor) == f"{READING_ANCHOR_PREFIX}{anchor}"


@pytest.mark.parametrize("anchor", ["outreach", "cohort", "condition", "organization", "campaign"])
def test_an_anchor_nothing_else_mints_keeps_its_name(anchor: str) -> None:
    """Renaming these would cost and buy nothing: `situation_bso` classifies an anchor as
    company-like by the literal string "organization", so a blanket prefix would silently drop
    that scope key. A reading namespaces only where it actually collides."""
    assert anchor_node_type(anchor) == anchor


# ── the defect, against the real SQL ─────────────────────────────────────────────────────────

def test_a_genuine_promise_now_reaches_the_reading_with_its_owner(monkeypatch) -> None:
    """The whole unit. Before this, every assertion below was False in production."""
    e = _graph()
    with e.begin() as c:
        # what `pipeline.py` mints for a real promise: a commitment node, its facts, an `owns`
        # edge from the person who made it
        _node(c, "cmt1", "commitment", "commitment:" + "a" * 20, "send the deck")
        _node(c, "p_sunil", "person", "sunil@sanchiconnect.tech", "Sunil")
        c.execute(text("insert into graph_edges values (:o,'owns','p_sunil','cmt1',null)"),
                  {"o": ORG})
        _fact(c, "cmt1", "commitment.due_at", DUE)
        _fact(c, "cmt1", "commitment.status", "open")
        _fact(c, "cmt1", "commitment.action", "send the deck")

    held = _gathered(e)
    assert "cmt1" in held, "the pipeline's promise reaches the reading"
    assert held["cmt1"]["commitment.due_at"] == DUE
    assert held["cmt1"]["commitment.status"] == "open"
    assert held["cmt1"]["_owner_key"] == "sunil@sanchiconnect.tech", (
        "the owner filter has something to filter on")
    assert held["cmt1"]["_owner_name"] == "Sunil"


def test_the_reading_still_cannot_eat_its_own_anchor() -> None:
    """The property the exclusion exists for, unchanged. One promise became fifteen identical
    cards and would have kept doubling."""
    e = _graph()
    with e.begin() as c:
        _node(c, "anchor1", anchor_node_type("commitment"), "commitment:node_" + "b" * 24)
        _fact(c, "anchor1", "commitment.due_at", DUE)
        _fact(c, "anchor1", "commitment.action", "reply to confirm receipt")
    assert _gathered(e) == {}, "a reading's own anchor is invisible to the next sweep"


def test_a_meeting_reading_anchor_is_excluded_too() -> None:
    """`meeting` failed OPEN: the anchor was never excluded, and only the field allow-list kept
    the trap shut. Closed on purpose now rather than by accident."""
    e = _graph()
    with e.begin() as c:
        _node(c, "m_anchor", anchor_node_type("meeting"), "meeting:node_" + "c" * 24)
        _fact(c, "m_anchor", "thread.ball_in_court", "us")
    assert _gathered(e) == {}


def test_a_real_calendar_meeting_is_not_swept_up_with_it() -> None:
    """A calendar event keeps `node_type = 'meeting'` and its provider event id, and stays a
    subject the reading may see."""
    e = _graph()
    with e.begin() as c:
        _node(c, "cal1", "meeting", "gcal_evt_9911", "Neon Fund intro")
        _fact(c, "cal1", "thread.ball_in_court", "us")
    assert "cal1" in _gathered(e)


# ── the migration's discriminator ────────────────────────────────────────────────────────────

def test_the_migration_predicate_separates_the_two_shapes() -> None:
    """`find_or_create_node` resolves by canonical_key alone and never rewrites `node_type`, so
    anchors already in a tenant's graph keep the old type until this predicate moves them. A
    wrong predicate here retypes real promises, or leaves stale anchors to be read back."""
    e = _graph()
    with e.begin() as c:
        _node(c, "anchor1", "commitment", "commitment:node_" + "d" * 24)   # reading's own
        _node(c, "cmt1", "commitment", "commitment:" + "e" * 20)           # pipeline's promise
        _node(c, "m_anchor", "meeting", "meeting:node_" + "f" * 24)        # reading's own
        _node(c, "cal1", "meeting", "gcal_evt_9911")                       # real calendar event
        c.execute(text(
            "update graph_nodes set node_type = 'reading:commitment' "
            "where node_type = 'commitment' "
            "and canonical_key like 'commitment:node!_%' escape '!'"))
        c.execute(text(
            "update graph_nodes set node_type = 'reading:meeting' "
            "where node_type = 'meeting' "
            "and canonical_key like 'meeting:node!_%' escape '!'"))
    with e.connect() as c:
        types = dict(c.execute(text("select node_id, node_type from graph_nodes")).all())
    assert types == {"anchor1": "reading:commitment", "cmt1": "commitment",
                     "m_anchor": "reading:meeting", "cal1": "meeting"}


# ── two shapes of subject, one reading ───────────────────────────────────────────────────────

def _held(node_type, name, **facts):
    base = {"_node_type": node_type, "_name": name,
            "commitment.due_at": "2026-09-01T00:00:00+00:00", "commitment.status": "open"}
    base.update(facts)
    return {"n1": base}


def _one(rows):
    from datetime import datetime, timezone
    from genios_engine.context.outreach_situations import read_overdue_commitments
    out = read_overdue_commitments(rows, datetime(2026, 9, 20, tzinfo=timezone.utc), {})
    assert len(out) == 1
    return out[0]


def test_on_a_person_the_display_name_is_still_the_counterparty() -> None:
    """The path that already worked, unchanged. `_name` is Harshita, and a promise is owed TO
    her."""
    finding = _one(_held("person", "Harshita", _owner_name="Rohit",
                         _owner_key="rohit@thegenios.com"))
    assert finding.display_name == "Rohit — promise to Harshita past due"
    assert ("commitment.owed_to", "Harshita", "string") in finding.facts


def test_on_a_commitment_node_the_action_is_never_rendered_as_a_person() -> None:
    """The pipeline's promise. Its display name is the promise's own text, so reading it as a
    counterparty produced "promise to send the deck past due" and filed the action as
    `commitment.owed_to` — which is not a party at all."""
    finding = _one(_held("commitment", "send the deck", _owner_name="Sunil",
                         _owner_key="sunil@sanchiconnect.tech"))
    assert finding.display_name == "Sunil — promise past due"
    assert "send the deck" not in finding.display_name
    assert not [f for f in finding.facts if f[0] == "commitment.owed_to"], (
        "nothing records who a pipeline-extracted promise was made TO; absent beats invented")


def test_the_promise_text_still_reaches_the_card_as_its_action() -> None:
    """Left absent as a recipient, kept as what it is."""
    finding = _one(_held("commitment", "send the deck"))
    assert ("commitment.action", "send the deck", "string") in finding.facts
    assert finding.display_name == "send the deck — promise past due"


def test_an_explicit_action_fact_wins_over_the_node_label() -> None:
    """`commitment.action` is the normalised obligation; the display name is it truncated to 80
    characters. Prefer the fact when both are present."""
    finding = _one(_held("commitment", "Deliver I'll be in PST starting this weeken",
                         **{"commitment.action": "share the updated deck"}))
    assert ("commitment.action", "share the updated deck", "string") in finding.facts
