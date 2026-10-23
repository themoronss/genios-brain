"""One health row per org per day, with alerts — against REAL Postgres (GeniOS-011 S05.U1).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_daily_health_pg.py -q

⛔ WHY. Nothing measured production card volume or quality daily (`process-no-daily-production-card-health`),
and the database reached its 500 MB tier twice in 17 days with no daily size line (`cross-db-tier-never-
budgeted`). `platform/daily_health` writes one row per org per UTC day from the tables that already hold the
facts, and `ops_alert` fires when cards per day fall below half the 14-day median, when a lane reads NO DATA
for the day, or when the database passes its ceiling. What only a database can prove: every number in the
row is the count the source table holds for that day and no other, the key makes "once a day" true across
ticks, and the alert reads the same median the row stores.

The scheduler half (`platform/scheduler`) is hermetic: the heavy tick runs the job, the light tick does not,
and a job that raises does not fail the tick.
"""
from __future__ import annotations

import threading
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import daily_health as DH
from genios_engine.platform import funnel

#: 06:00 UTC on 23 Oct: the row the job writes is 22 Oct, a whole day; the 14 days before it are the baseline.
NOW = datetime(2026, 10, 23, 6, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 22)

ORG_ROW = "org_s05u1_row"
ORG_DROP = "org_s05u1_drop"
ORG_EDGE = "org_s05u1_edge"
ORG_DARK = "org_s05u1_dark"
ORG_LINKED = "org_s05u1_linked"
ORG_UNLINKED = "org_s05u1_unlinked"
ORGS = (ORG_ROW, ORG_DROP, ORG_EDGE, ORG_DARK, ORG_LINKED, ORG_UNLINKED)

#: A ceiling no scratch database reaches — the size alert stays out of tests that are not about it.
NO_CEILING = 1 << 60


# ── fixtures ────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the daily health row needs real Postgres")
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
    yield eng
    _purge(eng)


@pytest.fixture
def alerts(monkeypatch):
    """Every `ops_alert.notify` the job makes, captured instead of posted."""
    from genios_engine.platform import ops_alert
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(ops_alert, "notify", lambda event, **fields: sent.append((event, fields)))
    return sent


def _purge(eng) -> None:
    with eng.begin() as c:
        # `llm_costs` is retained financial data (0058 dropped its cascade), so it is deleted by hand.
        c.execute(text("delete from llm_costs where org_id = any(:o)"), {"o": list(ORGS)})
        c.execute(text("delete from orgs where id = any(:o)"), {"o": list(ORGS)})       # cascades


def _at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


def _cards(eng, org: str, day: date, n: int, *, builder: str = "team.emit.v1",
           lane: str = "decision", hour: int = 12) -> None:
    with eng.begin() as c:
        for i in range(n):
            cid = f"card_{org}_{day.isoformat()}_{builder}_{lane}_{hour}_{i}"
            c.execute(text(
                "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                "score, expires_at, created_at, builder_version, output_lane, lane_reason) values "
                "(:id, :sig, :o, 'prescriptive', 'high', 'h', 's', 60, :exp, :at, :b, :lane, 'seeded')"),
                {"id": cid, "sig": f"sig_{cid}", "o": org, "exp": NOW + timedelta(days=7),
                 "at": _at(day, hour), "b": builder, "lane": lane})


def _baseline_cards(eng, org: str, per_day: int) -> None:
    for back in range(1, DH.WINDOW_DAYS + 1):
        _cards(eng, org, DAY - timedelta(days=back), per_day)


def _row(eng, org: str, day: date = DAY):
    with eng.connect() as c:
        return c.execute(text("select * from daily_health where org_id = :o and day = :d"),
                         {"o": org, "d": day}).mappings().one_or_none()


def _kinds(row) -> list[str]:
    return [a["kind"] for a in row["alerts"]]


# ── the row ─────────────────────────────────────────────────────────────────────────────────────

