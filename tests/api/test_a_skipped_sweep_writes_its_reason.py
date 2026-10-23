"""GeniOS-011 S02.U5 · every sweep skip is a row, and every door asks the same gates.

    pytest tests/api/test_a_skipped_sweep_writes_its_reason.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_a_skipped_sweep_writes_its_reason.py -q

⛔ WHY THIS FILE EXISTS (audit item `cross-billing-gates-silently-stop-the-org`, P0). A lapsed plan,
a full ingestion meter, the daily model cap or the pause switch stopped an org's sweep and left
nothing behind but four counters in one INFO log line. No `l1_sync_runs` row, nothing a founder or
an operator could read. And the doors disagreed: the scheduled sweep asked all four gates, the
dashboard's Sync now asked only the daily cap, and POST /sync/{id} and POST
/connections/{id}/backfill asked none — so on a lapsed org cards appeared only after a manual Sync.

What this file holds true:

* each of the four skips writes ONE `l1_sync_runs` row per org per sweep, with its reason in
  `error` as `skipped:<reason>` — readable in the admin console's sync list;
* the row names NO connection and NO source, because the gate is an org-level decision and the
  coverage readers (`capture/coverage/window`, `context/coverage_receipt`) read per source and per
  connection: a skip is not a sweep, and must not be counted as one (the next real sweep's cursor
  reads the gap);
* the sweep, Sync now, POST /sync/{id} and the backfill door all ask `_sweep_gate`, and the one
  exemption (the owner's backfill/resync passes the ingestion meter) is written in
  `DOOR_GATE_EXEMPTIONS` and logged — to the log and to `audit_log` — every time it is used.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import text

from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
from genios_engine.capture.acquire.sync_runner import SyncSummary
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.connection import Connection

ORG = "org_g011_s02u5_skip"
OTHER = "org_g011_s02u5_open"
REASONS = ("paused", "plan_expired", "over_budget", "sync_quota")


class _Store:
    def __init__(self, *connections: Connection) -> None:
        self._by_id = {c.connection_id: c for c in connections}

    def list_active(self, source_type: str | None = None):
        return list(self._by_id.values())

    def get(self, connection_id: str):
        return self._by_id.get(connection_id)


def _trip(monkeypatch, routes, reason: str | None) -> None:
    """Make exactly one gate refuse ORG (or none). OTHER is never refused."""
    monkeypatch.setattr(routes, "_org_paused", lambda o: o == ORG and reason == "paused")
    monkeypatch.setattr(routes, "_plan_expired", lambda o: o == ORG and reason == "plan_expired")
    monkeypatch.setattr(routes, "_llm_over_daily_cap",
                        lambda o: o == ORG and reason == "over_budget")
    monkeypatch.setattr(routes, "_sync_headroom",
                        lambda o: 0 if (o == ORG and reason == "sync_quota") else 5_000)


@pytest.fixture
def sweep_env(monkeypatch):
    """Two connections for ORG (gmail + gcal) and one for OTHER. `run_sync` records who it pulled;
    `_run_ledger` records every row the door writes."""
    from genios_engine.api import routes

    conns = [Connection(org_id=ORG, connection_id="con_s02u5_gmail", source_type="gmail",
                        composio_user_id=ORG),
             Connection(org_id=ORG, connection_id="con_s02u5_gcal", source_type="gcal",
                        composio_user_id=ORG),
             Connection(org_id=OTHER, connection_id="con_s02u5_other", source_type="gmail",
                        composio_user_id=OTHER)]
    pulled: list[str] = []
    rows: list[dict] = []
    chained: list[str] = []
    monkeypatch.setattr(routes, "_connections", _Store(*conns))
    monkeypatch.setattr(routes, "_cursors", InMemoryCursorStore())
    monkeypatch.setattr(routes, "_repo", InMemorySourceEventRepository())
    for name in ("_parked", "_trace_repo", "_payload_store", "_prepared_store", "_documents",
                 "_graph"):
        monkeypatch.setattr(routes, name, None)
    for name in ("make_relevance_classifier", "make_connector_for", "_bind_gate_costs",
                 "_semantic_lane_for", "_structured_lane_for", "_esqe_stage_for",
                 "_coverage_fn_for", "_sender_resolver_for", "_mailbox_owner_for_connection"):
        monkeypatch.setattr(routes, name, lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_semantic_activated_orgs", lambda *a, **kw: frozenset())
    monkeypatch.setattr(routes, "_notify_sync_failure", lambda **kw: None)
    monkeypatch.setattr(routes, "_compose_due_briefs", lambda: {})
    monkeypatch.setattr(routes, "_run_l2", lambda org, **kw: chained.append(org))

    def _pull(connector, **kw):
        pulled.append(kw["connection_id"])
        return SyncSummary(scanned=1, emitted=1)

    monkeypatch.setattr(routes, "run_sync", _pull)
    monkeypatch.setattr(routes, "_run_ledger", lambda **kw: rows.append(kw))
    return SimpleNamespace(routes=routes, pulled=pulled, rows=rows, chained=chained)


# ── 1 · the sweep: every skip is a row ─────────────────────────────────────────────────────────

_COUNTER = {"paused": "l1_skipped_paused", "plan_expired": "l1_skipped_plan_expired",
            "over_budget": "l1_skipped_over_budget", "sync_quota": "l1_skipped_sync_quota"}


@pytest.mark.parametrize("reason", REASONS)
def test_each_sweep_skip_writes_one_row_with_its_reason(sweep_env, monkeypatch, reason):
    """⛔ THE MUTATION THIS REJECTS: the row write removed, leaving the counter alone. A counter in
    one INFO log line is what the audit found; a row is what a founder's page can read."""
    routes = sweep_env.routes
    _trip(monkeypatch, routes, reason)

    out = routes.run_sync_sweep(mode="incremental")

    assert out[_COUNTER[reason]] == 2, out             # both of ORG's connections were skipped
    assert sweep_env.pulled == ["con_s02u5_other"], "a refused org was pulled anyway"
    skips = [r for r in sweep_env.rows if r["org_id"] == ORG]
    assert len(skips) == 1, f"one row per org per sweep, not one per connection: {skips}"
    row = skips[0]
    assert row["error"].startswith(f"skipped:{reason} "), row
    assert "door=sweep" in row["error"], row
    assert row["mode"] == "incremental"
    assert row.get("summary") is None
    # The org's decision, not a connection's sweep: the coverage readers must not count it.
    assert row["connection_id"] is None and row["source"] is None, row
    # A skip captured nothing, so it must not run L1's finalizer (conflicts, floor, publish).
    assert row.get("finalize") is False, row
    assert not [r for r in sweep_env.rows if r["org_id"] == OTHER], "an open org wrote a skip"


