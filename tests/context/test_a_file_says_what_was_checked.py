"""STEP-10 · a file says what was checked — "no reply" only when a mailbox covers it and its last sync finished.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_says_what_was_checked.py -q

`context/coverage_receipt.receipt_for` and `covers` (tree `yc2_w27_s10 · M29.C5.L-logic.V2.U03`). A
file said *"no reply"* with nothing beside it to say what was looked at: on the golden set no
card carried a coverage line (`STEP-10` §8.1), and a pitch sent before the mailbox's window opened,
or answered after its last sync, read exactly like one that was never answered. Now a tenant's
receipt names, per connected mailbox, its connection, its address when the row has one, the window
it is set to sweep, the oldest instant that window covers, when its last sync finished and whether
that sync completed — and `covers` lets a file say "no reply since then" only when some mailbox's
window reaches back that far and a sync that completed has looked since. No mailbox: an empty
receipt, and nothing is covered. Read only.
"""
from __future__ import annotations

import contextlib
import inspect
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import coverage_receipt as R

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "org_s10_receipt"
OTHER = "org_s10_receipt_other"


def _receipt(*, window_days=60, finished=NOW - timedelta(hours=2), completed=True,
             cid="con_a"):
    return R.MailboxReceipt(
        connection_id=cid, address=None, window_days=window_days,
        window_start=None if window_days is None else NOW - timedelta(days=window_days),
        last_finished_at=finished, last_completed=completed)


# =================================================================================================
# `covers` — the window reaches back far enough, and a completed sync has looked since
# =================================================================================================

def test_covers_needs_the_window_to_reach_back_to_since():
    receipt = _receipt(window_days=60)
    assert R.covers([receipt], NOW - timedelta(days=10))
    assert R.covers([receipt], NOW - timedelta(days=60)), "the window's own first instant"
    assert not R.covers([receipt], NOW - timedelta(days=61)), (
        "mail from before the window was vouched for")


def test_covers_needs_the_last_sync_to_have_completed():
    assert not R.covers([_receipt(completed=False)], NOW - timedelta(days=10))


def test_covers_needs_a_sync_that_finished_after_since():
    """A pitch sent an hour ago, a last sync two hours ago: nothing has been read since it went."""
    receipt = _receipt(finished=NOW - timedelta(hours=2))
    assert not R.covers([receipt], NOW - timedelta(hours=1))
    assert R.covers([receipt], NOW - timedelta(hours=2))


def test_one_mailbox_that_covers_it_is_enough():
    assert R.covers([_receipt(cid="con_a", completed=False), _receipt(cid="con_b")],
                    NOW - timedelta(days=10))


def test_a_mailbox_whose_window_cannot_be_read_covers_nothing():
    assert not R.covers([_receipt(window_days=None)], NOW - timedelta(days=10))


def test_no_receipt_covers_nothing():
    assert not R.covers([], NOW - timedelta(days=10))


def test_a_sync_cannot_have_completed_without_finishing():
    with pytest.raises(ValueError):
        _receipt(finished=None, completed=True)


class _Result:
    def __init__(self, rows): self._rows = list(rows)
    def fetchall(self): return self._rows
    def first(self): return self._rows[0] if self._rows else None


class _Scripted:
    """A connection that answers each read by a phrase in its SQL, or raises what it is given."""

    def __init__(self, answers: dict):
        self._answers = answers

    def begin_nested(self):
        """Every read is a savepoint; a scripted connection has nothing to roll back."""
        return contextlib.nullcontext()

    def execute(self, stmt, params=None):
        sql = str(stmt)
        for phrase, answer in self._answers.items():
            if phrase in sql:
                if isinstance(answer, Exception):
                    raise answer
                return _Result(answer)
        raise AssertionError(f"a read the receipt was not expected to make: {sql}")


def _row(**kw):
    return type("R", (), kw)()


_A_MAILBOX = {"status = 'connected'": [_row(connection_id="con_a", source_type="gmail")]}


def test_a_tenant_whose_connections_cannot_be_read_has_an_empty_receipt():
    conn = _Scripted({"status = 'connected'": RuntimeError("relation connections does not exist")})
    assert R.receipt_for(conn, ORG, now=NOW) == []


def test_a_mailbox_whose_row_is_gone_by_the_time_it_is_read_is_left_off():
    assert R.receipt_for(_Scripted({**_A_MAILBOX, "external_account_id": []}), ORG,
                         now=NOW) == []


