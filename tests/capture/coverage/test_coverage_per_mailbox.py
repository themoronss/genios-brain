"""STEP-10 · coverage is read per mailbox, over that mailbox's own window, and never reads more than it counts.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/coverage/test_coverage_per_mailbox.py -q

`capture/coverage/window` (tree `yc2_w27_s10 · M29.C5.L-logic.V1.U02`). The window read was per SOURCE —
two Gmail mailboxes were one window — over an interval its caller chose, and it summed what every run
read against the LARGEST total any one run was told. That is right for the rounds of one backfill, which
each re-count the same query, and wrong for everything else: an incremental sweep's total counts its own
new mail, so F14's two sweeps (1 of 1, then 3 of 3) read *"read 4 of about 3"*. A provider's count can
also be lower than what was read — an estimate that runs low, a message and its attachment landing as
two objects against one counted message — and the sentence then said so in its numbers. Now each run is
measured against its own total (a backfill's rounds against their one total), a total lower than what
was read is raised to it and called an estimate, a slice read with no total leaves the window with none,
and one mailbox — one `connections` row, its address when the row has one — is read over its own
`backfill_days` window as of an instant.
"""
from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.coverage.window import SyncHealth, WindowCoverage, coverage_for_window

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "org_s10_coverage_mailbox"
OTHER = "org_s10_coverage_mailbox_other"


@dataclass
class _Run:
    """One `l1_sync_runs` row as the window read selects it."""
    mode: str | None = "incremental"
    scanned: int = 0
    claimed_total: int | None = None
    claimed_is_estimate: bool = True
    cursor_exhausted: bool | None = True
    page_budget_spent: bool = False
    error: str | None = None
    connection_id: str | None = "con_a"


class _Conn:
    def __init__(self, rows): self._rows = rows
    def execute(self, *_a, **_k): return self
    def fetchall(self): return self._rows


def _window(*runs: _Run) -> WindowCoverage:
    return coverage_for_window(_Conn(list(runs)), org_id=ORG, source="gmail",
                               since=NOW - timedelta(days=60), until=NOW)


# =================================================================================================
# The measure — every run against its own total
# =================================================================================================

def test_two_incremental_sweeps_never_read_more_than_they_were_told_exists():
    """F14: each sweep's total counts its own new mail, so the window's total is their sum."""
    cov = _window(_Run(scanned=1, claimed_total=1), _Run(scanned=3, claimed_total=3))
    assert (cov.indexed, cov.claimed_total, cov.completeness_bp) == (4, 4, 10_000)
    assert cov.describe() == "read 4 of about 4 from gmail"


def test_the_rounds_of_one_backfill_still_share_its_one_total():
    """Every round re-counts the same query: adding the counts would triple the mailbox."""
    cov = _window(*(_Run(mode="backfill", scanned=n, claimed_total=465) for n in (200, 200, 65)))
    assert (cov.indexed, cov.claimed_total) == (465, 465)


def test_a_run_that_does_not_say_its_mode_is_read_as_a_backfill_round():
    """The rule rows were read by before modes were read: one shared total."""
    cov = _window(_Run(mode=None, scanned=20, claimed_total=465),
                  _Run(mode=None, scanned=17, claimed_total=465))
    assert (cov.indexed, cov.claimed_total) == (37, 465)


def test_two_mailboxes_backfills_add_up_rather_than_the_larger_hiding_the_smaller():
    cov = _window(_Run(mode="backfill", scanned=100, claimed_total=100, connection_id="con_a"),
                  _Run(mode="backfill", scanned=50, claimed_total=50, connection_id="con_b"))
    assert (cov.indexed, cov.claimed_total) == (150, 150)


def test_a_count_lower_than_what_was_read_is_raised_to_it_and_called_an_estimate():
    """A message and its attachment are two objects against one counted message; an exact count
    that ends up below what was read is no longer the provider's number, so it is labelled ours."""
    cov = _window(_Run(scanned=4, claimed_total=3, claimed_is_estimate=False))
    assert (cov.indexed, cov.claimed_total, cov.is_estimate) == (4, 4, True)
    assert cov.describe() == "read 4 of about 4 from gmail"