def test_an_org_no_gate_refuses_writes_no_skip_row(sweep_env, monkeypatch):
    """The negative control: the row is the skip's, never the sweep's."""
    routes = sweep_env.routes
    _trip(monkeypatch, routes, None)

    out = routes.run_sync_sweep(mode="incremental")

    assert sorted(sweep_env.pulled) == ["con_s02u5_gcal", "con_s02u5_gmail", "con_s02u5_other"]
    assert sweep_env.rows == []
    assert all(out[c] == 0 for c in _COUNTER.values()), out


@pytest.mark.parametrize("reason,reasoned", [("paused", False), ("plan_expired", False),
                                             ("over_budget", True), ("sync_quota", True)])
def test_the_chain_still_follows_the_gate_it_followed_before(sweep_env, monkeypatch, reason,
                                                             reasoned):
    """Unchanged by this unit: paused and lapsed orgs are not reasoned; over-budget and quota-full
    orgs still reason over what they already hold."""
    routes = sweep_env.routes
    _trip(monkeypatch, routes, reason)
    routes.run_sync_sweep(mode="incremental")
    assert (ORG in sweep_env.chained) is reasoned, sweep_env.chained


def test_the_sweep_trims_pages_to_the_headroom_the_gate_measured(sweep_env, monkeypatch):
    """The gate hands back the meter it read, so the sweep's page trim reads the same number."""
    routes = sweep_env.routes
    _trip(monkeypatch, routes, None)
    monkeypatch.setattr(routes, "_sync_headroom", lambda o: 30)
    pages: list[int] = []
    monkeypatch.setattr(routes, "run_sync",
                        lambda connector, **kw: pages.append(kw["max_pages"]) or SyncSummary())
    routes.run_sync_sweep(mode="incremental", limit=25)
    assert pages == [2, 2, 2], pages