def test_a_mailbox_whose_last_sync_cannot_be_read_has_not_completed():
    conn = _Scripted({**_A_MAILBOX,
                      "external_account_id": [_row(source_type="gmail", external_account_id=None,
                                                   capture_scope={})],
                      "mode, scanned": [], "bool_or": RuntimeError("statement timeout")})
    (receipt,) = R.receipt_for(conn, ORG, now=NOW)
    assert (receipt.last_finished_at, receipt.last_completed) == (None, False)


def test_the_receipt_only_reads():
    """Every statement in the module is a select: a receipt that could write would be asserting a
    sweep that never happened."""
    from genios_engine.platform import table_coverage as TC

    statements = TC._statements(inspect.getsource(R), TC._known_tables())
    assert statements, "the counter found no SQL — the guard is measuring nothing"
    for sql, _holes in statements:
        assert sql.lstrip().lower().startswith("select"), sql


# =================================================================================================
# `receipt_for` — real rows
# =================================================================================================

@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt reads Postgres")
    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)

    def _drop():
        with engine.begin() as conn:      # connections and l1_sync_runs cascade from the org
            conn.execute(text("delete from orgs where id in (:o, :x)"), {"o": ORG, "x": OTHER})

    _drop()
    with engine.begin() as conn:
        cols = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        for org in (ORG, OTHER):
            names, params = ["id"], {"id": org}
            for col in cols:
                names.append(col.column_name)
                params[col.column_name] = (0 if "int" in col.data_type
                                           or "numeric" in col.data_type
                                           else NOW if "timestamp" in col.data_type else org)
            conn.execute(text(f"insert into orgs ({', '.join(names)}) values "
                              f"({', '.join(':' + n for n in names)})"), params)
    yield engine
    _drop()


def _connection(engine, cid: str, *, org: str = ORG, source: str = "gmail",
                address: str | None = None, scope: dict | None = None,
                status: str = "connected") -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "insert into connections (connection_id, org_id, source_type, external_account_id, "
            "capture_scope, status) values (:c, :o, :s, :a, cast(:scope as jsonb), :st)"),
            {"c": cid, "o": org, "s": source, "a": address, "scope": json.dumps(scope or {}),
             "st": status})


def _run(engine, cid: str, finished_at: datetime, *, tag: str = "", org: str = ORG,
         exhausted: bool | None = True, error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, scanned, "
            "claimed_total, cursor_exhausted, error, started_at, finished_at) "
            "values (:r, :o, :c, 'gmail', 'incremental', 1, 1, :cx, :err, :fin, :fin)"),
            {"r": f"run_{org}_{cid}_{finished_at.isoformat()}{tag}", "o": org, "c": cid,
             "cx": exhausted, "err": error, "fin": finished_at})


def _receipts(engine, **kw) -> list:
    kw.setdefault("now", NOW)
    with engine.connect() as conn:
        return R.receipt_for(conn, ORG, **kw)


@pytest.mark.pg
def test_a_tenant_with_no_mailbox_has_an_empty_receipt_and_nothing_is_covered(pg):
    assert _receipts(pg) == []
    _connection(pg, "con_cal", source="gcal")
    _run(pg, "con_cal", NOW - timedelta(hours=1))
    assert _receipts(pg) == [], "a calendar swept end to end still says nothing about a reply"
    assert not R.covers(_receipts(pg), NOW - timedelta(days=1))


@pytest.mark.pg
@pytest.mark.parametrize("source", ["gmail", "outlook", "imap", "inkbox"])
def test_every_mail_source_is_a_mailbox(pg, source):
    _connection(pg, "con_mail", source=source)
    assert [r.connection_id for r in _receipts(pg)] == ["con_mail"]


@pytest.mark.pg
def test_each_connected_mailbox_says_what_it_checked(pg):
    _connection(pg, "con_a", address="Founder@Kestrel.test")
    _connection(pg, "con_b", scope={"backfill_days": 30})
    _connection(pg, "con_gone", status="disconnected")
    _connection(pg, "con_theirs", org=OTHER)
    _run(pg, "con_a", NOW - timedelta(hours=2))
    _run(pg, "con_gone", NOW - timedelta(hours=1))
    assert _receipts(pg) == [
        R.MailboxReceipt(connection_id="con_a", address="founder@kestrel.test", window_days=60,
                         window_start=NOW - timedelta(days=60),
                         last_finished_at=NOW - timedelta(hours=2), last_completed=True),
        R.MailboxReceipt(connection_id="con_b", address=None, window_days=30,
                         window_start=NOW - timedelta(days=30), last_finished_at=None,
                         last_completed=False)]