def _seed_every_source(eng) -> None:
    o, d = ORG_ROW, DAY
    _cards(eng, o, d, 2, builder="team.emit.v1", lane="decision")
    _cards(eng, o, d, 1, builder="pipeline.v2", lane="investigation")
    _cards(eng, o, d, 1, builder="team.emit.v1", lane="decision", hour=0)        # 00:xx belongs to the day
    _cards(eng, o, d + timedelta(days=1), 5, hour=0)                            # today: not the row's day
    _cards(eng, o, d - timedelta(days=30), 3)                                   # outside every window
    with eng.begin() as c:
        for i, rule in enumerate(("us", "us", "money")):
            c.execute(text(
                "insert into card_refusals (org_id, refusal_id, writer, ref, rule, found, refused_at) "
                "values (:o, :id, 'pipeline', 'sig_x', :rule, 'f', :at)"),
                {"o": o, "id": f"ref_{o}_{i}", "rule": rule, "at": _at(d)})
        c.execute(text(
            "insert into card_refusals (org_id, refusal_id, writer, ref, rule, found, refused_at) "
            "values (:o, 'ref_late', 'pipeline', 'sig_x', 'quote', 'f', :at)"), {"o": o, "at": _at(d + timedelta(days=1))})
        for i, status in enumerate(("refused", "truncated", "truncated")):
            c.execute(text(
                "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, dossier_digest, "
                "status, reason, reviewed_at) values (:o, :f, :fp, 'm', 'p', 'dd', :s, 'seeded', :at)"),
                {"o": o, "f": f"file_{i}", "fp": f"fp_{i}", "s": status, "at": _at(d)})
        for i, status in enumerate(("result", "result", "failed")):
            c.execute(text(
                "insert into reasoning_results (org_id, subject_ref, fingerprint, request_id, trigger, status, "
                "depth, prompt_version, reasoned_at) values (:o, :s, :fp, :r, 't', :st, 'none', 'p', :at)"),
                {"o": o, "s": f"subj_{i}", "fp": f"fp_{i}", "r": f"req_{i}", "st": status, "at": _at(d)})
        for i, decision in enumerate(("admit", "hold", "hold")):
            c.execute(text(
                "insert into l2_admissions (org_id, subject_ref, situation_id, decision, op, result_fingerprint, "
                "decided_at) values (:o, :s, '-', :dec, 'none', 'fp', :at)"),
                {"o": o, "s": f"subj_{i}", "dec": decision, "at": _at(d)})
        # Two sweeps that day: the first writes all five stages, the second only the first two, and
        # `decision_emitted` is a written zero — a stage that ran and counted nothing.
        for sweep, counts in (("sw1", {"signals_detected": 40, "situations_formed": 9,
                                       "capability_resolved": 6, "decision_emitted": 0,
                                       "card_delivered": 3}),
                              ("sw2", {"signals_detected": 2, "situations_formed": 1})):
            for stage, n in counts.items():
                c.execute(text(
                    "insert into pipeline_counters (org_id, sweep_id, stage, n, sweep_at) "
                    "values (:o, :sw, :st, :n, :at)"),
                    {"o": o, "sw": sweep, "st": stage, "n": n, "at": _at(d)})
        for success, error in ((True, None), (True, None), (False, "overloaded"),
                               (False, "truncated: the model hit max_tokens and the JSON was cut "
                                       "mid-structure (max_tokens=600)"),
                               (True, "truncated: the model hit max_tokens and the JSON was cut "
                                      "mid-structure (max_tokens=900)")):
            c.execute(text(
                "insert into llm_costs (org_id, model, purpose, success, error, created_at) "
                "values (:o, 'm', 'extract', :ok, :e, :at)"),
                {"o": o, "ok": success, "e": error, "at": _at(d)})
        for outcome in ("ran", "ran", "failed_generation", "skipped_budget"):
            c.execute(text(
                "insert into l4_r_site_calls (org_id, site, outcome, tier, cache_key, created_at) "
                "values (:o, 'R-1', :out, 't', 'k', :at)"), {"o": o, "out": outcome, "at": _at(d)})