# ── 2 · Sync now (the dashboard's button → sync_jobs → _onboarding_sync_bg) ─────────────────────

@pytest.fixture
def sync_now_env(monkeypatch):
    from genios_engine.api import routes

    rows: list[dict] = []
    pulled: list[str] = []
    monkeypatch.setattr(routes, "_graph", None)
    monkeypatch.setattr(routes, "_run_ledger", lambda **kw: rows.append(kw))
    monkeypatch.setattr(routes, "_backfill_one_source",
                        lambda org_id, st, limit, **kw: pulled.append(st) or (1, 1, False))
    monkeypatch.setattr(routes, "_process_and_reason_tracked", lambda *a, **k: None)
    monkeypatch.setattr(routes, "_set_sync_running", lambda *a, **k: None)
    return SimpleNamespace(routes=routes, rows=rows, pulled=pulled)


@pytest.mark.parametrize("reason", REASONS)
def test_sync_now_asks_the_sweeps_gates_and_writes_the_same_row(sync_now_env, monkeypatch,
                                                                reason):
    """⛔ Sync now asked only the daily cap. A lapsed org's only cards came from this button."""
    routes = sync_now_env.routes
    _trip(monkeypatch, routes, reason)
    routes._onboarding_sync_bg(ORG, ["gmail", "gcal"], checkpoint={})
    assert sync_now_env.pulled == [], f"Sync now pulled a refused org ({reason})"
    assert len(sync_now_env.rows) == 1, sync_now_env.rows
    row = sync_now_env.rows[0]
    assert row["error"].startswith(f"skipped:{reason} ") and "door=sync_now" in row["error"]
    assert row["connection_id"] is None and row["source"] is None
    assert row.get("finalize") is False


def test_sync_now_runs_when_no_gate_refuses(sync_now_env, monkeypatch):
    routes = sync_now_env.routes
    _trip(monkeypatch, routes, None)
    routes._onboarding_sync_bg(ORG, ["gmail"], checkpoint={})
    assert sync_now_env.pulled == ["gmail"]
    assert sync_now_env.rows == []


def test_a_resumed_sync_now_job_is_never_refused_mid_window(sync_now_env, monkeypatch):
    """Kept from before: a resumed job IS a run in progress, and refusing it would mark the job
    complete with half a window, for good."""
    routes = sync_now_env.routes
    _trip(monkeypatch, routes, "over_budget")
    routes._onboarding_sync_bg(
        ORG, ["gmail"],
        checkpoint={"sources": {"gmail": {"state": "running", "cursor": "p-3", "rounds": 1}}})
    assert sync_now_env.pulled == ["gmail"]
    assert sync_now_env.rows == []


# ── 3 · POST /sync/{id} ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def door_env(monkeypatch):
    from genios_engine.api import routes

    conn = Connection(org_id=ORG, connection_id="con_s02u5_door", source_type="gmail",
                      composio_user_id=ORG)
    rows: list[dict] = []
    monkeypatch.setattr(routes, "_connections", _Store(conn))
    monkeypatch.setattr(routes, "_run_ledger", lambda **kw: rows.append(kw))
    return SimpleNamespace(routes=routes, rows=rows, conn=conn)