@pytest.mark.pg
def test_the_last_sync_is_the_latest_one_finished_by_the_instant_asked(pg):
    _connection(pg, "con_a")
    _run(pg, "con_a", NOW - timedelta(days=3))
    _run(pg, "con_a", NOW - timedelta(days=1), exhausted=None, error="429 rate limited")
    _run(pg, "con_a", NOW + timedelta(hours=1))
    (receipt,) = _receipts(pg)
    assert (receipt.last_finished_at, receipt.last_completed) == (NOW - timedelta(days=1), False)
    (later,) = _receipts(pg, now=NOW + timedelta(hours=1))
    assert (later.last_finished_at, later.last_completed) == (NOW + timedelta(hours=1), True)


@pytest.mark.pg
@pytest.mark.parametrize("exhausted", [False, None])
def test_a_sync_that_stopped_with_mail_left_or_cannot_say_did_not_complete(pg, exhausted):
    _connection(pg, "con_a")
    _run(pg, "con_a", NOW - timedelta(hours=1), exhausted=exhausted)
    assert _receipts(pg)[0].last_completed is False


@pytest.mark.pg
def test_rounds_frozen_at_one_instant_completed_when_one_ran_out_of_mail_and_none_failed(pg):
    """A replay freezes every round of a backfill at the case's instant, so "the last sync" is
    that instant, whichever row the database hands back first."""
    _connection(pg, "con_a")
    _connection(pg, "con_b")
    at = NOW - timedelta(hours=1)
    _run(pg, "con_a", at, tag="_round1", exhausted=None)
    _run(pg, "con_a", at, tag="_round2", exhausted=True)
    _run(pg, "con_b", at, tag="_ok", exhausted=True)
    _run(pg, "con_b", at, tag="_failed", exhausted=None, error="boom")
    a, b = _receipts(pg)
    assert (a.last_finished_at, a.last_completed) == (at, True)
    assert (b.last_finished_at, b.last_completed) == (at, False)


@pytest.mark.pg
def test_the_receipt_can_be_asked_for_a_files_own_mailboxes(pg):
    _connection(pg, "con_a")
    _connection(pg, "con_b")
    _connection(pg, "con_cal", source="gcal")
    _connection(pg, "con_theirs", org=OTHER)
    assert [r.connection_id for r in _receipts(pg, connection_ids=["con_b"])] == ["con_b"]
    assert _receipts(pg, connection_ids=()) == [], "an empty selection is not every mailbox"
    assert _receipts(pg, connection_ids=["con_cal", "con_theirs"]) == []


class _Recording:
    """The real connection, keeping the parameters of every read it is asked to make."""

    def __init__(self, conn):
        self._conn, self.params = conn, []

    def begin_nested(self):
        return self._conn.begin_nested()

    def execute(self, stmt, params=None):
        self.params.append(dict(params or {}))
        return self._conn.execute(stmt, params)


@pytest.mark.pg
def test_the_receipt_never_reads_another_tenants_mailbox(pg):
    """Not even to discard it a read later: another tenant's connection is never asked about."""
    _connection(pg, "con_a")
    _connection(pg, "con_theirs", org=OTHER)
    with pg.connect() as conn:
        recording = _Recording(conn)
        assert [r.connection_id for r in R.receipt_for(recording, ORG, now=NOW)] == ["con_a"]
    assert not [p for p in recording.params if "con_theirs" in p.values()]


@pytest.mark.pg
def test_another_tenants_runs_under_the_same_connection_id_are_not_this_mailboxs_last_sync(pg):
    _connection(pg, "con_a")
    _run(pg, "con_a", NOW - timedelta(days=2))
    _run(pg, "con_a", NOW - timedelta(hours=1), org=OTHER, exhausted=None, error="boom")
    (receipt,) = _receipts(pg)
    assert (receipt.last_finished_at, receipt.last_completed) == (NOW - timedelta(days=2), True)


@pytest.mark.pg
def test_no_reply_is_said_only_when_a_mailbox_covers_it_and_its_last_sync_finished(pg):
    """The goal, end to end: a pitch inside the window with a completed sync after it is covered;
    one before the window opened is not; and a failed last sync takes the licence back."""
    _connection(pg, "con_a")
    _run(pg, "con_a", NOW - timedelta(hours=2))
    assert R.covers(_receipts(pg), NOW - timedelta(days=25))
    assert not R.covers(_receipts(pg), NOW - timedelta(days=70))
    _run(pg, "con_a", NOW - timedelta(hours=1), exhausted=None, error="401 credentials revoked")
    assert not R.covers(_receipts(pg), NOW - timedelta(days=25))