@pytest.mark.pg
def test_one_row_holds_every_number_for_that_day_and_no_other(engine, alerts):
    _seed_every_source(engine)
    out = DH.run_daily_health(engine, now=NOW, orgs=[ORG_ROW], ceiling=NO_CEILING)
    assert out["day"] == DAY.isoformat() and out["written"] == 1, out

    row = _row(engine, ORG_ROW)
    assert row is not None
    assert row["cards"] == {"team.emit.v1": {"decision": 3}, "pipeline.v2": {"investigation": 1}}
    assert row["cards_total"] == 4
    assert row["card_refusals"] == {"us": 2, "money": 1}
    assert row["expert_reviews"] == {"refused": 1, "truncated": 2}
    assert row["reasoning_results"] == {"result": 2, "failed": 1}
    assert row["l2_admissions"] == {"admit": 1, "hold": 2}
    assert row["funnel"] == {"signals_detected": 42, "situations_formed": 10, "capability_resolved": 6,
                             "decision_emitted": 0, "card_delivered": 3}
    assert set(row["funnel"]) == set(funnel.STAGES)
    assert (row["llm_calls"], row["llm_failures"], row["llm_truncations"]) == (5, 2, 2), (
        "a truncation is counted by its error, whether or not the lenient parser closed the JSON")
    assert row["r_site_calls"] == {"ran": 2, "failed_generation": 1, "skipped_budget": 1}
    assert row["database_bytes"] > 0
    assert row["measured_at"] is not None


@pytest.mark.pg
def test_a_stage_no_sweep_wrote_is_null_not_zero(engine, alerts):
    """0188's rule carried into the row: `null` = nobody looked, `0` = it ran and counted nothing."""
    _cards(engine, ORG_ROW, DAY, 1)
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_ROW], ceiling=NO_CEILING)
    row = _row(engine, ORG_ROW)
    assert row["funnel"] == {stage: None for stage in funnel.STAGES}
    assert row["card_refusals"] == {} and row["llm_calls"] == 0


@pytest.mark.pg
def test_once_a_day_means_once_a_second_tick_writes_and_alerts_nothing(engine, alerts):
    _baseline_cards(engine, ORG_DROP, 10)
    first = DH.run_daily_health(engine, now=NOW, orgs=[ORG_DROP], ceiling=NO_CEILING)
    sent = len(alerts)
    second = DH.run_daily_health(engine, now=NOW + timedelta(hours=6), orgs=[ORG_DROP],
                                 ceiling=NO_CEILING)
    assert first["written"] == 1 and sent >= 1
    assert second["written"] == 0 and second["already_written"] == 1, second
    assert len(alerts) == sent, "a second tick on the same day alerted again"
    with engine.connect() as c:
        assert c.execute(text("select count(*) from daily_health where org_id = :o"),
                         {"o": ORG_DROP}).scalar() == 1


# ── the alerts ──────────────────────────────────────────────────────────────────────────────────

@pytest.mark.pg
def test_cards_below_half_the_14_day_median_alert_and_at_half_they_do_not(engine, alerts):
    """⛔ THE THRESHOLD. Median 10: 4 cards is below half and alerts; 5 is exactly half and does not."""
    _baseline_cards(engine, ORG_DROP, 10)
    _cards(engine, ORG_DROP, DAY, 4)
    _baseline_cards(engine, ORG_EDGE, 10)
    _cards(engine, ORG_EDGE, DAY, 5)
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_DROP, ORG_EDGE], ceiling=NO_CEILING)

    drop, edge = _row(engine, ORG_DROP), _row(engine, ORG_EDGE)
    assert float(drop["cards_median_14d"]) == 10.0 and float(edge["cards_median_14d"]) == 10.0
    assert "cards_below_half_median" in _kinds(drop), drop["alerts"]
    assert "cards_below_half_median" not in _kinds(edge), edge["alerts"]
    events = [(e, f["org_id"]) for e, f in alerts if e == "daily_health_cards_below_half_median"]
    assert events == [("daily_health_cards_below_half_median", ORG_DROP)], alerts