def test_an_exact_count_that_holds_stays_exact():
    cov = _window(_Run(scanned=3, claimed_total=3, claimed_is_estimate=False))
    assert (cov.claimed_total, cov.is_estimate) == (3, False)
    assert cov.describe() == "read 3 of 3 from gmail"


def test_a_slice_read_with_no_count_leaves_the_window_without_one():
    """Its mail would sit in the numerator over a total that never counted it."""
    cov = _window(_Run(scanned=4, claimed_total=4), _Run(scanned=3, claimed_total=None))
    assert (cov.indexed, cov.claimed_total, cov.completeness_bp) == (7, None, None)
    assert cov.describe() == "read 7 from gmail; the provider gave no total"


def test_a_count_of_zero_beside_mail_read_is_no_count():
    cov = _window(_Run(scanned=5, claimed_total=0))
    assert (cov.claimed_total, cov.completeness_bp) == (None, None)


def test_a_slice_that_read_nothing_adds_nothing_either_way():
    """An empty poll — nothing new and no count, or a count of none — leaves the total alone."""
    assert _window(_Run(scanned=0, claimed_total=None),
                   _Run(scanned=3, claimed_total=3)).claimed_total == 3
    assert _window(_Run(scanned=0, claimed_total=0),
                   _Run(scanned=3, claimed_total=3)).claimed_total == 3
    assert _window(_Run(scanned=0, claimed_total=0)).claimed_total == 0


def test_a_poll_that_read_nothing_and_was_told_nothing_has_no_total_rather_than_zero():
    cov = _window(_Run(scanned=0, claimed_total=None))
    assert cov.claimed_total is None
    assert cov.describe() == "read 0 from gmail; the provider gave no total"


class _TextScope:
    """A driver that hands `capture_scope` back as text, then has no runs to show."""

    def __init__(self, scope: str):
        self._row = type("R", (), {"source_type": "gmail", "external_account_id": None,
                                   "capture_scope": scope})()

    def execute(self, *_a, **_k):
        return self

    def begin_nested(self):
        """Every read is a savepoint (`window._optional`); this driver has nothing to roll back."""
        return contextlib.nullcontext()

    def first(self):
        return self._row

    def fetchall(self):
        return []


def test_a_window_setting_stored_as_text_reads_like_one_stored_as_an_object():
    from genios_engine.capture.coverage.window import coverage_for_connection

    cov = coverage_for_connection(_TextScope('{"backfill_days": 30}'), org_id=ORG,
                                  connection_id="con_a", now=NOW)
    assert (cov.window_days, cov.window_start) == (30, NOW - timedelta(days=30))


@pytest.mark.parametrize("runs", [
    (_Run(scanned=1, claimed_total=1), _Run(scanned=3, claimed_total=3)),
    (_Run(scanned=9, claimed_total=2), _Run(mode="backfill", scanned=50, claimed_total=40)),
    (_Run(mode="backfill", scanned=300, claimed_total=100),
     _Run(mode="backfill", scanned=300, claimed_total=100)),
    (_Run(scanned=7, claimed_total=7), _Run(scanned=0, claimed_total=None),
     _Run(mode="recovery", scanned=12, claimed_total=5)),
])
def test_no_window_ever_says_it_read_more_than_exists(runs):
    """"Read 4 of about 3" no more: whatever the mix, the numerator never passes the total."""
    cov = _window(*runs)
    assert cov.claimed_total is not None and cov.indexed <= cov.claimed_total
    assert cov.completeness_bp is not None and cov.completeness_bp <= 10_000


# =================================================================================================
# One mailbox, its own window — real rows
# =================================================================================================

@pytest.fixture
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the per-mailbox read needs Postgres")
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


def _connection(engine, cid: str, *, org: str = ORG, address: str | None = None,
                scope: dict | None = None, source: str = "gmail") -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "insert into connections (connection_id, org_id, source_type, external_account_id, "
            "capture_scope) values (:c, :o, :s, :a, cast(:scope as jsonb))"),
            {"c": cid, "o": org, "s": source, "a": address, "scope": json.dumps(scope or {})})


