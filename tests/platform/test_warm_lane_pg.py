"""Warm lane against REAL Postgres — the queue, the leases and the doors.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5433/<scratch> \\
        pytest tests/platform/test_warm_lane_pg.py -q

What only a real database can prove: SKIP LOCKED keeps two workers off one row; the org lease
keeps every chain caller (sweep `_run_l2`, a Sync job's `_process_and_reason_tracked`, the warm
worker) from running one org twice at once; a burst coalesces into one run; an expired lease or
claim comes back; a deferral is never finished by a run that started before it; and the two doors
— the Composio webhook and the upload route — really queue what they emitted.
"""
from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.platform import warm_lane as W

pytestmark = pytest.mark.pg

ORGS = ("org_warm_a", "org_warm_b", "org_warm_c")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the warm lane needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    _purge(eng)
    with eng.begin() as c:
        names = [r.column_name for r in c.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        for org in ORGS:
            c.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                           f"({', '.join(':' + x for x in cols)}) on conflict (id) do nothing"),
                      {"id": org, **{n: "scratch" for n in names}})
    W._housekeeping.update(stale_check=0.0, prune=0.0)
    yield eng
    W.stop_warm_lane()
    _purge(eng)


def _purge(eng) -> None:
    with eng.begin() as c:
        c.execute(text("delete from warm_lane_slots"))
        c.execute(text("delete from orgs where id = any(:o)"), {"o": list(ORGS)})   # cascades


def _rows(eng, org: str) -> list:
    with eng.connect() as c:
        return c.execute(text(
            "select id, event_id, source, claimed_by, lease_until, done_at, parked_at, attempts, "
            "last_error, enqueued_at, lease_until > now() as leased from l2_work_queue "
            "where org_id = :o order by id"), {"o": org}).fetchall()


def _open(eng, org: str) -> list:
    return [r for r in _rows(eng, org) if r.done_at is None and r.parked_at is None]


def _chain(eng, fn=lambda: True, **kw):
    """A stand-in chain that runs under the REAL single-flight, as `_run_l2` does."""
    return lambda org: W.run_exclusive(eng, org, fn, caller="test", wait_s=0, defer=False, **kw)


# ── queue basics ────────────────────────────────────────────────────────────────────────────────

def test_one_pending_row_per_event_and_a_rerun_trigger_moves_forward(engine):
    assert W.enqueue(engine, "org_warm_a", ["e1", "e2", "e1"], "webhook:gmail") == 2
    assert W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail") == 0       # already pending
    W.enqueue(engine, "org_warm_a", [W.ORG_TRIGGER], "deferred:t")
    first = next(r for r in _rows(engine, "org_warm_a") if r.event_id == W.ORG_TRIGGER)
    time.sleep(0.02)
    W.enqueue(engine, "org_warm_a", [W.ORG_TRIGGER], "deferred:t")
    again = [r for r in _rows(engine, "org_warm_a") if r.event_id == W.ORG_TRIGGER]
    assert len(again) == 1 and again[0].enqueued_at > first.enqueued_at


def test_a_burst_coalesces_into_one_chain_run(engine):
    for i in range(5):
        W.enqueue(engine, "org_warm_a", [f"evt_{i}_{j}" for j in range(5)], "webhook:gmail")
    runs = []
    assert W.run_once(engine, "w1", run_chain=_chain(engine, lambda: runs.append(1)), slots=1)
    assert runs == [1], "25 queued events must cost ONE chain run"
    assert _open(engine, "org_warm_a") == []
    assert all(r.done_at is not None for r in _rows(engine, "org_warm_a"))
    assert W.run_once(engine, "w1", run_chain=_chain(engine), slots=1) is False     # nothing left