@pytest.mark.pg
def test_a_quiet_tenant_with_no_baseline_does_not_alert_on_volume(engine, alerts):
    _cards(engine, ORG_EDGE, DAY, 0)
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_EDGE], ceiling=NO_CEILING)
    row = _row(engine, ORG_EDGE)
    assert float(row["cards_median_14d"]) == 0.0 and row["alerts"] == [], row["alerts"]
    assert alerts == []


@pytest.mark.pg
def test_a_lane_that_ran_most_days_and_was_silent_for_the_day_is_no_data(engine, alerts):
    """A card path, the expert and a funnel stage each wrote on every baseline day and not on the row's
    day: each is NO DATA for 24 h. A lane that never ran in the window is not expected and stays quiet."""
    for back in range(1, DH.WINDOW_DAYS + 1):
        d = DAY - timedelta(days=back)
        _cards(engine, ORG_DARK, d, 2, builder="team.emit.v1")
        _cards(engine, ORG_DARK, d, 2, builder="pipeline.v2", lane="investigation")
        with engine.begin() as c:
            c.execute(text(
                "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, dossier_digest, "
                "status, reason, reviewed_at) values (:o, :f, 'fp', 'm', 'p', 'dd', 'refused', 'r', :at)"),
                {"o": ORG_DARK, "f": f"file_{back}", "at": _at(d)})
            c.execute(text(
                "insert into pipeline_counters (org_id, sweep_id, stage, n, sweep_at) "
                "values (:o, :sw, 'card_delivered', 0, :at)"), {"o": ORG_DARK, "sw": f"sw{back}", "at": _at(d)})
    _cards(engine, ORG_DARK, DAY, 4, builder="pipeline.v2", lane="investigation")   # this path still writes

    DH.run_daily_health(engine, now=NOW, orgs=[ORG_DARK], ceiling=NO_CEILING)
    row = _row(engine, ORG_DARK)
    no_data = [a for a in row["alerts"] if a["kind"] == "lane_no_data"]
    assert len(no_data) == 1, row["alerts"]
    assert set(no_data[0]["lanes"]) == {"cards.builder:team.emit.v1", "cards.lane:decision",
                                        "expert_reviews", "funnel:card_delivered"}, no_data
    assert "cards_below_half_median" not in _kinds(row), "4 of a median 4 is not a drop"
    assert [e for e, _ in alerts] == ["daily_health_lane_no_data"], alerts


@pytest.mark.pg
def test_the_database_past_its_ceiling_alerts_once_per_run_not_once_per_org(engine, alerts):
    _cards(engine, ORG_ROW, DAY, 1)
    _cards(engine, ORG_EDGE, DAY, 1)
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_ROW, ORG_EDGE], ceiling=1)
    size = [f for e, f in alerts if e == "daily_health_database_over_ceiling"]
    assert len(size) == 1 and size[0]["bytes"] > size[0]["ceiling_bytes"] == 1, alerts
    for org in (ORG_ROW, ORG_EDGE):
        assert "database_over_ceiling" in _kinds(_row(engine, org))


@pytest.mark.pg
def test_under_the_ceiling_the_size_is_recorded_and_nothing_fires(engine, alerts):
    _cards(engine, ORG_ROW, DAY, 1)
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_ROW], ceiling=NO_CEILING)
    assert _row(engine, ORG_ROW)["database_bytes"] > 0
    assert [e for e, _ in alerts if e == "daily_health_database_over_ceiling"] == []


