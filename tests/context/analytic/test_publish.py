"""D5 · the derived-fact writer must not rewrite history — proven on real Postgres.

The defect these tests exist to keep dead: four L2.4 writers (`comparator`, `anomaly`,
`correlation_dependency`, `correlation_timeline`) each carried the same upsert ending
`on conflict ... do update set valid_from = excluded.valid_from`. A cohort position published in
March and swept again in September therefore came back from `read_graph(as_of=March)` as NOTHING
— its window had been moved to `[September, inf)` — so the audit answered "GeniOS knew nothing
about this node's position in March" about a fact GeniOS published in March. Doc 02's acceptance
row, *"replaying a March decision against as_of=March reproduces its inputs"*, failed for exactly
the class of facts L2.4 exists to produce.

Why it survived a green suite: `test_point_in_time.py` proves the point-in-time property only on
rows written through `GraphStore.write_fact`, never on a `derived.*` row, and the derived writers'
own tests assert on the LATEST read. Nothing looked at an old instant through a derived fact. So
every temporal assertion below goes through `pg_store.read_graph(as_of=...)` — the reader X7
shipped — rather than through a SELECT this file wrote, because a test that spells its own window
predicate is testing itself.

THE WRITES COMMIT, AND THIS FILE OWNS ITS OWN TENANT (`ORG_PUB`, dropped at the end, which
cascades every row away). Unlike `test_point_in_time.py` these do NOT need separately timed
transactions: `publish_derived_fact` takes `eval_time` as a PARAMETER and writes it into
`valid_from`/`valid_to`, so March and September are stated, not waited for — which is the same
"no clocks in logic" discipline the rest of L2.4 holds to, and it is what makes a nine-month
history assertable in one test.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.publish import (DERIVED_FACT_GRAIN, PublishAction,
                                                    close_derived_facts,
                                                    derived_fact_version_id, publish_derived_fact)

ORG_PUB = "org_x3_publish_seam"

#: This module's namespace in `graph_facts`, and a true PREFIX of every id it writes — which is
#: what keeps the `left(fact_version_id, n) = :prefix` closes the two correlation modules already
#: run working unchanged.
PREFIX = "fv_pubtest_"

FIELD = "derived.comparison.engagement_touch_count_28d"
NODE = "node_pub_acme"
VALUE_TYPE = "cohort_position"

MARCH = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)
APRIL = datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc)
AUGUST = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)
SEPTEMBER = datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)

#: One microsecond — `timestamptz`'s resolution, and therefore the smallest step that can name
#: "just before" an instant when checking a half-open boundary.
TICK = timedelta(microseconds=1)


def position(percentile_bp: int, band: str = "D4") -> dict:
    """A fact body the shape `comparator.position_fact_value` publishes."""
    return {"percentile_bp": percentile_bp, "band": band, "population_size": 37,
            "cohort_id": "accounts_by_arr_quartile:q4"}


# =================================================================================================
# THE HERMETIC HALF — the pure pieces, with no database in reach
# =================================================================================================

def test_the_version_id_is_period_keyed_and_deterministic():
    """The whole fix rests on this id: a value that changes in a later WEEK gets a different key,
    so the new stint is a new row instead of an edit to the old one's window."""
    first = derived_fact_version_id(PREFIX, NODE, FIELD, datetime(2026, 3, 2, tzinfo=timezone.utc))
    again = derived_fact_version_id(PREFIX, NODE, FIELD, datetime(2026, 3, 2, tzinfo=timezone.utc))
    later = derived_fact_version_id(PREFIX, NODE, FIELD, datetime(2026, 9, 7, tzinfo=timezone.utc))
    assert first == again == f"{PREFIX}{NODE}:{FIELD}:2026-03-02"
    assert later != first
    assert first.startswith(PREFIX) and later.startswith(PREFIX)