def _run(engine, cid: str, finished_at: datetime, *, org: str = ORG, mode: str = "incremental",
         scanned: int = 1, claimed: int | None = 1, exhausted: bool | None = True,
         error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, scanned, "
            "claimed_total, claimed_is_estimate, cursor_exhausted, error, started_at, finished_at) "
            "values (:r, :o, :c, 'gmail', :m, :sc, :ct, true, :cx, :err, :fin, :fin)"),
            {"r": f"run_{cid}_{finished_at.isoformat()}_{mode}", "o": org, "c": cid, "m": mode,
             "sc": scanned, "ct": claimed, "cx": exhausted, "err": error, "fin": finished_at})


def _mailbox(engine, cid: str, *, org: str = ORG, now: datetime = NOW) -> WindowCoverage | None:
    from genios_engine.capture.coverage.window import coverage_for_connection

    with engine.connect() as conn:
        return coverage_for_connection(conn, org_id=org, connection_id=cid, now=now)


@pytest.mark.pg
def test_a_mailbox_is_read_from_its_own_runs_and_not_its_sources(pg):
    _connection(pg, "con_a")
    _connection(pg, "con_b")
    _run(pg, "con_a", NOW - timedelta(days=2), scanned=1, claimed=1)
    _run(pg, "con_a", NOW - timedelta(days=1), scanned=3, claimed=3)
    _run(pg, "con_b", NOW - timedelta(days=1), scanned=40, claimed=50)
    a = _mailbox(pg, "con_a")
    assert (a.connection_id, a.source, a.runs, a.indexed, a.claimed_total) == ("con_a", "gmail",
                                                                              2, 4, 4)
    assert a.health is SyncHealth.HEALTHY and a.describe() == "read 4 of about 4 from gmail"
    assert _mailbox(pg, "con_b").indexed == 40


@pytest.mark.pg
def test_a_mailboxs_backfill_and_its_sweeps_are_each_measured_against_their_own_count(pg):
    """Off the real table: the mode the measure groups by has to be read, not defaulted."""
    _connection(pg, "con_a")
    for hour in (1, 2):
        _run(pg, "con_a", NOW - timedelta(days=5, hours=hour), mode="backfill", scanned=100,
             claimed=465)
    _run(pg, "con_a", NOW - timedelta(days=1), scanned=3, claimed=3)
    cov = _mailbox(pg, "con_a")
    assert (cov.indexed, cov.claimed_total) == (203, 468)


@pytest.mark.pg
def test_the_per_source_read_measures_real_rows_the_same_way(pg):
    """Off the real table, per source: F14's two sweeps, and two mailboxes' backfills."""
    _connection(pg, "con_a")
    _connection(pg, "con_b")
    _run(pg, "con_a", NOW - timedelta(days=3), scanned=1, claimed=1)
    _run(pg, "con_a", NOW - timedelta(days=2), scanned=3, claimed=3)
    _run(pg, "con_a", NOW - timedelta(days=9), mode="backfill", scanned=100, claimed=200)
    _run(pg, "con_b", NOW - timedelta(days=9), mode="backfill", scanned=50, claimed=80)
    with pg.connect() as conn:
        cov = coverage_for_window(conn, org_id=ORG, source="gmail",
                                  since=NOW - timedelta(days=60), until=NOW)
    assert (cov.runs, cov.indexed, cov.claimed_total) == (4, 154, 284)


@pytest.mark.pg
def test_the_window_is_the_mailboxs_own_setting_and_sixty_days_when_it_has_none(pg):
    _connection(pg, "con_short", scope={"backfill_days": 30})
    _connection(pg, "con_default")
    for cid in ("con_short", "con_default"):
        for days, scanned in ((10, 1), (40, 10), (59, 100), (61, 1000)):
            _run(pg, cid, NOW - timedelta(days=days), scanned=scanned, claimed=scanned)
    short, default = _mailbox(pg, "con_short"), _mailbox(pg, "con_default")
    assert (short.window_days, short.window_start, short.window_end) == (
        30, NOW - timedelta(days=30), NOW)
    assert short.indexed == 1, "a run from before its own window was counted"
    assert (default.window_days, default.window_start, default.indexed) == (
        60, NOW - timedelta(days=60), 111)