@pytest.mark.parametrize("reason", REASONS)
def test_post_sync_refuses_what_the_sweep_refuses(door_env, monkeypatch, reason):
    routes = door_env.routes
    _trip(monkeypatch, routes, reason)
    tasks = BackgroundTasks()
    out = routes.sync_one("con_s02u5_door", tasks, org_id=ORG)
    assert tasks.tasks == [], "POST /sync/{id} scheduled a sync the sweep would refuse"
    assert out["scheduled"] is False and out["skipped"] == reason, out
    assert out["detail"] == routes.SWEEP_SKIP_LINES[reason]
    assert len(door_env.rows) == 1 and "door=sync_one" in door_env.rows[0]["error"]


def test_post_sync_schedules_when_no_gate_refuses(door_env, monkeypatch):
    routes = door_env.routes
    _trip(monkeypatch, routes, None)
    tasks = BackgroundTasks()
    out = routes.sync_one("con_s02u5_door", tasks, org_id=ORG)
    assert out["scheduled"] is True and len(tasks.tasks) == 1
    assert door_env.rows == []


# ── 4 · POST /connections/{id}/backfill — the one exemption, and it is logged ──────────────────

@pytest.mark.parametrize("reason", ("paused", "plan_expired", "over_budget"))
def test_the_backfill_door_refuses_the_three_gates_it_is_not_exempt_from(door_env, monkeypatch,
                                                                         reason):
    routes = door_env.routes
    _trip(monkeypatch, routes, reason)
    tasks = BackgroundTasks()
    out = routes.backfill_connection("con_s02u5_door", tasks, org_id=ORG)
    assert tasks.tasks == [], f"the backfill door started a drain for a {reason} org"
    assert out["started"] is False and out["skipped"] == reason, out
    assert len(door_env.rows) == 1 and "door=backfill" in door_env.rows[0]["error"]


def test_the_resyncs_quota_bypass_is_an_explicit_logged_decision(door_env, monkeypatch, caplog):
    """⛔ A 365-day resync on a full meter used to bypass it in silence, and the next period's
    polling then stopped. The bypass is kept (the owner asked for that history) — but it is now
    named in `DOOR_GATE_EXEMPTIONS`, logged, and written to `audit_log` with the headroom it
    spent past."""
    import logging

    from genios_engine.platform import audit

    routes = door_env.routes
    _trip(monkeypatch, routes, "sync_quota")
    recorded: list[tuple] = []
    monkeypatch.setattr(audit, "record", lambda org, action, **kw: recorded.append((org, action,
                                                                                    kw)))
    tasks = BackgroundTasks()
    with caplog.at_level(logging.WARNING, logger="genios.api"):
        out = routes.backfill_connection("con_s02u5_door", tasks, org_id=ORG)
    assert out["started"] is True and len(tasks.tasks) == 1, "the exempt door was refused"
    assert door_env.rows == [], "an exemption is not a skip"
    assert [(o, a) for o, a, _ in recorded] == [(ORG, "sync_quota_bypassed")], recorded
    meta = recorded[0][2]["metadata"]
    assert meta["door"] == "backfill" and meta["headroom"] == 0, meta
    assert meta["why"] == routes.DOOR_GATE_EXEMPTIONS["backfill"]["sync_quota"]
    assert any("sync_quota bypassed" in r.getMessage() for r in caplog.records), caplog.text


def test_the_exemption_table_names_every_door_and_exempts_only_the_backfill_meter():
    from genios_engine.api import routes

    assert set(routes.DOOR_GATE_EXEMPTIONS) == {"sweep", "sync_now", "sync_one", "backfill"}
    exempt = {door: set(g) for door, g in routes.DOOR_GATE_EXEMPTIONS.items() if g}
    assert exempt == {"backfill": {"sync_quota"}}, exempt
    assert set(routes.SWEEP_SKIP_REASONS) == set(REASONS)
    assert set(routes.SWEEP_SKIP_LINES) == set(REASONS)


