"""A sweep that explains nothing and a sweep with nothing to explain used to read identically.

Every pass in `process_pending` reports what it PRODUCED — derived rows, situations refreshed,
metric points, cohort changes, budgets exhausted. Not one reported what it LEFT BEHIND. So the
question a founder actually asks — "what is happening in my mailbox that this thing never
mentioned?" — had no answer anywhere in the engine, and the only way to find out was to read the
graph by hand and compare it against the cards. That is how every defect on this branch was found.

THE FAILURE MODE THIS MUST AVOID IS FALSE RESIDUE. A detector that reports a well-served
counterparty as unexplained is worse than no detector: it would send somebody hunting for a bug
that is not there, and it would hide the real ones in noise. Most of what follows is therefore
NEGATIVE — proof that coverage, in each of the shapes coverage actually takes in this layer,
suppresses the finding.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.graph_store import GraphStore
from genios_engine.context.residue import (RESIDUE_BALL_IN_COURT, RESIDUE_NODE_EVIDENCE,
                                           RESIDUE_OPEN_LOOP, RESIDUE_SIGNAL, detect_residue,
                                           read_residue)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"

_SCHEMA = (
    "create table context_residue (org_id text, residue_kind text, subject_ref text, "
    "detail text, first_seen_at timestamp, last_seen_at timestamp, "
    "primary key (org_id, residue_kind, subject_ref))",
    # `situation_type` is in the real table (migration 0038) and was missing here, so the
    # coverage predicate could not read the one column that tells a card reporting a gap apart
    # from a card explaining one. A fixture short of a column the engine selects on is a test
    # that passes on a schema nobody runs.
    "create table context_situations (org_id text, situation_id text, correlation_id text, "
    "anchor_node_id text, status text, situation_type text)",
    "create table context_correlation_members (org_id text, correlation_id text, event_id text)",
    "create table graph_observations (org_id text, observation_id text, subject_node_id text, "
    "status text)",
    "create table graph_edges (org_id text, edge_type text, from_node_id text, "
    "to_node_id text, valid_to text)",
    "create table graph_facts (org_id text, subject_node_id text, field text, value text, "
    "status text, valid_to text)",
    "create table graph_source_refs (org_id text, observation_id text, event_id text)",
    "create table open_loops (org_id text, loop_id text, subject_node_id text, kind text, "
    "status text)",
    "create table qualified_signals (org_id text, signal_id text, event_id text, "
    "signal_type text)",
)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for stmt in _SCHEMA:
            c.execute(text(stmt))
    s = object.__new__(GraphStore)
    s._engine = engine
    return s


def _sql(store, *statements):
    with store._engine.begin() as c:
        for stmt in statements:
            c.execute(text(stmt))


def _counts(store, *, at=NOW):
    return detect_residue(store, ORG, eval_time=at).counts


def _watched(store):
    """A person the layer holds evidence about."""
    _sql(store, "insert into graph_observations values ('o','ob1','sehan','active')")


# ── the four kinds fire ──────────────────────────────────────────────────────────────────────

def test_evidence_nothing_speaks_about_is_residue(store) -> None:
    _watched(store)
    assert _counts(store)[RESIDUE_NODE_EVIDENCE] == 1


def test_the_ball_being_in_our_court_with_no_card_is_residue(store) -> None:
    """The case named directly: they replied, we went quiet, and nothing said so."""
    _sql(store, "insert into graph_facts values "
                "('o','sehan','thread.ball_in_court','\"us\"','active',null)")
    assert _counts(store)[RESIDUE_BALL_IN_COURT] == 1


def test_the_ball_in_their_court_is_not_residue(store) -> None:
    """Waiting on somebody else is a different situation and has its own reading."""
    _sql(store, "insert into graph_facts values "
                "('o','sehan','thread.ball_in_court','\"them\"','active',null)")
    assert _counts(store)[RESIDUE_BALL_IN_COURT] == 0


def test_an_open_ask_attached_to_nothing_is_residue(store) -> None:
    _sql(store, "insert into open_loops values ('o','l1','sehan','question','open')")
    assert _counts(store)[RESIDUE_OPEN_LOOP] == 1


def test_a_closed_loop_is_not_residue(store) -> None:
    _sql(store, "insert into open_loops values ('o','l1','sehan','question','closed')")
    assert _counts(store)[RESIDUE_OPEN_LOOP] == 0


def test_layer_one_signals_nothing_consumes_are_counted_by_type(store) -> None:
    """The useful sentence is "deadline: 131, none consumed", not 131 identical rows — a missing
    PRODUCER is a fact about a type."""
    _sql(store,
         "insert into qualified_signals values ('o','s1','e1','deadline')",
         "insert into qualified_signals values ('o','s2','e2','deadline')",
         "insert into qualified_signals values ('o','s3','e3','decision')")
    assert _counts(store)[RESIDUE_SIGNAL] == 2, "two TYPES, not three signals"


# ── coverage suppresses it, in each shape coverage actually takes ────────────────────────────

def test_a_situation_anchored_on_the_subject_explains_it(store) -> None:
    _watched(store)
    _sql(store, "insert into context_situations values ('o','sit1','c1','sehan','active','admin_contact')")
    assert _counts(store)[RESIDUE_NODE_EVIDENCE] == 0


def test_a_concerns_hop_from_a_state_readings_anchor_explains_it(store) -> None:
    """NOT OPTIONAL. Every state reading mints its OWN anchor node and links the person with one
    `concerns` hop, so checking `anchor_node_id` alone would report every correctly-served
    counterparty in the tenant as unexplained."""
    _watched(store)
    _sql(store,
         "insert into context_situations values ('o','sit1','corr_state','anchor1','active','admin_contact')",
         "insert into graph_edges values ('o','concerns','anchor1','sehan',null)")
    assert _counts(store)[RESIDUE_NODE_EVIDENCE] == 0


def test_a_partial_situation_explains_it(store) -> None:
    """`partial` is live at both Layer 3 doors — a partially-resolved situation is still open on
    the half nobody closed."""
    _watched(store)
    _sql(store, "insert into context_situations values ('o','sit1','c1','sehan','partial','admin_contact')")
    assert _counts(store)[RESIDUE_NODE_EVIDENCE] == 0


@pytest.mark.parametrize("status", ["dormant", "resolved", "archived"])
def test_a_situation_that_cannot_reach_a_card_explains_nothing(store, status: str) -> None:
    """The whole point of the status filter. Both Layer 3 doors admit only `active` and `partial`,
    so counting a dormant row as coverage would hide exactly the staleness this table exists to
    find — a subject with evidence, a situation on file, and no way to be told about it."""
    _watched(store)
    _sql(store, f"insert into context_situations values ('o','sit1','c1','sehan','{status}','admin_contact')")
    assert _counts(store)[RESIDUE_NODE_EVIDENCE] == 1


# ── the honesty test for signals ─────────────────────────────────────────────────────────────

def test_a_signal_reached_through_correlation_membership_is_not_residue(store) -> None:
    """Path one: the join `situation_bso._L1_SELECT` itself uses."""
    _sql(store,
         "insert into qualified_signals values ('o','s1','e1','deadline')",
         "insert into context_correlation_members values ('o','c1','e1')",
         "insert into context_situations values ('o','sit1','c1','n1','active','admin_contact')")
    assert _counts(store)[RESIDUE_SIGNAL] == 0


def test_a_signal_reached_only_through_a_state_reading_is_not_residue(store) -> None:
    """PATH TWO, AND THE REASON IT EXISTS. Only `correlation.py` writes
    `context_correlation_members`; every state reading, the period sweep, meeting touch and the
    document register mint a SYNTHETIC correlation with no membership rows at all. Checking the
    first join alone would count a signal whose event produced a perfectly good state reading as
    unreached — the detector would slander the readings that work, which is the one failure that
    would make it worse than nothing."""
    _sql(store,
         "insert into qualified_signals values ('o','s1','e1','deadline')",
         "insert into graph_source_refs values ('o','ob1','e1')",
         "insert into graph_observations values ('o','ob1','sehan','active')",
         "insert into context_situations values ('o','sit1','corr_state_x','sehan','active','admin_contact')")
    assert _counts(store)[RESIDUE_SIGNAL] == 0


# ── it is current state, and it remembers how long ───────────────────────────────────────────

def test_residue_that_gets_explained_disappears(store) -> None:
    """Deleting by `last_seen_at < :now` is the whole reconciliation — no second state, and
    nothing to keep consistent with the first."""
    _watched(store)
    assert _counts(store)[RESIDUE_NODE_EVIDENCE] == 1
    _sql(store, "insert into context_situations values ('o','sit1','c1','sehan','active','admin_contact')")
    assert _counts(store, at=NOW + timedelta(hours=1))[RESIDUE_NODE_EVIDENCE] == 0
    with store._engine.connect() as c:
        assert read_residue(c, ORG) == []


def test_how_long_it_has_gone_unexplained_is_never_overwritten(store) -> None:
    """`first_seen_at` is what makes this a work queue rather than a gauge: the item nobody has
    been able to explain for three months is the one worth looking at."""
    _watched(store)
    _counts(store)
    later = NOW + timedelta(days=30)
    _counts(store, at=later)
    with store._engine.connect() as c:
        [row] = read_residue(c, ORG, kind=RESIDUE_NODE_EVIDENCE)
    assert str(row["first_seen_at"]).startswith("2026-09-20")
    assert str(row["last_seen_at"]).startswith("2026-10-20")


def test_the_queue_is_ordered_longest_unexplained_first(store) -> None:
    _watched(store)
    _counts(store)
    _sql(store, "insert into graph_observations values ('o','ob2','theresa','active')")
    _counts(store, at=NOW + timedelta(days=10))
    with store._engine.connect() as c:
        rows = read_residue(c, ORG, kind=RESIDUE_NODE_EVIDENCE)
    assert [r["subject_ref"] for r in rows] == ["sehan", "theresa"]


# ── bounded, and it says so ──────────────────────────────────────────────────────────────────

def test_one_sweep_cannot_scan_an_unbounded_graph(store) -> None:
    """The first run on a tenant with poor coverage meets the whole graph at once, inside the
    transaction budget of the path that ingests mail."""
    _sql(store, *[f"insert into graph_observations values ('o','ob{i}','n{i}','active')"
                  for i in range(6)])
    report = detect_residue(store, ORG, eval_time=NOW, limit=3)
    assert report.counts[RESIDUE_NODE_EVIDENCE] == 3
    assert RESIDUE_NODE_EVIDENCE in report.truncated, (
        "a truncated pass must not look like a clean one")


def test_a_complete_pass_is_not_reported_as_truncated(store) -> None:
    _watched(store)
    assert detect_residue(store, ORG, eval_time=NOW, limit=3).truncated == frozenset()


# ── tenancy ──────────────────────────────────────────────────────────────────────────────────

def test_another_tenants_graph_is_never_scanned(store) -> None:
    _sql(store, "insert into graph_observations values ('other','ob1','theirs','active')")
    assert detect_residue(store, ORG, eval_time=NOW).total == 0
