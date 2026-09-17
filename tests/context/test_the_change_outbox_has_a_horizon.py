"""The second append-only store in this layer, and the one with no horizon at all.

`graph_change_outbox` takes one row per committed event — both lanes write it — and it has a real
reader: `GraphStore.graph_version_at` answers "which version had this org reached at instant T",
the number an audit has to quote because read models and reasoning runs are stamped with it.

It is not, despite its name, an outbox anybody drains. `published_at` has never been set by
anything, and three things followed from that:

    the table grew without bound, which `analytic/history` names as "the exact shape that put this
    database into read-only once before" — and that one has a 24-month horizon on a path that runs;

    its only index was partial on `published_at is null`, true of every row that has ever existed,
    so it was a second copy of the org_id column maintained on every insert and selecting nothing;

    the reader's own filter — `org_id` and `created_at <= :t` — had no index at all.

Retention is safe here because the reader was written expecting it. Its docstring already says it
returns None for "an org whose outbox rows have aged out", and that a null is honest there where a
0 would read as a real version.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.graph_store import GraphStore
from genios_engine.context.analytic.history import RETENTION_MONTHS, months_before

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_change_outbox (change_id text primary key, "
                       "org_id text, graph_version bigint, cause_event_id text, payload text, "
                       "published_at timestamp, created_at timestamp)"))
    s = object.__new__(GraphStore)
    s._engine = engine
    return s


def _change(store, change_id, version, *, age_days, org=ORG):
    with store._engine.begin() as c:
        c.execute(text("insert into graph_change_outbox (change_id, org_id, graph_version, "
                       "payload, created_at) values (:id,:o,:v,'{}',:at)"),
                  {"id": change_id, "o": org, "v": version,
                   "at": NOW - timedelta(days=age_days)})


def _remaining(store):
    with store._engine.connect() as c:
        return {r[0] for r in c.execute(text("select change_id from graph_change_outbox")).all()}


# ── the horizon ──────────────────────────────────────────────────────────────────────────────

def test_the_horizon_matches_the_layers_longest_lived_store() -> None:
    """Chosen rather than invented: `graph_version_at` exists so an audit can resolve the version
    a stamped artifact was produced under, and a horizon shorter than the longest-lived store
    would leave a retained metric point pointing at a version nothing can name."""
    assert GraphStore.OUTBOX_RETENTION_MONTHS == RETENTION_MONTHS


def test_rows_past_the_horizon_are_deleted(store) -> None:
    _change(store, "old", 1, age_days=365 * 3)
    _change(store, "recent", 2, age_days=30)
    assert store.prune_change_outbox(ORG, eval_time=NOW) == 1
    assert _remaining(store) == {"recent"}


def test_a_row_inside_the_horizon_is_kept(store) -> None:
    """The cutoff is the month START, so a row from the boundary month survives."""
    cutoff = months_before(NOW, RETENTION_MONTHS)
    _change(store, "just_inside", 1, age_days=(NOW - cutoff).days - 1)
    store.prune_change_outbox(ORG, eval_time=NOW)
    assert _remaining(store) == {"just_inside"}


def test_pruning_twice_in_a_month_deletes_nothing_the_second_time(store) -> None:
    """`months_before` anchors on the month start, so the horizon does not creep between two
    sweeps in the same month — the second prune is a no-op rather than a few more rows."""
    _change(store, "old", 1, age_days=365 * 3)
    assert store.prune_change_outbox(ORG, eval_time=NOW) == 1
    assert store.prune_change_outbox(ORG, eval_time=NOW + timedelta(days=1)) == 0


def test_another_tenants_rows_are_never_touched(store) -> None:
    _change(store, "theirs", 1, age_days=365 * 3, org="other_org")
    assert store.prune_change_outbox(ORG, eval_time=NOW) == 0
    assert _remaining(store) == {"theirs"}


# ── bounded, because the first sweep meets the whole backlog ─────────────────────────────────

def test_one_sweep_cannot_become_an_unbounded_delete(store) -> None:
    """The first prune on a tenant that has been draining for a year meets every row at once, and
    this runs inside the transaction budget of the path that ingests mail."""
    for i in range(5):
        _change(store, f"old{i}", i, age_days=365 * 3)
    assert store.prune_change_outbox(ORG, eval_time=NOW, batch_limit=2) == 2
    assert len(_remaining(store)) == 3


def test_the_backlog_drains_across_repeated_sweeps(store) -> None:
    """A bounded batch is only correct if repeating it finishes the job — the drain repeats."""
    for i in range(5):
        _change(store, f"old{i}", i, age_days=365 * 3)
    while store.prune_change_outbox(ORG, eval_time=NOW, batch_limit=2):
        pass
    assert _remaining(store) == set()


# ── and the reader still answers honestly on the other side of it ────────────────────────────

def test_the_reader_answers_none_past_the_horizon_rather_than_zero(store) -> None:
    """Its own docstring: None for "an org whose outbox rows have aged out" — a null is honest
    where a 0 would read as a real version."""
    _change(store, "recent", 7, age_days=30)
    store.prune_change_outbox(ORG, eval_time=NOW)
    assert store.graph_version_at(ORG, as_of=NOW) == 7
    assert store.graph_version_at(ORG, as_of=NOW - timedelta(days=365 * 3)) is None


def test_an_org_with_nothing_left_resolves_to_none(store) -> None:
    _change(store, "old", 3, age_days=365 * 3)
    store.prune_change_outbox(ORG, eval_time=NOW)
    assert store.graph_version_at(ORG, as_of=NOW) is None


# ── the other half of versioning: does every writer bump? ────────────────────────────────────

def test_the_sweep_bumps_once_after_the_derived_passes() -> None:
    """`bump_slice_versions` calls `bump_version` "the one step every graph write already takes",
    and that was untrue of everything between the drain and the fixpoint hash.

    Every pass in that block writes to the graph — engagement, momentum, the waiting arithmetic,
    trends, cohort positions, situations and their lifecycle — and none bumped. So a seat holding
    a live device was never told the facts its card shows had changed, and a query spanning the
    block passed `_require_stable_query_inputs`, whose whole job is to "reject a mixed read if
    graph... changed mid-query", while the facts under it moved.
    """
    import inspect

    from genios_engine.context import runner

    source = inspect.getsource(runner.process_pending)
    assert "store.bump_version(_bump_conn, org_id)" in source

    # ONCE, and after the work. A bump per derived row would announce thousands of slice deltas
    # for one sweep; a bump before the passes would announce a change that had not happened yet.
    assert source.count("store.bump_version(") == 1
    assert source.index("store.bump_version(") > source.index("refresh_situation_importance")


def test_the_bump_cannot_break_ingestion() -> None:
    """Same contract as every other pass in the sweep: a missed bump costs one cycle of live
    freshness, and a guard that could stop a drain reporting its work would be the worse failure.
    """
    import inspect

    from genios_engine.context import runner

    source = inspect.getsource(runner.process_pending)
    after = source[source.index("store.bump_version(_bump_conn, org_id)"):]
    assert "except Exception:" in after[:400]