def test_the_conflict_clause_never_touches_valid_from():
    """The mutation guard, read off the SQL itself. `valid_from = excluded.valid_from` in a
    `do update` list is the one line that produced D5, in four files; if it ever reappears in this
    one, every point-in-time assertion below would still pass on the INSERT path and fail only on
    a second sweep months later. Cheaper to forbid the string."""
    from pathlib import Path
    import genios_engine.context.analytic.publish as module
    source = Path(module.__file__).read_text()
    upsert = source[source.index("_UPSERT_SQL = text("):source.index("_REVISE_SQL")]
    # everything the conflict path may write, i.e. up to the `returning` clause — which names
    # `valid_from` because the caller is told the window it landed in, and never assigns it.
    do_update = upsert[upsert.index("do update set"):upsert.index("returning")]
    assert "valid_from" not in do_update, (
        "the conflict path may correct a row's body, never the instant it began to be true")
    revise = source[source.index("_REVISE_SQL"):source.index("_CLOSE_SQL")]
    assert "valid_from" not in revise[:revise.index("returning")]


@pytest.mark.parametrize("scope", ["orgs", "everyone", "", None, 7])
def test_an_unknown_visibility_scope_is_refused(scope):
    """D2. `visibility_scope` is a required argument with no default precisely because all four
    call sites hardcoded `'org'` on facts derived from OTHER nodes' evidence; a required argument
    that accepted anything would only move the lie. Refused before any I/O — `target=None` proves
    nothing was opened."""
    with pytest.raises((ValueError, TypeError)):
        publish_derived_fact(None, org_id=ORG_PUB, subject_node_id=NODE, field=FIELD,
                             value=position(3_100), eval_time=MARCH, value_type=VALUE_TYPE,
                             visibility_scope=scope, version_prefix=PREFIX)


def test_visibility_scope_has_no_default():
    """Stated as a signature property, because a default is how the four hardcoded `'org'`s would
    quietly come back as one hardcoded `'org'`."""
    import inspect
    parameter = inspect.signature(publish_derived_fact).parameters["visibility_scope"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


# =================================================================================================
# THE REAL-POSTGRES HALF
# =================================================================================================

@pytest.fixture(scope="module")
def pub_org(pg_store):
    """This file's own tenant, cloned from the scratch org's row (so a later NOT NULL column does
    not turn these tests into an insert error) and dropped at the end, which cascades every
    `graph_facts` row written below out with it."""
    engine = pg_store.engine
    with engine.begin() as conn:
        if not conn.execute(text("select 1 from orgs where id='org_scratch_tests'")).scalar():
            pytest.skip("no scratch org seeded — nothing to clone a tenant from")
        columns = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_generated='NEVER' order by ordinal_position"))]
        projected = ", ".join(":new_id" if c == "id" else c for c in columns)
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) select {projected} "
                          "from orgs where id='org_scratch_tests' on conflict (id) do nothing"),
                     {"new_id": ORG_PUB})
    yield ORG_PUB
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG_PUB})


@pytest.fixture
def field(pg_store, pub_org, request):
    """One field name per test, so the tests share a tenant without sharing a timeline."""
    name = f"{FIELD}.{request.node.name[:60]}"
    yield name
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from graph_facts where org_id=:o and field=:f"),
                     {"o": ORG_PUB, "f": name})


def publish(pg_store, field: str, value: dict, at: datetime, *, node: str = NODE,
            scope: str = "org"):
    with pg_store.engine.begin() as conn:
        return publish_derived_fact(conn, org_id=ORG_PUB, subject_node_id=node, field=field,
                                    value=value, eval_time=at, value_type=VALUE_TYPE,
                                    visibility_scope=scope, version_prefix=PREFIX)


def rows(pg_store, field: str) -> list:
    """Every stored version of one field, oldest first. Raw, because the point of several tests
    below is the SHAPE of the history, which an as-of read deliberately hides."""
    with pg_store.engine.connect() as conn:
        return conn.execute(text(
            "select fact_version_id, value, valid_from, valid_to, status, visibility_scope "
            "from graph_facts where org_id=:o and field=:f order by valid_from, fact_version_id"),
            {"o": ORG_PUB, "f": field}).all()