def test_an_unnamed_door_cannot_ask_the_gate():
    """A door must be named in the exemption table to ask at all — a new door cannot quietly
    invent its own exemptions by passing a name nobody wrote down."""
    from genios_engine.api import routes

    with pytest.raises(KeyError):
        routes._sweep_gate(ORG, door="a_door_nobody_named")


# ── 5 · the AST guard: one gate function, asked by every door ───────────────────────────────────

_GATE_HELPERS = {"_org_paused", "_plan_expired", "_llm_over_daily_cap", "_sync_headroom"}
_DOORS = {"run_sync_sweep": "sweep", "_onboarding_sync_bg": "sync_now", "sync_one": "sync_one",
          "backfill_connection": "backfill"}


def _calls(fn) -> list[ast.Call]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]


@pytest.mark.parametrize("name", sorted(_DOORS))
def test_every_door_asks_the_one_gate_by_its_own_name(name):
    from genios_engine.api import routes

    calls = _calls(getattr(routes, name))
    asked = [c for c in calls if c.func.id == "_sweep_gate"]
    assert asked, f"{name} does not ask `_sweep_gate`"
    doors = {kw.value.value for c in asked for kw in c.keywords
             if kw.arg == "door" and isinstance(kw.value, ast.Constant)}
    assert doors == {_DOORS[name]}, (name, doors)
    direct = sorted({c.func.id for c in calls} & _GATE_HELPERS)
    assert not direct, f"{name} asks {direct} itself — a second answer to the gate's question"


def test_the_gate_asks_all_four_in_the_sweeps_order():
    """Plan before budget: "you stopped paying" and "you spent today's allowance" send the
    customer to two different buttons, and the first outranks."""
    from genios_engine.api import routes

    src = textwrap.dedent(inspect.getsource(routes._sweep_gate))
    order = [src.index(f"{h}(") for h in ("_org_paused", "_plan_expired", "_llm_over_daily_cap",
                                          "_sync_headroom")]
    assert order == sorted(order), order


# ── 6 · Postgres: the row lands, and the coverage readers do not count it ─────────────────────

@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger write needs real Postgres")
    return live_db_url


@pytest.mark.pg
def test_the_skip_row_lands_and_no_coverage_reader_counts_it(pg_url, monkeypatch):
    from genios_engine.api import routes
    from genios_engine.capture.coverage.window import coverage_for_window
    from genios_engine.platform.db import get_engine

    engine = get_engine(pg_url)
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=engine))
    finalized: list = []
    monkeypatch.setattr(routes, "finalize_l1", lambda *a, **k: finalized.append(a))
    now = datetime.now(timezone.utc)
    with engine.begin() as c:
        c.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 's02u5@example.test')"),
                  {"o": ORG})
    try:
        routes._note_sweep_skip(ORG, "plan_expired", door="sweep", mode="incremental")
        with engine.connect() as c:
            rows = c.execute(text("select connection_id, source, mode, scanned, error "
                                  "from l1_sync_runs where org_id = :o"), {"o": ORG}).all()
            cov = coverage_for_window(c, org_id=ORG, source="gmail",
                                      since=now - timedelta(hours=1),
                                      until=now + timedelta(hours=1))
        assert len(rows) == 1, rows
        row = rows[0]
        assert (row.connection_id, row.source, row.mode, row.scanned) == (
            None, None, "incremental", 0)
        assert row.error.startswith("skipped:plan_expired door=sweep — ")
        assert cov.runs == 0, "the per-source coverage read counted a skip as a sweep"
        assert finalized == [], "a skip ran L1's finalizer"
    finally:
        with engine.begin() as c:
            c.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
            c.execute(text("delete from orgs where id = :o"), {"o": ORG})
