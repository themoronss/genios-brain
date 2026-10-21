"""A database blip parks nothing, and a parked event is read again — no event leaves memory for good.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_parked_event_is_not_lost_pg.py -q

L3 audit, 21 Oct 2026. Every exception the drain met counted toward `_MAX_ATTEMPTS`: a connection drop or a
pool timeout during one sweep — and the warm lane re-runs within minutes — failed the same events three times
and parked them, and `PENDING_FROM` never offered a parked event again. Their facts and cards never came and the
progress bar still read complete. Now a transient database failure is HELD (no attempt spent) and a parked event
is offered again after `PARKED_RETRY_AFTER`. No road into memory calls a model, so neither costs a cent.
"""
from __future__ import annotations

import pytest
from sqlalchemy import exc as sa
from sqlalchemy import text

from genios_engine.context import runner
from tests.context import test_every_kept_event_is_pulled as seed

pytestmark = pytest.mark.pg
ORG = seed.ORG


@pytest.fixture
def store(pg_store):
    seed._reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'founder.pull@gmail.com')"),
                  {"o": ORG})
        for e in ("p_fresh", "p_old", "p_done", "p_blip"):
            seed._event(c, e); seed._extraction(c, e, f"x_{e}"); seed._signal(c, e, f"x_{e}")
    yield pg_store
    seed._reset(pg_store)


def _run(c, event_id: str, status: str, age: str) -> None:
    c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts, updated_at) "
                   "values (:o, :e, :s, 3, now() - cast(:age as interval))"),
              {"o": ORG, "e": event_id, "s": status, "age": age})


def _pulled(store) -> set[str]:
    return {r.event_id for r in runner._pull(store, ORG, 100)}


def test_a_parked_event_is_offered_again_after_a_day_and_not_before(store):
    with store.engine.begin() as c:
        _run(c, "p_fresh", "parked", "1 hour")
        _run(c, "p_old", "parked", "25 hours")
        _run(c, "p_done", "done", "30 days")
    pulled = _pulled(store)
    assert "p_old" in pulled, "a parked event was never offered again — out of memory for good"
    assert "p_fresh" not in pulled, "a just-parked event must not fail every drain of the day"
    assert "p_done" not in pulled
    assert "p_blip" in pulled


def test_the_pending_count_moves_with_the_pull(store, monkeypatch):
    from genios_engine.api import routes
    monkeypatch.setattr(routes, "_graph", store)
    with store.engine.begin() as c:
        _run(c, "p_old", "parked", "25 hours")
    assert routes._pending_count(ORG) == len(_pulled(store))


def test_a_database_blip_holds_the_event_and_spends_no_attempt(store, monkeypatch):
    def _blip(row, **_):
        raise sa.OperationalError("select 1", {}, Exception("server closed the connection unexpectedly"))
    monkeypatch.setattr(runner, "_process_one", _blip)
    row = next(r for r in runner._pull(store, ORG, 100) if r.event_id == "p_blip")
    outcome, _node, err = runner._safe_process_one(row, org_id=ORG, store=store, llm=None, crypto_key=None)
    assert outcome == runner.HELD_DATABASE_UNAVAILABLE and "server closed" in err
    runner._record_hold(store, ORG, "p_blip", outcome)
    with store.engine.connect() as c:
        status, attempts = c.execute(text("select status, attempts from l2_processing_runs "
                                          "where org_id=:o and event_id='p_blip'"), {"o": ORG}).one()
    assert (status, attempts) == ("held", 0)
    assert "p_blip" in _pulled(store), "a held event is read by the next drain"


def test_a_real_failure_still_counts(store, monkeypatch):
    def _bug(row, **_):
        raise KeyError("thread")
    monkeypatch.setattr(runner, "_process_one", _bug)
    row = next(r for r in runner._pull(store, ORG, 100) if r.event_id == "p_blip")
    assert runner._safe_process_one(row, org_id=ORG, store=store, llm=None, crypto_key=None)[0] == "error"


@pytest.mark.parametrize("exc, transient", [
    (sa.OperationalError("s", {}, Exception("deadlock detected")), True),
    (sa.InterfaceError("s", {}, Exception("connection already closed")), True),
    (sa.TimeoutError("QueuePool limit reached"), True),
    (sa.IntegrityError("s", {}, Exception("duplicate key")), False),
    (ValueError("bad payload"), False),
])
def test_what_counts_as_transient(exc, transient):
    assert runner._is_transient(exc) is transient