def fact_at(pg_store, field: str, as_of: datetime):
    """What the audit sees at `as_of`, through X7's reader — not through a query this file wrote."""
    view = pg_store.read_graph(ORG_PUB, as_of=as_of)
    found = [f for f in view.facts if f.field == field]
    assert len(found) <= 1, f"two open rows on {field} at {as_of.isoformat()}: {found}"
    return found[0] if found else None


def body(fact) -> dict:
    return json.loads(fact.value) if isinstance(fact.value, str) else fact.value


# ------------------------------------------------------------------ idempotence, the bound

def test_two_sweeps_in_one_period_with_the_same_value_write_one_row_and_do_not_move_it(
        pg_store, field):
    """The write-amplification bound the four modules' docstrings defend, and the property their
    old upsert bought by destroying history. Here it costs nothing: the second sweep writes
    NOTHING AT ALL — same row, same `valid_from`, and not even a touched `occurred_at` to leave a
    dead tuple behind."""
    first = publish(pg_store, field, position(3_100), MARCH)
    second = publish(pg_store, field, position(3_100), MARCH + timedelta(hours=6))
    assert first.action is PublishAction.INSERTED
    assert second.action is PublishAction.UNCHANGED and second.wrote is False
    assert second.version_id == first.version_id
    assert second.valid_from == first.valid_from
    stored = rows(pg_store, field)
    assert len(stored) == 1
    assert stored[0].valid_from == MARCH


def test_a_hundred_sweeps_of_an_unchanging_fact_are_one_row(pg_store, field):
    """The bound stated as arithmetic: rows track CHANGES, not sweeps. A hundred drains across
    fourteen weeks of a value that never moves is one row, still opened in March."""
    for sweep in range(100):
        publish(pg_store, field, position(3_100), MARCH + timedelta(days=sweep))
    stored = rows(pg_store, field)
    assert len(stored) == 1 and stored[0].valid_from == MARCH


def test_growth_is_one_row_per_week_the_value_actually_changed(pg_store, field):
    """The bound, measured over many sweeps: 120 sweeps across 60 weeks, the value moving every
    third week, must leave exactly the number of CHANGED weeks as rows — not 120, and not one.

    This is the number that replaces the old writer's "one row per (node, field), for ever": at
    ISO-week grain the ceiling is 52 rows per (node, field) per year even for a value that flaps
    every single week, and it is reached only by a fact that really did change that often.
    """
    changes = 0
    value = 1_000
    for week in range(60):
        at = MARCH + timedelta(weeks=week)
        if week % 3 == 0 and week:
            value += 500
            changes += 1
        publish(pg_store, field, position(value), at)         # two sweeps per week
        publish(pg_store, field, position(value), at + timedelta(days=2))
    stored = rows(pg_store, field)
    assert len(stored) == changes + 1 == 20
    assert sum(1 for r in stored if r.valid_to is None) == 1
    assert len(stored) <= 52


# ------------------------------------------------------------------ the point-in-time property

def test_a_march_position_is_still_readable_at_march_after_a_september_sweep(pg_store, field):
    """**THE D5 TEST.** Proven broken on real Postgres by the review: after one September sweep of
    the same node and field, `read_graph(as_of=March)` returned `[]`. It must return MARCH'S ROW,
    with March's value, while `as_of=now` returns September's."""
    march = publish(pg_store, field, position(3_100, "D4"), MARCH)
    september = publish(pg_store, field, position(9_400, "D10"), SEPTEMBER)
    assert september.action is PublishAction.SUPERSEDED
    assert september.closed_version_id == march.version_id
    assert september.version_id != march.version_id

    then = fact_at(pg_store, field, MARCH + timedelta(days=1))
    assert then is not None, "the March fact vanished from March — this is D5"
    assert then.fact_version_id == march.version_id
    assert body(then)["percentile_bp"] == 3_100
    assert then.valid_from == MARCH

    now = fact_at(pg_store, field, SEPTEMBER + timedelta(days=1))
    assert now.fact_version_id == september.version_id
    assert body(now)["percentile_bp"] == 9_400