def test_the_ceiling_defaults_below_the_500_mb_tier_and_an_operator_can_move_it(monkeypatch):
    monkeypatch.delenv(DH.CEILING_ENV, raising=False)
    assert DH.ceiling_bytes() == DH.DEFAULT_CEILING_MB * 1024 * 1024 < 500 * 1024 * 1024
    monkeypatch.setenv(DH.CEILING_ENV, "300")
    assert DH.ceiling_bytes() == 300 * 1024 * 1024
    monkeypatch.setenv(DH.CEILING_ENV, "not a number")
    assert DH.ceiling_bytes() == DH.DEFAULT_CEILING_MB * 1024 * 1024


# ── which orgs, and the bound ───────────────────────────────────────────────────────────────────

@pytest.mark.pg
def test_a_tenant_with_a_connected_source_or_an_active_pack_gets_a_row(engine):
    with engine.begin() as c:
        c.execute(text("insert into connections (connection_id, org_id, status) "
                       "values ('con_s05u1_on', :o, 'connected')"), {"o": ORG_LINKED})
        c.execute(text("insert into connections (connection_id, org_id, status) "
                       "values ('con_s05u1_off', :o, 'disconnected')"), {"o": ORG_UNLINKED})
        c.execute(text("insert into tenant_packs (org_id, pack_id, version, state) "
                       "values (:o, 'admin', '1', 'active')"), {"o": ORG_DARK})
    try:
        with engine.connect() as c:
            orgs = DH.orgs_to_measure(c)
        assert ORG_LINKED in orgs and ORG_DARK in orgs
        assert ORG_UNLINKED not in orgs
    finally:
        with engine.begin() as c:
            c.execute(text("delete from connections where connection_id like 'con_s05u1_%'"))
            c.execute(text("delete from tenant_packs where org_id = :o"), {"o": ORG_DARK})


@pytest.mark.pg
def test_rows_past_the_retention_are_purged_by_the_run_that_writes(engine, alerts):
    old = DAY - timedelta(days=DH.RETENTION_DAYS + 1)
    kept = DAY - timedelta(days=DH.RETENTION_DAYS - 1)
    with engine.begin() as c:
        for d in (old, kept):
            c.execute(text("insert into daily_health (org_id, day) values (:o, :d)"), {"o": ORG_ROW, "d": d})
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_ROW], ceiling=NO_CEILING)
    assert _row(engine, ORG_ROW, old) is None
    assert _row(engine, ORG_ROW, kept) is not None and _row(engine, ORG_ROW) is not None


@pytest.mark.pg
def test_one_org_failing_does_not_stop_the_rest(engine, alerts, monkeypatch):
    real = DH.measure_day

    def flaky(conn, org_id, day):
        if org_id == ORG_DROP:
            raise RuntimeError("one tenant's read broke")
        return real(conn, org_id, day)
    monkeypatch.setattr(DH, "measure_day", flaky)
    _cards(engine, ORG_ROW, DAY, 1)
    out = DH.run_daily_health(engine, now=NOW, orgs=[ORG_DROP, ORG_ROW], ceiling=NO_CEILING)
    assert out["written"] == 1 and out["failed"] == [ORG_DROP], out
    assert _row(engine, ORG_ROW) is not None


# ── hermetic: the threshold, the truncation mark, the scheduler ─────────────────────────────────

def test_the_threshold_is_half_the_median_by_the_pure_rule():
    assert DH.cards_alert(4, [10] * 14) is not None
    assert DH.cards_alert(5, [10] * 14) is None
    assert DH.cards_alert(0, [0] * 14) is None
    assert DH.cards_alert(2, [0] * 7 + [10] * 7) is not None                       # median 5


def test_the_truncation_mark_is_the_clients_own_words():
    """`llm_costs.error` is written from `LLMClient`'s TRUNCATED; the job's LIKE must match its prefix."""
    from genios_engine.context.llm.client import TRUNCATED
    assert TRUNCATED.startswith(DH.TRUNCATED_PREFIX)


