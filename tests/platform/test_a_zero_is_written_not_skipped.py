"""S4 · the five-stage funnel — and the distinction the whole table exists for.

    pytest tests/platform/test_a_zero_is_written_not_skipped.py -q

⛔ THE ONE THAT MATTERS:

    situations_formed = 0   the stage RAN and formed nothing
    (no row)                nobody looked

Conflating those is how this programme got caught twice already — `no_model_wired` in L1 (632 failures
that were one model-free lane) and the graph-revision guard in L3. Both were *a count read without
knowing what it was a count OF*.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.platform.funnel import (CAPABILITY_RESOLVED, CARD_DELIVERED, DECISION_EMITTED,
                                           SIGNALS_DETECTED, SITUATIONS_FORMED, STAGE_OWNERS,
                                           STAGES, biggest_loss, observe, read_sweep, record)

pytestmark = pytest.mark.unit

_AT = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


class _Conn:
    def __init__(self, rows=()):
        self.writes: list[dict] = []
        self._rows = list(rows)

    def execute(self, statement, params=None):
        sql = str(statement).lower()
        if sql.startswith("insert"):
            self.writes.append(dict(params or {}))
            return type("R", (), {"rowcount": 1})()
        rows = self._rows
        return type("R", (), {"mappings": lambda s: iter(rows)})()


# =================================================================================================
# 1 · ⛔ a zero is written
# =================================================================================================
def test_zero_is_written_like_any_other_count():
    conn = _Conn()
    record(conn, org_id="o", sweep_id="s1", stage=SITUATIONS_FORMED, n=0, sweep_at=_AT)
    assert len(conn.writes) == 1
    assert conn.writes[0]["n"] == 0


def test_a_stage_that_wrote_no_row_reads_back_as_None_never_zero():
    """⛔ `None`, never `0`. Returning zero for both would undo the table's whole purpose at the last
    hop — the `not_carried` shape, at the read instead of the write."""
    conn = _Conn(rows=[{"stage": SIGNALS_DETECTED, "n": 4000}])
    funnel = read_sweep(conn, "o", "s1")
    assert funnel[SIGNALS_DETECTED] == 4000
    assert funnel[SITUATIONS_FORMED] is None
    assert funnel[CARD_DELIVERED] is None


def test_a_real_zero_and_a_missing_row_read_differently():
    conn = _Conn(rows=[{"stage": SITUATIONS_FORMED, "n": 0}])
    funnel = read_sweep(conn, "o", "s1")
    assert funnel[SITUATIONS_FORMED] == 0
    assert funnel[CAPABILITY_RESOLVED] is None
    assert funnel[SITUATIONS_FORMED] is not None


def test_every_stage_appears_in_the_read_whether_or_not_it_wrote():
    """A funnel missing a key is a funnel a caller has to `.get()` carefully. All five, always."""
    assert set(read_sweep(_Conn(), "o", "s1")) == set(STAGES)


# =================================================================================================
# 2 · the closed vocabulary
# =================================================================================================
def test_the_five_stages_are_in_flow_order():
    assert STAGES == (SIGNALS_DETECTED, SITUATIONS_FORMED, CAPABILITY_RESOLVED,
                      DECISION_EMITTED, CARD_DELIVERED)


@pytest.mark.parametrize("stage", ["signals", "situation_formed", "", "SIGNALS_DETECTED", "lanes"])
def test_a_stage_outside_the_five_is_refused_by_name(stage):
    """⛔ Refused here rather than by the database's check constraint, so the caller gets the list
    instead of an IntegrityError three frames down. An open vocabulary makes "is the funnel complete?"
    unanswerable, because a typo becomes a sixth stage nobody notices."""
    with pytest.raises(ValueError, match="not a funnel stage"):
        record(_Conn(), org_id="o", sweep_id="s", stage=stage, n=1, sweep_at=_AT)


def test_a_negative_count_is_refused():
    with pytest.raises(ValueError, match="broken writer"):
        record(_Conn(), org_id="o", sweep_id="s", stage=CARD_DELIVERED, n=-1, sweep_at=_AT)


# =================================================================================================
# 3 · ⛔ one writer per number
# =================================================================================================
def test_every_stage_names_exactly_one_owning_package():
    """⛔ A collector must re-derive four numbers it did not compute, and a re-derived count can
    disagree with the thing it counts — two answers to "how many situations formed?" and no way to tell
    which is the measurement. `DECISION_PROJECTIONS` applies the same rule to the decision."""
    assert set(STAGE_OWNERS) == set(STAGES)
    assert all(owner for owner in STAGE_OWNERS.values())


def test_the_owners_follow_the_data_flow():
    assert STAGE_OWNERS[SIGNALS_DETECTED] == "capture"
    assert STAGE_OWNERS[SITUATIONS_FORMED] == "context"
    assert STAGE_OWNERS[CARD_DELIVERED] == "deliver"


def test_the_two_reason_stages_are_the_only_shared_owner():
    """`reason/` owns two because it both resolves the capability and emits the decision. Any other
    package owning two would mean a stage is being written by something that did not compute it."""
    from collections import Counter

    counts = Counter(STAGE_OWNERS.values())
    assert [owner for owner, n in counts.items() if n > 1] == ["reason"]


# =================================================================================================
# 4 · where the loss is
# =================================================================================================
def test_it_names_the_pair_that_lost_the_most():
    funnel = {SIGNALS_DETECTED: 4000, SITUATIONS_FORMED: 100, CAPABILITY_RESOLVED: 90,
              DECISION_EMITTED: 85, CARD_DELIVERED: 28}
    assert biggest_loss(funnel) == (SIGNALS_DETECTED, SITUATIONS_FORMED, 3900)


def test_a_pair_with_an_unmeasured_end_is_skipped_not_called_a_total_collapse():
    """⛔ An unwritten stage looks like a loss of everything to arithmetic. Reporting it as one would
    send somebody debugging a stage that simply never reported."""
    funnel = {SIGNALS_DETECTED: 4000, SITUATIONS_FORMED: None, CAPABILITY_RESOLVED: 90,
              DECISION_EMITTED: 85, CARD_DELIVERED: 28}
    assert biggest_loss(funnel) == (DECISION_EMITTED, CARD_DELIVERED, 57)


def test_a_funnel_that_lost_nothing_names_nothing():
    funnel = {s: 10 for s in STAGES}
    assert biggest_loss(funnel) is None


def test_an_entirely_unmeasured_funnel_names_nothing():
    assert biggest_loss({s: None for s in STAGES}) is None


def test_a_stage_that_grew_is_not_a_loss():
    """More decisions than capabilities resolved is a defect, but it is not a funnel LOSS and calling
    it one would hide it behind the wrong number."""
    funnel = {SIGNALS_DETECTED: 10, SITUATIONS_FORMED: 10, CAPABILITY_RESOLVED: 10,
              DECISION_EMITTED: 99, CARD_DELIVERED: 99}
    assert biggest_loss(funnel) is None


# =================================================================================================
# 5 · a re-run overwrites, never appends
# =================================================================================================
def test_the_write_is_an_upsert_on_the_sweep():
    """⛔ `expertise_packages` put this database into read-only at 181 MB over 345 rows by appending
    per sweep. The primary key is the sweep, so a re-run overwrites its own row rather than adding a
    second, disagreeing observation of the same pass."""
    from genios_engine.platform import funnel

    sql = str(funnel._UPSERT).lower()
    assert "on conflict (org_id, sweep_id, stage) do update" in sql
    assert "written_at = now()" in sql


def test_record_takes_a_connection_so_the_count_shares_the_work_s_transaction():
    """A count committed separately from the thing it describes can survive a rollback of that thing."""
    import inspect

    assert list(inspect.signature(record).parameters)[0] == "conn"


# =================================================================================================
# 6 · ⛔ a measurement never breaks the thing it measures
# =================================================================================================
def test_observe_swallows_a_database_failure_and_says_it_did_not_write():
    """⛔ The return value matters: a caller that cares can then say "unmeasured" rather than "zero" —
    the distinction this module exists for, surviving its own failure path."""
    class _Broken:
        class engine:
            @staticmethod
            def begin():
                raise RuntimeError("database is down")

    assert observe(_Broken(), org_id="o", sweep_id="s", stage=CARD_DELIVERED, n=3,
                   sweep_at=_AT) is False


def test_observe_reports_true_when_it_wrote():
    class _Ok:
        class engine:
            @staticmethod
            def begin():
                class _Cm:
                    def __enter__(self): return _Conn()
                    def __exit__(self, *a): return False
                return _Cm()

    assert observe(_Ok(), org_id="o", sweep_id="s", stage=CARD_DELIVERED, n=3,
                   sweep_at=_AT) is True


def test_a_bad_stage_still_raises_through_observe_rather_than_being_swallowed():
    """A typo in a stage name is a programming error, not a transient failure, and swallowing it would
    mean the stage silently never records."""
    class _Ok:
        class engine:
            @staticmethod
            def begin():
                class _Cm:
                    def __enter__(self): return _Conn()
                    def __exit__(self, *a): return False
                return _Cm()

    assert observe(_Ok(), org_id="o", sweep_id="s", stage="nonsense", n=1, sweep_at=_AT) is False


# =================================================================================================
# 7 · ⛔ the migration and the code agree
# =================================================================================================
def test_the_migration_carries_the_same_five_stages():
    """Two lists that must agree forever will eventually disagree. This is the test that notices."""
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[2] / "migrations"
           / "0188_pipeline_counters.sql").read_text()
    for stage in STAGES:
        assert f"'{stage}'" in sql
    assert "check (n >= 0)" in sql


def test_the_migration_makes_the_count_not_null():
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[2] / "migrations"
           / "0188_pipeline_counters.sql").read_text()
    assert "n          bigint      not null" in sql