def test_two_workers_never_process_the_same_event_and_never_overlap_an_org(engine, monkeypatch):
    for org in ORGS:
        W.enqueue(engine, org, [f"{org}_e{i}" for i in range(10)], "webhook:gmail")
    lock = threading.Lock()
    local = threading.local()
    processed: list[str] = []
    running: dict[str, int] = {o: 0 for o in ORGS}
    overlaps: list[str] = []
    real_claim = W.claim_batch

    def spy_claim(eng, worker_id):
        got = real_claim(eng, worker_id)
        local.batch = got[0] if got else None
        return got

    monkeypatch.setattr(W, "claim_batch", spy_claim)

    def chain(org):
        def fn():
            with lock:
                running[org] += 1
                if running[org] > 1:
                    overlaps.append(org)
                processed.extend(r.event_id for r in local.batch.rows)
            time.sleep(0.15)
            with lock:
                running[org] -= 1
            return True
        return W.run_exclusive(engine, org, fn, caller="test", wait_s=0, defer=False)

    def worker(n):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if not W.run_once(engine, f"w{n}", run_chain=chain, slots=2):
                if not any(_open(engine, o) for o in ORGS):
                    return
                time.sleep(0.05)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not overlaps
    assert sorted(processed) == sorted(f"{o}_e{i}" for o in ORGS for i in range(10)), \
        "every event processed exactly once"
    assert not any(_open(engine, o) for o in ORGS)


# ── recovery, busy, failure ─────────────────────────────────────────────────────────────────────

def test_an_expired_org_lease_and_an_expired_claim_are_recovered(engine):
    W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail")
    with engine.begin() as c:
        c.execute(text("update l2_work_queue set claimed_by='dead-worker', attempts=1, "
                       "lease_until = now() - interval '1 second' where org_id='org_warm_a'"))
        c.execute(text("insert into org_run_leases (org_id, holder, lease_until) values "
                       "('org_warm_a', 'dead-holder', now() - interval '1 minute')"))
    ran = []
    assert W.run_once(engine, "w1", run_chain=_chain(engine, lambda: ran.append(1)), slots=1)
    assert ran == [1]
    assert _open(engine, "org_warm_a") == []
    with engine.connect() as c:
        assert c.execute(text("select count(*) from org_run_leases "
                              "where org_id='org_warm_a'")).scalar() == 0      # released


def test_a_busy_org_releases_the_claim_without_charging_an_attempt(engine):
    W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail")
    with engine.begin() as c:
        c.execute(text("insert into org_run_leases (org_id, holder, lease_until) values "
                       "('org_warm_a', 'someone-else', now() + interval '1 minute')"))
    ran = []
    assert W.run_once(engine, "w1", run_chain=_chain(engine, lambda: ran.append(1)),
                      slots=1) is False
    assert ran == []
    (row,) = _open(engine, "org_warm_a")
    assert row.claimed_by is None and row.attempts == 0 and row.leased      # retry shortly


def test_failures_back_off_then_park_and_a_parked_event_can_queue_again(engine, monkeypatch):
    W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail")
    notified = []
    from genios_engine.platform import ops_alert
    monkeypatch.setattr(ops_alert, "notify", lambda kind, **kw: notified.append(kind))
    for attempt in range(1, W.MAX_ATTEMPTS + 1):
        assert W.run_once(engine, "w1", run_chain=_chain(engine, lambda: False), slots=1)
        (row,) = _rows(engine, "org_warm_a")
        assert row.attempts == attempt and row.last_error
        if attempt < W.MAX_ATTEMPTS:
            assert row.parked_at is None and row.leased, "backoff sets a not-before"
            assert W.run_once(engine, "w1", run_chain=_chain(engine), slots=1) is False
            with engine.begin() as c:                                  # fast-forward the backoff
                c.execute(text("update l2_work_queue set lease_until = now() - interval '1 s' "
                               "where org_id='org_warm_a'"))
    assert row.parked_at is not None and notified == ["warm_lane_parked"]
    assert W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail") == 1


def test_a_crashing_chain_counts_as_a_failed_run(engine):
    W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail")

    def boom(_org):
        raise RuntimeError("chain exploded")
    assert W.run_once(engine, "w1", run_chain=boom, slots=1)
    (row,) = _rows(engine, "org_warm_a")
    assert row.done_at is None and row.attempts == 1 and "chain exploded" in row.last_error


def test_the_global_slot_bounds_concurrency_across_workers(engine):
    W.enqueue(engine, "org_warm_a", ["e1"], "webhook:gmail")
    with engine.begin() as c:
        c.execute(text("insert into warm_lane_slots (slot, holder, lease_until) values "
                       "(0, 'other-instance', now() + interval '1 minute')"))
    assert W.run_once(engine, "w1", run_chain=_chain(engine), slots=1) is False
    assert len(_open(engine, "org_warm_a")) == 1


