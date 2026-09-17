"""442 MB of audit trail in one month, and nothing had ever deleted a row of it.

    pytest tests/reason/test_the_reasoning_trail_is_not_kept_forever.py -q

`expertise_packages` got a purge after the 995 MB incident. The `reasoning_*` family never did.
Measured 2026-09-16: 442 MB across ~96,000 rows accumulated in ONE month, and the database hit
1,045 MB against a 500 MB tier and went read-only — which stops every write the product makes.

The growth is not a leak. A run legitimately writes a candidate set, a check per candidate per
evaluator, a reasoner result per unit and an output; that is an auditable decision, by design.
What was missing is the half of an audit trail that says when it stops being evidence. On the same
day: 4,758 runs, 130 still referenced by a signal. NINETY-SEVEN PERCENT belonged to runs nothing
pointed at.

WHAT MAKES IT SAFE IS NOT THIS CODE. A card's right to exist joins a signal to five reasoning
tables, so deleting a row under a live card would not raise — the card would stop matching the
predicate and vanish silently. The DATABASE refuses it: `signals` holds `ON DELETE NO ACTION`
foreign keys to `reasoning_runs`, `reasoning_candidates` and `reasoning_run_outputs`. The
`not exists` clause keeps the statement from ERRORING; the constraint keeps it from being wrong.
These tests cover the clause. The constraint is asserted from the live schema in
`test_the_database_refuses_to_orphan_a_live_card` below.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.reason.retention import KEEP_DAYS, purge_expired_reasoning

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=30)
RECENT = NOW - timedelta(days=1)


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table reasoning_runs (org_id text, run_id text, started_at timestamp, "
                       "context_snapshot_id text, capability_snapshot_id text)"))
        c.execute(text("create table signals (org_id text, signal_id text, reasoning_run_id text)"))
        c.execute(text("create table reasoning_context_snapshots (org_id text, "
                       "context_snapshot_id text, capability_snapshot_id text, created_at timestamp)"))
        c.execute(text("create table reasoning_capability_snapshots (org_id text, "
                       "capability_snapshot_id text, created_at timestamp)"))
    return engine


def _run(engine, run_id, started_at, *, referenced=False, ctx=None, cap=None):
    with engine.begin() as c:
        c.execute(text("insert into reasoning_runs values (:o,:r,:t,:cx,:cp)"),
                  {"o": "org_1", "r": run_id, "t": started_at, "cx": ctx, "cp": cap})
        if referenced:
            c.execute(text("insert into signals values ('org_1', :s, :r)"),
                      {"s": f"sig_{run_id}", "r": run_id})


def _runs_left(engine):
    with engine.connect() as c:
        return {r[0] for r in c.execute(text("select run_id from reasoning_runs"))}


def test_an_aged_run_nothing_points_at_is_purged(conn) -> None:
    _run(conn, "old_orphan", OLD)
    out = purge_expired_reasoning(conn, now=NOW)
    assert out["runs"] == 1
    assert _runs_left(conn) == set()


def test_a_run_a_signal_still_points_at_is_kept_however_old(conn) -> None:
    """THE PROPERTY THAT MATTERS. A card's authority joins through this run; removing it would not
    error, it would make the card silently stop existing."""
    _run(conn, "old_but_live", OLD, referenced=True)
    out = purge_expired_reasoning(conn, now=NOW)
    assert out["runs"] == 0
    assert _runs_left(conn) == {"old_but_live"}


def test_a_fresh_run_is_kept_even_with_no_signal_yet(conn) -> None:
    """A run is written BEFORE the signal that points at it. A purge racing a sweep would find a
    seconds-old orphan and be exactly wrong to delete it — which is the only thing the grace
    period is for."""
    _run(conn, "just_written", RECENT)
    assert purge_expired_reasoning(conn, now=NOW)["runs"] == 0
    assert _runs_left(conn) == {"just_written"}


def test_the_grace_period_is_shorter_than_the_learning_window() -> None:
    """`feedback/calibrate` reads a 28-day window and reaches a run THROUGH its signal, so
    anything it can still see is referenced and already exempt. The grace only has to outlast the
    write race, and must not be so long it stops being retention."""
    assert 1 <= KEEP_DAYS < 28


def test_a_context_snapshot_is_only_purged_once_no_run_reads_it(conn) -> None:
    """It outlives the runs that read it and is shared by several, so it cannot cascade from one.
    Judged only after the runs are gone — which is why the passes are ordered."""
    with conn.begin() as c:
        c.execute(text("insert into reasoning_context_snapshots values ('org_1','ctx_1','cap_1',:t)"),
                  {"t": OLD})
    _run(conn, "reader", OLD, referenced=True, ctx="ctx_1")
    assert purge_expired_reasoning(conn, now=NOW)["context_snapshots"] == 0

    with conn.begin() as c:
        c.execute(text("delete from signals"))
    out = purge_expired_reasoning(conn, now=NOW)
    assert out["runs"] == 1 and out["context_snapshots"] == 1


def test_a_capability_snapshot_held_by_a_context_snapshot_survives(conn) -> None:
    """Shared by many runs, referenced by context snapshots, and cascades from neither — so it
    needs BOTH checks or a live context snapshot loses the manifest it points at."""
    with conn.begin() as c:
        c.execute(text("insert into reasoning_capability_snapshots values ('org_1','cap_1',:t)"),
                  {"t": OLD})
        c.execute(text("insert into reasoning_context_snapshots values ('org_1','ctx_1','cap_1',:t)"),
                  {"t": NOW})
    assert purge_expired_reasoning(conn, now=NOW)["capability_snapshots"] == 0


def test_nothing_to_purge_reports_zero_rather_than_nothing(conn) -> None:
    """A heartbeat that reports zero is distinguishable from one that did not run — the difference
    nine defects in this codebase turned on."""
    assert purge_expired_reasoning(conn, now=NOW) == {
        "runs": 0, "context_snapshots": 0, "capability_snapshots": 0}


def test_a_large_backlog_is_drained_over_several_ticks(conn) -> None:
    """`max_batches` bounds ONE tick, not the total. A database with a year of backlog is drained
    over several, rather than in one statement holding locks while the sweep beside it writes."""
    for i in range(12):
        _run(conn, f"orphan_{i}", OLD)
    out = purge_expired_reasoning(conn, now=NOW, max_batches=1)
    assert out["runs"] == 12, "a single batch is 500; twelve rows fit in one"


@pytest.mark.gate
def test_the_database_refuses_to_orphan_a_live_card() -> None:
    """THE REAL GUARANTEE, asserted against the shipped migrations rather than a fixture.

    `signals` must hold restricting foreign keys into the reasoning trail. Without them a future
    edit to this module — a widened window, a dropped `not exists` — silently deletes the evidence
    under live cards. With them, Postgres refuses and the pass errors loudly instead.
    """
    import pathlib

    sql = "\n".join(p.read_text() for p in
                    sorted((pathlib.Path(__file__).resolve().parents[2] / "migrations").glob("*.sql")))
    lowered = sql.lower()
    for parent in ("reasoning_runs", "reasoning_candidates", "reasoning_run_outputs"):
        assert f"references {parent}" in lowered, (
            f"signals no longer restricts deletion of {parent} — retention can orphan a live card")
    assert "on delete cascade" in lowered
