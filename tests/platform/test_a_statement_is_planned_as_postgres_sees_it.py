"""STEP-17 §3.2 · a statement is planned the way Postgres will be asked it.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q \
        tests/platform/test_a_statement_is_planned_as_postgres_sees_it.py

`yc2_w27_s17` M40.C1.L-logic.V0.U02. Two halves:

  * `positional(sql)` — the statement as the driver sends it: SQLAlchemy's OWN bind parsing for
    psycopg (so `:x::int`, which SQLAlchemy does not bind, stays a syntax error as it is in
    production), an expanding `in :ids` as the list it becomes, `$n` per bind name;
  * `plan(conn, sql)` — `PREPARE` then `EXPLAIN EXECUTE` inside a transaction that is rolled back,
    the prepared statement deallocated. A bind Postgres cannot type on its own is typed by a search
    that accepts only a typing that PLANS, and only on a type error: a missing column or table is
    reported, never retried away.

The positional half is hermetic; the plan half needs a real Postgres.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.platform import statement_plans as sp


# ── positional: hermetic ───────────────────────────────────────────────────────────────────────

def test_each_bind_name_is_one_dollar_parameter_in_order_of_first_use():
    sql, names = sp.positional("select a from t where x = :x and y = cast(:y as text) and z = :x")
    assert sql == "select a from t where x = $1 and y = cast($2 as text) and z = $1"
    assert names == ("x", "y")


def test_an_expanding_in_becomes_the_list_it_is_at_run_time():
    sql, names = sp.positional("select a from t where id in :ids and k not in :ks")
    assert sql == "select a from t where id in ($1) and k not in ($2)"
    assert names == ("ids", "ks")


def test_a_double_colon_cast_on_a_bind_is_not_a_bind_as_in_production():
    """SQLAlchemy's `text()` does not take `:x::int` as a bind — production sends the colon to
    Postgres, which refuses it. The planner must see what production sends."""
    sql, names = sp.positional("select :x::int, a::text from t")
    assert names == ()
    assert ":x::int" in sql and "a::text" in sql


def test_a_percent_sign_in_the_sql_survives():
    sql, _ = sp.positional("select a from t where b like '%x%' and c = :c")
    assert sql == "select a from t where b like '%x%' and c = $1"


def test_an_escaped_colon_is_a_colon():
    sql, names = sp.positional(r"select '10\:30' as at from t where a = :a")
    assert names == ("a",) and "'10:30'" in sql


# ── plan: real Postgres ────────────────────────────────────────────────────────────────────────

@pytest.fixture
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the planner needs real Postgres")
    from genios_engine.platform.db import get_engine
    with get_engine(live_db_url).connect() as c:
        yield c


def test_a_valid_statement_plans(conn):
    assert sp.plan(conn, "select card_id, headline from cards where org_id = :o and state = :s") \
        is None


def test_a_column_that_does_not_exist_is_reported(conn):
    err = sp.plan(conn, "select card_id, nosuch from cards where org_id = :o")
    assert err is not None and 'column "nosuch" does not exist' in err


def test_a_table_that_does_not_exist_is_reported(conn):
    err = sp.plan(conn, "select 1 from nosuch_table where org_id = :o")
    assert err is not None and 'relation "nosuch_table" does not exist' in err


def test_the_b1_shape_a_cte_that_never_projected_the_column_fails(conn):
    """STEP-18 B1 in miniature: a CTE that does not carry `card_level`, and a reader that filters
    on it. Postgres refuses it at PREPARE — before any row exists."""
    err = sp.plan(conn, "with canonical as (select card_id from cards where org_id = :o) "
                        "select count(*) filter (where card_level = 'prescriptive') from canonical")
    assert err is not None and 'column "card_level" does not exist' in err


def test_a_double_colon_cast_on_a_bind_fails_as_it_would_in_production(conn):
    err = sp.plan(conn, "select :x::int")
    assert err is not None and "syntax error" in err


def test_an_expanding_in_plans(conn):
    assert sp.plan(conn, "select card_id from cards where org_id = :o and card_id in :ids") is None


def test_a_bind_postgres_cannot_type_alone_is_typed_by_a_typing_that_plans(conn):
    """At run time psycopg sends `:d` as an integer and `:base` as an interval. Untyped, Postgres
    guesses wrong (`date - date`, `unknown * double`) — the search finds a typing that plans."""
    assert sp.plan(conn, "delete from rate_counters where kind = any(cast(:k as text[])) "
                         "and window_start < current_date - :d") is None
    assert sp.plan(conn, "select 1 from parked_events pe where coalesce("
                         "pe.refetch_next_attempt_at, pe.created_at + :base * power(2, 3)) <= :now"
                   ) is None


def test_a_missing_column_is_never_typed_away(conn, monkeypatch):
    """Not retried at all: a column error is answered by the first attempt and no typing is tried —
    the search is for type errors only."""
    attempts: list[list[str]] = []
    real = sp._attempt

    def counting(c, sql, types):
        attempts.append(list(types))
        return real(c, sql, types)

    monkeypatch.setattr(sp, "_attempt", counting)
    err = sp.plan(conn, "select nosuch from screen_thread_verdicts where org_id = :o "
                        "and judged_at > :now")
    assert err is not None and 'column "nosuch" does not exist' in err
    assert attempts == [["unknown", "unknown"]]


def test_a_bind_with_no_context_at_all_is_text(conn, monkeypatch):
    """`:a is null` gives Postgres nothing to type `:a` from — any number of them, each made text
    in turn, which is what psycopg sends for a str; a bind Postgres types itself is left alone."""
    attempts: list[list[str]] = []
    real = sp._attempt

    def counting(c, sql, types):
        attempts.append(list(types))
        return real(c, sql, types)

    monkeypatch.setattr(sp, "_attempt", counting)
    assert sp.plan(conn, "select 1 from cards where (:a is null or org_id = :o) "
                         "and :b is null and :c is null") is None
    assert attempts[-1] == ["text", "unknown", "text", "text"], attempts


def test_an_error_only_the_planner_raises_is_reported(conn):
    """PREPARE only analyses; some statements are refused by the PLANNER — a FULL JOIN on a
    condition it cannot merge or hash. That is why the statement is EXPLAINed, not only prepared."""
    err = sp.plan(conn, "select 1 from cards a full join cards b on a.created_at > b.created_at")
    assert err is not None and "FULL JOIN is only supported" in err


def test_planning_writes_nothing_and_leaves_the_connection_clean(conn):
    before = conn.execute(text("select count(*) from orgs")).scalar()
    conn.commit()
    assert sp.plan(conn, "insert into orgs (id, name) values (:id, :name)") is None
    assert conn.execute(text("select count(*) from orgs")).scalar() == before
    assert conn.execute(text("select count(*) from pg_prepared_statements")).scalar() == 0
    conn.commit()
    err = sp.plan(conn, "select nosuch from cards")
    assert err is not None
    assert not conn.in_transaction()
    assert conn.execute(text("select count(*) from pg_prepared_statements")).scalar() == 0
