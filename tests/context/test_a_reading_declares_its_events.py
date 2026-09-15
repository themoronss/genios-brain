"""M9.C1.L-data.V1.U02 — a reading's correlation id gains the membership its facts imply.

    pytest tests/context/test_a_reading_declares_its_events.py -q

THE DEFECT, MEASURED ON THE PILOT 2026-09-15. Layer 3 held 73 of 94 situations at
`QES_REQUIRED` — the gate that says a situation whose importance did not come from a Layer 1
qualified signal may not carry authority. They could not satisfy it, and not because the data was
missing: 238 qualified signals were live and all 99 correlation-member events carried one. Only 20
of 94 situations could reach one.

`gather_l1_signals` joins signals THROUGH `context_correlation_members`, and its join is exactly
`qualified_signals.event_id = context_correlation_members.event_id`. A reading mints a synthetic
correlation id — `outreach:{node}`, `stated:{hash}`, `analytic:trend:{node}` — and writes no
membership for it, so the join has nothing to match and the situation falls back to
`DEFAULT_IMPORTANCE_BP`. Fourteen of the eighteen live situation types are in that state, which is
87% of the cards.

The provenance to fix it was already on every fact. `_finding_events` (U01) exposes it; this unit
writes it down.

TWO GUARDS, AND BOTH ARE ABOUT NOT DAMAGING WHAT WORKS:

* A READING ONLY CLAIMS ITS OWN CORRELATION. If a `context_correlations` row exists, the
  correlation engine owns that id — it decided which events are one thing, and it maintains a
  counter beside the membership. Adding rows underneath it would enlarge somebody else's scope and
  desynchronise `event_count` from the rows it counts.
* `None` IS NOT `()`. An unreadable graph leaves existing membership alone; a finding that rests
  on no events writes nothing. Deleting on absence is the failure this codebase refuses
  everywhere.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import _Finding, _declare_finding_events

pytestmark = pytest.mark.unit

ORG = "org1"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table context_correlation_members (org_id text, "
                       "correlation_id text, event_id text, joined_via text, "
                       "joined_at timestamp, primary key (org_id, correlation_id, event_id))"))
        c.execute(text("create table context_correlations (org_id text, correlation_id text, "
                       "event_count integer)"))
        yield c


def members(conn, correlation_id="outreach:n1"):
    return [tuple(r) for r in conn.execute(text(
        "select event_id, joined_via from context_correlation_members "
        "where org_id=:o and correlation_id=:c order by event_id"),
        {"o": ORG, "c": correlation_id}).fetchall()]


def finding(**kw):
    kw.setdefault("correlation_id", "outreach:n1")
    kw.setdefault("concerns_node", "n1")
    return _Finding(**kw)


def test_a_readings_events_become_its_membership(conn) -> None:
    """THE WHOLE UNIT. Before this, the join `gather_l1_signals` performs had nothing to match."""
    n = _declare_finding_events(conn, org_id=ORG, finding=finding(event_ids=("evt_a", "evt_b")))
    assert n == 2
    assert members(conn) == [("evt_a", "reading"), ("evt_b", "reading")]


def test_the_provenance_says_a_reading_wrote_it(conn) -> None:
    """`joined_via` already distinguishes `anchor` from `thread`. A membership row a reading
    derived from its own facts is a third thing, and a reader has to be able to tell."""
    _declare_finding_events(conn, org_id=ORG, finding=finding(event_ids=("evt_a",)))
    assert members(conn) == [("evt_a", "reading")]


def test_it_is_idempotent(conn) -> None:
    """It runs on every finding of every sweep. A second pass over an unchanged graph must write
    nothing — otherwise the sweep is not replayable and the table grows without bound."""
    f = finding(event_ids=("evt_a", "evt_b"))
    assert _declare_finding_events(conn, org_id=ORG, finding=f) == 2
    assert _declare_finding_events(conn, org_id=ORG, finding=f) == 0
    assert len(members(conn)) == 2


def test_a_growing_event_set_adds_only_what_is_new(conn) -> None:
    """THE CASE THAT PROVES IDEMPOTENCE IS REAL RATHER THAN SWALLOWED. Returning 0 twice can be
    earned two ways: by an insert that conflicts harmlessly, or by an insert that RAISES and is
    caught by the guard below — and the second silently rolls the whole nested transaction back.
    A partial overlap tells them apart: the new event must land, which it cannot do if the batch
    aborted on the duplicate."""
    assert _declare_finding_events(conn, org_id=ORG, finding=finding(event_ids=("evt_a",))) == 1
    grown = finding(event_ids=("evt_a", "evt_b"))
    assert _declare_finding_events(conn, org_id=ORG, finding=grown) == 1, \
        "the duplicate aborted the batch instead of being skipped"
    assert members(conn) == [("evt_a", "reading"), ("evt_b", "reading")]


def test_a_correlation_the_engine_owns_is_never_touched(conn) -> None:
    """THE FIRST GUARD. `context_correlations` existing means the correlation engine decided which
    events are one thing and maintains `event_count` beside the rows. Adding membership underneath
    it enlarges somebody else's scope and desynchronises a counter from what it counts."""
    conn.execute(text("insert into context_correlations values (:o,'corr_real',3)"), {"o": ORG})
    n = _declare_finding_events(conn, org_id=ORG,
                                finding=finding(correlation_id="corr_real",
                                                event_ids=("evt_x",)))
    assert n == 0
    assert members(conn, "corr_real") == []