def test_the_two_windows_are_contiguous_and_never_double_count(pg_store, field):
    """Half-open `[valid_from, valid_to)`, checked at the boundary itself: the instant the new row
    opens is the instant the old one closes, so no reader can see both and no reader can see
    neither."""
    publish(pg_store, field, position(3_100), MARCH)
    publish(pg_store, field, position(9_400), SEPTEMBER)
    assert fact_at(pg_store, field, SEPTEMBER - TICK).valid_from == MARCH
    assert fact_at(pg_store, field, SEPTEMBER).valid_from == SEPTEMBER
    assert fact_at(pg_store, field, MARCH - TICK) is None
    closed = [r for r in rows(pg_store, field) if r.valid_to is not None]
    assert [r.valid_to for r in closed] == [SEPTEMBER]
    assert [r.status for r in closed] == ["superseded"]


def test_a_change_inside_one_period_revises_that_period_without_moving_its_window(pg_store, field):
    """The one place the latest value overwrites: within a single ISO week. The period IS the
    grain — `metric_history` and `peer_baselines` key on the same week — so the week's answer is
    its latest reading, and a row per intra-period change is the per-sweep growth the bound
    forbids. What must NOT happen is the window moving: an as-of read from earlier in that same
    week still lands inside the stint that was opened at its start."""
    first = publish(pg_store, field, position(3_100), MARCH)
    revised = publish(pg_store, field, position(3_600), MARCH + timedelta(days=2))
    assert revised.action is PublishAction.REVISED
    assert revised.version_id == first.version_id
    assert revised.valid_from == MARCH
    stored = rows(pg_store, field)
    assert len(stored) == 1 and stored[0].valid_from == MARCH
    assert body(fact_at(pg_store, field, MARCH + timedelta(hours=1)))["percentile_bp"] == 3_600


def test_a_replay_of_an_earlier_period_is_refused(pg_store, field):
    """A derived writer replayed backwards would have to open a window BEFORE one that is already
    open — two rows claiming the same field over overlapping instants, which is the state every
    as-of read here assumes cannot exist. Refused loudly rather than absorbed."""
    publish(pg_store, field, position(9_400), SEPTEMBER)
    with pytest.raises(ValueError) as caught:
        publish(pg_store, field, position(3_100), MARCH)
    assert "replayed backwards" in str(caught.value)
    assert len(rows(pg_store, field)) == 1


# ------------------------------------------------------------------ the reopen `correlation_dependency` needs

def test_a_blocking_stated_resolved_and_restated_keeps_both_stints(pg_store, field):
    """`correlation_dependency.py:917` set `valid_to = null` AND `valid_from = excluded.valid_from`
    on conflict, so a blocking stated in March, resolved in April and re-stated in August
    collapsed into ONE row reading `[August, inf)` — while the docstring six lines above argued
    that erasing history that way "would make every as-of read of last week silently change its
    answer". Both stints must survive, and April must read as resolved."""
    march = publish(pg_store, field, {"blocked": True, "by": "legal"}, MARCH)
    with pg_store.engine.begin() as conn:
        closed = close_derived_facts(conn, org_id=ORG_PUB, version_prefix=PREFIX, keep=[],
                                     eval_time=APRIL)
    assert closed == 1
    august = publish(pg_store, field, {"blocked": True, "by": "legal"}, AUGUST)
    assert august.action is PublishAction.INSERTED
    assert august.version_id != march.version_id

    assert body(fact_at(pg_store, field, MARCH + timedelta(days=1)))["blocked"] is True
    assert fact_at(pg_store, field, APRIL + timedelta(days=1)) is None, "April was resolved"
    assert fact_at(pg_store, field, AUGUST + timedelta(days=1)).fact_version_id == august.version_id
    assert len(rows(pg_store, field)) == 2