# ── single-flight + deferral ───────────────────────────────────────────────────────────────────

def test_a_deferral_is_not_finished_by_the_run_it_was_deferred_behind(engine):
    W.enqueue(engine, "org_warm_a", ["before"], "webhook:gmail")
    inside, release = threading.Event(), threading.Event()
    result = {}

    def holder():
        result["out"] = W.run_exclusive(
            engine, "org_warm_a", lambda: (inside.set(), release.wait(10)), caller="holder")

    t = threading.Thread(target=holder)
    t.start()
    assert inside.wait(5)
    busy = W.run_exclusive(engine, "org_warm_a", lambda: pytest.fail("ran concurrently"),
                           caller="sweep", wait_s=0.3, defer=True)
    assert busy.status == "busy"
    release.set()
    t.join(10)
    assert result["out"].ok and result["out"].marked_done == 1        # "before" only
    (left,) = _open(engine, "org_warm_a")
    assert left.event_id == W.ORG_TRIGGER, "the deferral must survive the holder's run"
    ran = []
    assert W.run_once(engine, "w1", run_chain=_chain(engine, lambda: ran.append(1)), slots=1)
    assert ran == [1] and _open(engine, "org_warm_a") == []


def test_the_chain_callers_are_mutually_exclusive_per_org(engine, monkeypatch):
    """The sweep's `_run_l2`, a Sync job's `_process_and_reason_tracked` and the warm worker, all
    at once for one org: `process_pending` never runs twice concurrently, and nothing is left."""
    from genios_engine.api import routes
    if routes._graph is None:
        pytest.skip("graph store not configured")
    import genios_engine.context.runner as runner
    import genios_engine.reason.runner as l3
    from genios_engine.platform import intelligence_onboarding, progress
    lock = threading.Lock()
    state = {"running": 0, "max": 0, "calls": 0}

    def slow_pending(**kw):
        with lock:
            state["running"] += 1
            state["calls"] += 1
            state["max"] = max(state["max"], state["running"])
        time.sleep(0.4)
        with lock:
            state["running"] -= 1
        return {"processed": 0}

    monkeypatch.setattr(runner, "process_pending", slow_pending)
    monkeypatch.setattr(l3, "run_all", lambda **_kw: None)
    monkeypatch.setattr(routes, "_card_store", None)
    monkeypatch.setattr(intelligence_onboarding, "provision_intelligence", lambda *_a: None)
    monkeypatch.setattr(progress, "set_phase", lambda *_a, **_k: None)
    monkeypatch.setattr(routes, "_pending_count", lambda _org: 0)
    monkeypatch.setattr(W, "CHAIN_WAIT_SECONDS", 5.0)

    org = "org_warm_b"
    W.enqueue(engine, org, ["e1", "e2"], "webhook:gmail")
    callers = [lambda: routes._run_l2(org),
               lambda: routes._process_and_reason_tracked(org),
               lambda: W.run_once(engine, "w1", slots=1)]           # the REAL default chain
    threads = [threading.Thread(target=c) for c in callers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert state["max"] == 1, "two chain runs for one org overlapped"
    assert state["calls"] >= 1
    for _ in range(3):                                   # drain any deferral the race produced
        W.run_once(engine, "w1", slots=1)
    assert _open(engine, org) == []


# ── the doors ───────────────────────────────────────────────────────────────────────────────────

def test_the_composio_webhook_queues_what_it_emitted(engine, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import routes as R
    from genios_engine.capture.connectors import composio_push, dispatch
    if R._graph is None:
        pytest.skip("graph store not configured")
    org = "org_warm_c"
    conn = SimpleNamespace(org_id=org, source_type="gmail", connection_id=f"con_{org}_gmail")
    monkeypatch.setattr(R, "get_settings",
                        lambda: SimpleNamespace(composio_webhook_secret="", env="dev"))
    monkeypatch.setattr(composio_push, "parse_push",
                        lambda payload: SimpleNamespace(skip_reason=None, data=payload["data"]))
    monkeypatch.setattr(composio_push, "pick_connection", lambda conns, push: conn)
    monkeypatch.setattr(dispatch, "can_dispatch", lambda source: True)
    monkeypatch.setattr(dispatch, "webhook_to_raw_objects",
                        lambda source, data, connector_factory=None: ("raw",))
    for helper in ("make_relevance_classifier", "_sender_resolver_for", "_mailbox_owner_for",
                   "_coverage_fn_for", "_esqe_stage_for", "_semantic_lane_for",
                   "_structured_lane_for"):
        monkeypatch.setattr(R, helper, lambda *_a, **_k: None)
    mail = SimpleNamespace(outcome="emitted",
                           event=SimpleNamespace(event_id="evt_hook_1", object_type="email_message"))
    dup = SimpleNamespace(outcome="duplicate",
                          event=SimpleNamespace(event_id="evt_hook_0", object_type="email_message"))
    monkeypatch.setattr(R, "ingest_pushed_objects", lambda objs, **kw: SimpleNamespace(
        results=(mail, dup), primary=mail, quarantined=()))
    finalized = []
    monkeypatch.setattr(R, "finalize_l1",
                        lambda summary, *, org_id, stores: finalized.append(org_id))
    app = FastAPI()
    app.include_router(R.router)
    resp = TestClient(app).post("/webhooks/composio", json={"data": {"id": "m1"}})
    assert resp.status_code == 200 and resp.json()["ingested"] is True, resp.text
    assert finalized == [org]
    rows = _open(engine, org)
    assert [(r.event_id, r.source) for r in rows] == [("evt_hook_1", "webhook:gmail")], \
        "only the EMITTED event is queued, after the finalizer"


def test_an_upload_is_queued_and_the_warm_lane_gives_it_reasoning(engine, monkeypatch):
    """G-26: the upload door ran L2 alone. Now it queues its chunks and the worker runs the whole
    chain — L2, reasoning, cards — before the file's counts are reconciled."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import routes, upload_routes
    from genios_engine.platform.auth import AuthCtx, get_auth_ctx
    import genios_engine.reason.runner as l3
    if routes._graph is None or upload_routes._graph is None:
        pytest.skip("graph store not configured")
    org = "org_warm_a"
    reasoned, carded = [], []
    real_run_all = l3.run_all

    def spy_run_all(**kw):
        reasoned.append(kw["org_id"])
        return real_run_all(**kw)

    monkeypatch.setattr(l3, "run_all", spy_run_all)
    import genios_engine.deliver.pipeline as deliver
    real_cards = deliver.build_cards_for_org

    def spy_cards(**kw):
        carded.append(kw["org_id"])
        return real_cards(**kw)

    monkeypatch.setattr(deliver, "build_cards_for_org", spy_cards)
    from genios_engine.feedback import org_rule_ingest
    monkeypatch.setattr(org_rule_ingest, "sweep_org_rule_discovery", lambda _org: None)
    assert W.start_warm_lane(initial_delay=0)

    app = FastAPI()
    app.include_router(upload_routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=org, actor_id="t@warm.test")
    doc = ("PAYMENT TERMS\nContoso Ltd master services agreement. The annual fee of $12,000 is "
           "payable on 30 October 2026.")
    resp = TestClient(app).post(f"/api/org/{org}/upload",
                                files={"file": ("contoso.txt", doc.encode(), "text/plain")})
    assert resp.status_code == 200, resp.text
    file_id = resp.json()["file_id"]
    try:
        rows = _rows(engine, org)
        assert rows and {r.source for r in rows} == {"upload"}
        assert _open(engine, org) == [], "the upload's reconciliation ran before its chain"
        assert org in reasoned, "the upload never reached reasoning"
        assert org in carded, "the upload never reached card building"
        with engine.connect() as c:
            status = c.execute(text("select status from resource_uploads where org_id=:o "
                                    "and file_id=:f"), {"o": org, "f": file_id}).scalar()
        assert status == "indexed"
    finally:
        W.stop_warm_lane()
        with engine.connect() as c:
            path = c.execute(text("select storage_path from resource_uploads where org_id=:o "
                                  "and file_id=:f"), {"o": org, "f": file_id}).scalar()
        if path and os.path.exists(path):
            os.remove(path)