def test_an_unreadable_graph_costs_membership_and_never_the_sweep(conn) -> None:
    """THE SECOND GUARD, stated as what is actually observable today. This writer is INSERT-ONLY,
    so "no events" and "could not read the events" both write nothing — the two are not
    distinguishable here and this test does not pretend they are. What IS observable, and what the
    guard exists for: a graph it cannot read must not raise into the sweep, and must not disturb
    membership already written. The `None`/`()` distinction `_finding_events` keeps becomes
    load-bearing the day anything reconciles; until then it is a contract, not a behaviour."""
    _declare_finding_events(conn, org_id=ORG, finding=finding(event_ids=("evt_a",)))
    broken = finding(event_ids=None, inputs=None, concerns_node="n1")
    assert _declare_finding_events(conn, org_id=ORG, finding=broken) == 0
    assert members(conn) == [("evt_a", "reading")]


def test_nothing_here_ever_deletes_membership(conn) -> None:
    """The rule that makes the guard above safe, pinned in the code rather than in prose: an
    insert-only writer cannot reconcile a shrinking event set, and cannot destroy one either."""
    import ast
    import inspect

    from genios_engine.context import outreach_situations

    tree = ast.parse(inspect.getsource(outreach_situations._declare_finding_events))
    # ONLY WHAT IS EXECUTED — the literals handed to `text(...)`. Scanning every string constant
    # reads the docstring, where "would delete real membership" is a sentence about the rule and
    # not a statement this function runs. That trap has cost this suite four tests already.
    sql = " ".join(
        lit.value.lower()
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "text"
        for lit in ast.walk(call)
        if isinstance(lit, ast.Constant) and isinstance(lit.value, str))
    assert sql, "no SQL was found to check"
    assert "delete" not in sql, "this writer can now delete membership"
    assert "on conflict do nothing" in sql, (
        "the insert no longer skips duplicates, so a replayed sweep aborts its own batch")


def test_a_finding_resting_on_nothing_writes_nothing(conn) -> None:
    assert _declare_finding_events(conn, org_id=ORG, finding=finding(event_ids=())) == 0
    assert members(conn) == []


def test_a_finding_with_no_correlation_id_writes_nothing(conn) -> None:
    """There is no namespace to claim, so there is nothing to claim it for."""
    f = _Finding(correlation_id=None, concerns_node="n1", event_ids=("evt_a",))
    assert _declare_finding_events(conn, org_id=ORG, finding=f) == 0


def test_no_counter_is_invented_for_a_synthetic_correlation(conn) -> None:
    """A reading's correlation has no `context_correlations` row and must not gain one. The
    counter belongs to the engine that owns the correlation; minting one here would make a
    diagnostic the reason a row exists."""
    _declare_finding_events(conn, org_id=ORG, finding=finding(event_ids=("evt_a",)))
    assert conn.execute(text("select count(*) from context_correlations")).scalar() == 0


def test_membership_is_written_under_the_id_the_situation_carries(conn) -> None:
    """CAUGHT ON THE LIVE TENANT, NOT HERE — and this is the test that should have caught it.

    A finding is stored once per CLAIMING DOMAIN, under `f"{finding.correlation_id}_{domain}"`.
    The first cut of this writer used the finding's bare correlation id, so it wrote membership
    for `analytic:anomaly:node_df86…:engagement.days_since_contact` while the situation carried
    `…days_since_contact_admin`. 307 rows landed, every one of them under an id no situation
    holds, and the measured reach stayed at exactly 20 of 129.

    The membership has to match the id `gather_l1_signals` will be asked about, which is the
    situation's, not the finding's."""
    _declare_finding_events(conn, org_id=ORG,
                            finding=finding(correlation_id="outreach:n1_admin",
                                            event_ids=("evt_a",)))
    assert members(conn, "outreach:n1_admin") == [("evt_a", "reading")]
    assert members(conn, "outreach:n1") == [], "written under the unsuffixed id"


def test_the_persistence_loop_writes_one_membership_per_domain() -> None:
    """The loop mints `corr` per claiming domain and upserts a situation for each. Membership is
    written from inside that loop, so a finding claimed by two domains gets two memberships —
    one for each id that actually exists."""
    import ast
    import inspect

    from genios_engine.context import outreach_situations

    tree = ast.parse(inspect.getsource(outreach_situations))
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)
             and getattr(n.target, "id", "") == "domain"]
    assert loops, "the per-domain loop was not found"
    assert any(getattr(c.func, "id", "") == "_declare_finding_events"
               for loop in loops for c in ast.walk(loop) if isinstance(c, ast.Call)), \
        "membership is written outside the per-domain loop, so it uses an id no situation carries"


def test_the_persistence_loop_calls_it(conn) -> None:
    """Wired at the seam, inside the transaction that writes the finding's facts — so membership
    and facts are the same write or neither is."""
    import ast
    import inspect

    from genios_engine.context import outreach_situations

    tree = ast.parse(inspect.getsource(outreach_situations))
    holders = [w for w in ast.walk(tree) if isinstance(w, ast.With)
               and any(getattr(c.func, "attr", "") == "find_or_create_node"
                       for c in ast.walk(w) if isinstance(c, ast.Call))]
    assert holders, "the findings' write transaction was not found"
    assert any(getattr(c.func, "id", "") == "_declare_finding_events"
               for w in holders for c in ast.walk(w) if isinstance(c, ast.Call)), \
        "membership is not written inside the transaction that writes the facts"