def test_a_reopen_inside_one_period_restores_the_window_it_had_and_does_not_move_it(
        pg_store, field):
    """The CONFLICT path, which is the only branch that can still touch an existing row — and the
    one `valid_from = excluded.valid_from` lived on in all four writers.

    Reached when a stint is closed and the value comes back in the SAME ISO week: the open-row
    lookup sees nothing (the row has a `valid_to`), so the writer INSERTs, and the deterministic
    period-keyed id collides with the row it just closed. `do update` must reopen that row —
    `valid_to = null`, `status = 'active'` — while leaving `valid_from` exactly where it was.

    Restoring the original window rather than opening a new one is the grain being consistent
    with itself: the REVISE branch already says the week's answer is its latest reading, so a
    close and a re-statement inside one week is intra-period churn, not two stints. If instead
    `valid_from` moved to the re-statement, the earlier days of that same week would silently
    stop having an answer — D5 in miniature, on the one path period keying does not eliminate.

    Without this the property is guarded only by `test_the_conflict_clause_never_touches_valid_from`
    reading the SQL as a string, and a string check is not a proof that the row survives.
    """
    same_week = MARCH + timedelta(days=3)                 # 2026-03-07, still ISO week 2026-03-02
    first = publish(pg_store, field, position(3_100), MARCH)
    with pg_store.engine.begin() as conn:
        close_derived_facts(conn, org_id=ORG_PUB, version_prefix=PREFIX, keep=[],
                            eval_time=MARCH + timedelta(days=1))
    assert fact_at(pg_store, field, MARCH + timedelta(days=2)) is None

    again = publish(pg_store, field, position(3_100), same_week)
    assert again.version_id == first.version_id, "same ISO week is the same key"
    assert again.valid_from == MARCH, "the reopened row must keep the instant it began to be true"

    stored = rows(pg_store, field)
    assert len(stored) == 1, "a reopen inside one period must not open a second stint"
    assert stored[0].valid_from == MARCH
    assert stored[0].valid_to is None and stored[0].status == "active"
    assert fact_at(pg_store, field, MARCH + timedelta(hours=1)).valid_from == MARCH


def test_close_retires_only_what_this_sweep_did_not_publish(pg_store, pub_org):
    """The `keep` list is the ids `publish_derived_fact` RETURNED. Under period keying an
    unchanged fact keeps the id of the period it was FIRST published in, so a caller that rebuilt
    the id from (node, field, today) would close the row it meant to keep — which is the whole
    reason the id comes back on the `UNCHANGED` branch too."""
    still_true = f"{FIELD}.kept"
    gone = f"{FIELD}.retired"
    try:
        publish(pg_store, still_true, {"blocked": True}, MARCH)
        publish(pg_store, gone, {"blocked": True}, MARCH)
        kept = publish(pg_store, still_true, {"blocked": True}, AUGUST)   # unchanged, old id
        assert kept.action is PublishAction.UNCHANGED
        with pg_store.engine.begin() as conn:
            closed = close_derived_facts(conn, org_id=ORG_PUB, version_prefix=PREFIX,
                                         keep=[kept.version_id], eval_time=AUGUST)
        assert closed == 1
        assert fact_at(pg_store, still_true, AUGUST + timedelta(days=1)) is not None
        assert fact_at(pg_store, gone, AUGUST + timedelta(days=1)) is None
        assert fact_at(pg_store, gone, MARCH + timedelta(days=1)) is not None
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from graph_facts where org_id=:o and field = any(:f)"),
                         {"o": ORG_PUB, "f": [still_true, gone]})


