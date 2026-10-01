r"""⛔ One unrunnable receipt must not take every receipt after it.

WHAT THIS CATCHES. Measured against production 2026-10-01, before the fix:

    {'PASS': 12, 'FAIL': 4, 'ERROR': 13}   of 29

Migration `0190` is unapplied, so the L5 lane receipt raised `UndefinedColumn` — **correctly, once.**
Then **twelve** further receipts reported `InFailedSqlTransaction`: SQLAlchemy opens an implicit
transaction on first use, and a statement that raises leaves it invalid for every statement after it
on the same connection.

    after the fix:  {'PASS': 20, 'FAIL': 8, 'ERROR': 1}   of 29

**Twelve phantom ERRORs were hiding four real FAILs and one real ERROR.** `api/routes.py:161` computes
`ready = not failed` from this list, so the operator page said thirteen things were broken when one was
— and named the wrong twelve.

⛔ IT IS THE SAME DEFECT `domain_shadow` ALREADY FIXED FOR ITS OWN LOOP: *"ONE connection serves the
whole loop … a single bad situation silently takes every situation after it … The six missing
situations were not unroutable; **they were never attempted**."*
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest
from sqlalchemy import text

from genios_engine.platform import receipts as R

REPO = pathlib.Path(__file__).resolve().parents[2]


class _PoisonedConnection:
    """A connection that goes invalid after one failure, the way a real one does.

    ⛔ MODELLED, NOT MOCKED AWAY. The behaviour under test is a property of the transaction, so a
    stub that forgives the second statement would make the test pass against the bug.
    """

    def __init__(self, fail_on: str) -> None:
        self.fail_on = fail_on
        self.invalid = False
        self.rollbacks = 0
        self.attempted: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.attempted.append(sql)
        if self.invalid:
            raise RuntimeError("InFailedSqlTransaction: current transaction is aborted")
        if self.fail_on in sql:
            self.invalid = True
            raise RuntimeError("UndefinedColumn: column does not exist")

        class _R:
            @staticmethod
            def scalar():
                return 0
        return _R()

    def rollback(self):
        self.rollbacks += 1
        self.invalid = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Engine:
    def __init__(self, conn) -> None:
        self._conn = conn

    def connect(self):
        return self._conn


def _first_sql_fragment() -> str:
    """A fragment present in exactly one receipt's SQL, used as the poison trigger."""
    return "output_lane is null"


def test_the_reset_happens_after_every_receipt_not_only_the_broken_ones():
    """⛔ IN `finally`, NOT IN `except`. A receipt whose query SUCCEEDS still leaves an open implicit
    transaction; resetting only on the failure path would leave a successful receipt holding one, and
    the next failure would be attributed to whichever receipt happened to be running."""
    tree = ast.parse(inspect.getsource(R.evaluate))
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    assert tries, "evaluate no longer guards each receipt"
    rollback_in_finally = any(
        "rollback" in ast.unparse(stmt) for node in tries for stmt in node.finalbody)
    assert rollback_in_finally, "the connection reset is not in `finally`"


def test_one_failure_does_not_turn_every_later_receipt_into_an_error():
    """⛔ THE WHOLE TEST. Driven through a connection that genuinely goes invalid."""
    conn = _PoisonedConnection(fail_on=_first_sql_fragment())
    rows = R.evaluate(_Engine(conn), None)

    errors = [r for r in rows if r["status"] == "ERROR"]
    assert len(errors) == 1, (
        f"{len(errors)} receipts reported ERROR; exactly one query was broken. "
        f"{[r['claim'] for r in errors][:4]}")
    assert "column does not exist" in errors[0]["detail"]


def test_every_receipt_is_still_attempted_after_a_failure():
    """*The six missing situations were not unroutable; they were never attempted.*"""
    conn = _PoisonedConnection(fail_on=_first_sql_fragment())
    rows = R.evaluate(_Engine(conn), None)
    assert len(conn.attempted) == len(R.receipts(None))
    assert len(rows) == len(R.receipts(None))


def test_the_connection_is_reset_once_per_receipt():
    conn = _PoisonedConnection(fail_on="a fragment no receipt contains")
    R.evaluate(_Engine(conn), None)
    assert conn.rollbacks == len(R.receipts(None))


def test_a_reset_on_a_healthy_connection_is_a_no_op_so_no_flag_guards_it():
    """⛔ The reason it is unconditional, and the same reason `domain_shadow` gives: a flag somebody
    must keep correct is a flag that will one day be wrong."""
    src = inspect.getsource(R.evaluate)
    assert "if " not in src.split("finally:")[1].split("return")[0], (
        "the reset is conditional; it must be unconditional")


def test_an_unrunnable_receipt_is_still_reported_as_a_finding():
    """The docstring's own promise — *an unrunnable one is a finding (ERROR), never a skip* — must
    survive the fix. Swallowing it would turn a broken deployment into a green page."""
    conn = _PoisonedConnection(fail_on=_first_sql_fragment())
    rows = R.evaluate(_Engine(conn), None)
    assert any(r["status"] == "ERROR" for r in rows)
    assert all(r["claim"] for r in rows)


def test_the_real_error_today_is_the_unapplied_migration_and_it_is_named():
    """⛔ PINNED. The one true ERROR against production is `0190` being unapplied — `cards.output_lane`
    does not exist. If this stops being the case, the migration was applied; good, and the pin should
    move rather than be deleted."""
    lane = [r for r in R.receipts(None) if "carries a lane" in r.claim]
    assert len(lane) == 1
    assert "output_lane" in lane[0].sql