@pytest.mark.pg
def test_the_window_is_read_as_of_the_instant_asked_including_a_run_that_ends_at_it(pg):
    """A replay asks as of its case's instant: the sweep that finished at it is in, a later one
    is not, and one exactly at the window's far edge read mail from before it."""
    _connection(pg, "con_a", scope={"backfill_days": 30})
    _run(pg, "con_a", NOW, scanned=2, claimed=2)
    _run(pg, "con_a", NOW + timedelta(hours=1), scanned=20, claimed=20)
    _run(pg, "con_a", NOW - timedelta(days=30), scanned=200, claimed=200)
    cov = _mailbox(pg, "con_a")
    assert (cov.runs, cov.indexed) == (1, 2)


@pytest.mark.pg
def test_a_mailbox_says_its_address_when_its_row_has_one(pg):
    _connection(pg, "con_named", address="  Founder@Kestrel.TEST ")
    _connection(pg, "con_unnamed")
    _connection(pg, "con_account_id", address="ca_7f3a")
    assert _mailbox(pg, "con_named").address == "founder@kestrel.test"
    assert _mailbox(pg, "con_unnamed").address is None
    assert _mailbox(pg, "con_account_id").address is None, "an account id is not an address"


@pytest.mark.pg
def test_a_mailbox_with_no_sync_in_its_window_is_unknown_and_never_complete(pg):
    _connection(pg, "con_quiet")
    cov = _mailbox(pg, "con_quiet")
    assert (cov.runs, cov.health, cov.completeness_bp) == (0, SyncHealth.UNKNOWN, None)


@pytest.mark.pg
def test_one_failed_sweep_in_the_mailboxs_window_is_its_health(pg):
    _connection(pg, "con_a")
    _run(pg, "con_a", NOW - timedelta(days=3), scanned=0, claimed=None, error="429 rate limited")
    _run(pg, "con_a", NOW - timedelta(days=1), scanned=3, claimed=3)
    assert _mailbox(pg, "con_a").health is SyncHealth.FAILED


@pytest.mark.pg
def test_a_connection_the_tenant_does_not_have_has_no_coverage(pg):
    _connection(pg, "con_theirs", org=OTHER)
    _run(pg, "con_theirs", NOW - timedelta(days=1), org=OTHER, scanned=9, claimed=9)
    assert _mailbox(pg, "con_nobody") is None
    assert _mailbox(pg, "con_theirs") is None, "the read crossed a tenant"


@pytest.mark.pg
def test_another_tenants_runs_under_the_same_connection_id_are_not_this_mailboxs(pg):
    """A run's connection id is no foreign key — every golden tenant syncs as
    `conn_golden_gmail` — so the runs are read by tenant as well as by connection."""
    _connection(pg, "con_a")
    _run(pg, "con_a", NOW - timedelta(days=1), scanned=3, claimed=3)
    _run(pg, "con_a", NOW - timedelta(days=1), org=OTHER, mode="backfill", scanned=70,
         claimed=90)
    assert (_mailbox(pg, "con_a").runs, _mailbox(pg, "con_a").indexed) == (1, 3)


@pytest.mark.pg
def test_a_window_setting_that_cannot_be_read_is_an_unknown_window_not_the_default(pg):
    """A typo'd admin setting fails the connector loudly; the coverage read must not quietly
    restore sixty days and vouch for a window nobody configured."""
    _connection(pg, "con_typo", scope={"backfill_days": "sixty"})
    _run(pg, "con_typo", NOW - timedelta(days=1), scanned=3, claimed=3)
    cov = _mailbox(pg, "con_typo")
    assert (cov.window_days, cov.window_start, cov.runs, cov.health) == (
        None, None, 0, SyncHealth.UNKNOWN)