# ------------------------------------------------------------------ what the row actually says

def test_the_stated_scope_is_what_lands_in_the_column(pg_store, field):
    """D2 again, at the other end: a scope a caller states must arrive in the row unchanged, or
    the required argument is theatre. `participants` is the case that matters — a position built
    from peers' readings is not automatically an org-wide fact."""
    publish(pg_store, field, position(3_100), MARCH, scope="participants")
    assert rows(pg_store, field)[0].visibility_scope == "participants"
    publish(pg_store, field, position(4_100), SEPTEMBER, scope="participants")
    assert {r.visibility_scope for r in rows(pg_store, field)} == {"participants"}


def test_a_legacy_row_from_the_old_id_shape_is_absorbed_not_orphaned(pg_store, field):
    """Every tenant already has rows written under the old, period-less id. They match the prefix
    and the (org, node, field) lookup, so the first sweep after this lands finds one as the open
    stint: same value leaves it alone, a change CLOSES it and opens a period-keyed successor. If
    it were orphaned instead, the field would carry two open rows for ever and every as-of read of
    it would be ambiguous."""
    legacy = f"{PREFIX}{NODE}_{field}"
    with pg_store.engine.begin() as conn:
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "value, value_type, status, authority_rank, confidence, occurred_at, valid_from, "
            "visibility_scope) values (:vid, :fid, :o, :n, :f, cast(:v as jsonb), :vt, 'active', "
            "100, 0.9, :now, :now, 'org')"),
            {"vid": legacy, "fid": legacy, "o": ORG_PUB, "n": NODE, "f": field,
             "v": json.dumps(position(3_100), sort_keys=True), "vt": VALUE_TYPE, "now": MARCH})

    unchanged = publish(pg_store, field, position(3_100), APRIL)
    assert unchanged.action is PublishAction.UNCHANGED and unchanged.version_id == legacy
    assert len(rows(pg_store, field)) == 1

    moved = publish(pg_store, field, position(9_400), SEPTEMBER)
    assert moved.action is PublishAction.SUPERSEDED and moved.closed_version_id == legacy
    assert len(rows(pg_store, field)) == 2
    assert fact_at(pg_store, field, APRIL).fact_version_id == legacy
    assert fact_at(pg_store, field, SEPTEMBER).fact_version_id == moved.version_id


def test_the_engine_form_and_the_connection_form_agree(pg_store, field):
    """The four call sites publish inside the transaction they already own; a route or a script
    has only an engine. Both must produce the same row, or the seam has two behaviours."""
    handed_engine = publish_derived_fact(
        pg_store.engine, org_id=ORG_PUB, subject_node_id=NODE, field=field, value=position(3_100),
        eval_time=MARCH, value_type=VALUE_TYPE, visibility_scope="org", version_prefix=PREFIX)
    assert handed_engine.action is PublishAction.INSERTED
    assert publish(pg_store, field, position(3_100), MARCH).action is PublishAction.UNCHANGED
    assert len(rows(pg_store, field)) == 1


def test_the_period_is_computed_in_utc(pg_store, field):
    """`period_start` floors to a calendar day, so the same instant read back in a non-UTC session
    timezone would floor to a different ISO week and the writer would disagree with itself about
    which period a row belongs to. Sunday 23:00 UTC and the Monday after it are different weeks —
    and would be the SAME week if the boundary were computed in, say, Asia/Kolkata."""
    sunday = datetime(2026, 3, 8, 23, 0, tzinfo=timezone.utc)
    monday = datetime(2026, 3, 9, 1, 0, tzinfo=timezone.utc)
    first = publish(pg_store, field, position(3_100), sunday)
    second = publish(pg_store, field, position(4_100), monday)
    assert second.action is PublishAction.SUPERSEDED
    assert first.version_id.endswith("2026-03-02") and second.version_id.endswith("2026-03-09")
    assert DERIVED_FACT_GRAIN.value == "week"