def test_a_failing_job_never_raises():
    class _Broken:
        def connect(self):
            raise RuntimeError("database is gone")
    out = DH.run_daily_health(_Broken(), now=NOW, orgs=[ORG_ROW])
    assert out["error"].startswith("RuntimeError"), out


def _drive_loop(monkeypatch, *, health, light_interval: float):
    """Run the real `_loop` for one heavy tick and one light tick, then stop it."""
    from genios_engine.platform import scheduler as S
    ran: list[str] = []

    def tick():
        ran.append("heavy")
        return {}

    def light():
        ran.append("light")
        S._stop.set()
        return {}

    def daily():
        ran.append("daily")
        return health()
    monkeypatch.setattr(S, "_tick", tick)
    monkeypatch.setattr(S, "_light_tick", light)
    monkeypatch.setattr(S, "_daily_health", daily)
    S._stop.clear()
    t = threading.Thread(target=S._loop, args=(3600.0, 0.0, light_interval), daemon=True)
    t.start()
    t.join(timeout=10)
    S._stop.clear()
    assert not t.is_alive(), "the loop did not stop"
    return ran


def test_the_heavy_tick_runs_the_daily_job_and_the_light_tick_does_not(monkeypatch):
    ran = _drive_loop(monkeypatch, health=lambda: {"written": 0}, light_interval=0.01)
    assert ran == ["heavy", "daily", "light"], ran


def test_a_daily_job_that_raises_does_not_fail_the_tick(monkeypatch, alerts):
    def boom():
        raise RuntimeError("health read failed")
    ran = _drive_loop(monkeypatch, health=boom, light_interval=0.01)
    assert ran == ["heavy", "daily", "light"], "the loop stopped after the daily job raised"
    assert [e for e, _ in alerts] == ["daily_health_crashed"], alerts


def test_the_scheduler_job_measures_through_the_routes_engine(monkeypatch):
    """`_daily_health` uses the engine the heavy tick uses, and with no database it skips, never raises."""
    from genios_engine.api import routes
    from genios_engine.platform import scheduler as S
    seen = []
    monkeypatch.setattr(DH, "run_daily_health", lambda eng, **kw: seen.append(eng) or {"written": 0})
    monkeypatch.setattr(routes, "_graph", None)
    assert S._daily_health() == {"skipped": "no_database"} and seen == []

    class _G:
        engine = object()
    monkeypatch.setattr(routes, "_graph", _G())
    assert S._daily_health() == {"written": 0} and seen == [_G.engine]


# ── GeniOS-012 U12-01 · an expired plan is said on the row ─────────────────────────────────────

@pytest.mark.pg
def test_an_expired_tenant_row_says_so_and_alerts_once(engine, alerts):
    """The sweep skips an expired tenant; its row now says `plan_state = 'expired'` and raises `plan_expired`."""
    with engine.begin() as c:
        c.execute(text("update orgs set plan_status = 'expired', plan_expires_at = :at, grace_until = null "
                       "where id = :o"), {"o": ORG_DARK, "at": NOW - timedelta(days=32)})
        c.execute(text("update orgs set plan_status = 'active', plan_expires_at = :at, grace_until = null "
                       "where id = :o"), {"o": ORG_EDGE, "at": NOW + timedelta(days=30)})
    DH.run_daily_health(engine, now=NOW, orgs=[ORG_DARK, ORG_EDGE], ceiling=NO_CEILING)
    dark, edge = _row(engine, ORG_DARK), _row(engine, ORG_EDGE)
    assert dark["plan_state"] == "expired" and "plan_expired" in _kinds(dark)
    assert edge["plan_state"] == "active" and "plan_expired" not in _kinds(edge)
    assert [e for e, f in alerts if e == "daily_health_plan_expired" and f["org_id"] == ORG_DARK]
    DH.run_daily_health(engine, now=NOW + timedelta(hours=6), orgs=[ORG_DARK], ceiling=NO_CEILING)
    assert len([e for e, _f in alerts if e == "daily_health_plan_expired"]) == 1, "once a day means once"
