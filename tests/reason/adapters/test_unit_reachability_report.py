"""K1a's gate command: `python scripts/unit_reachability_report.py --org <pilot>`.

The report answers one question the engine could not answer about itself — which reasoning units
actually reached a Finding on a real tenant, and what the receipt says for the ones that did not.
So it is tested the way it is used: against a real Postgres tenant with real Layer 1 ingestion, a
real corpus and the real compiled lane, plus the hermetic checks that keep it a GATE rather than a
description (a non-zero exit, a refusal to guess its own database, an instant it takes as an
argument, and a silence it cannot round up to a pass).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import situations

from scripts._db import UnsafeDatabaseTarget
from scripts.unit_reachability_report import (
    MINIMUM_UNITS_EMITTING,
    STATED_DORMANT,
    Reachability,
    UnitRow,
    collect,
    main,
    parse_instant,
    read_only_engine,
    render,
)

from ...l1_supply import attach_l1_signals
from ...test_admin_support_packs import NOW, _run_admin, _seed_org

pytestmark = pytest.mark.pg


def _pilot(pg_store, org: str, *, activate_roster: bool) -> None:
    from genios_engine.platform.l4_activation import activate

    _seed_org(pg_store, org)
    # ORG-SCOPED EVENT ID — `source_events_pkey` is `(event_id)` alone and `_seed_event` inserts
    # `on conflict do nothing`, so the constant default gives every org after the first no
    # `source_events` row at all.
    _run_admin(pg_store, org, event_id=f"adm_evt_{org}")
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    # THE GATE COMMAND MEASURES A TENANT, so the tenant has to be one. L2's admission gate refuses
    # a situation with no verified evidence span, and only a `qualified_signals` row carries one:
    # without this the K1a report ran against a tenant whose every situation was HELD and reported
    # UNRECEIPTED SILENCE for twenty units that were never given anything to observe.
    assert attach_l1_signals(pg_store, org, eval_time=NOW) > 0
    if activate_roster:
        activate(pg_store.engine, org, feature="roster_v2", by="test")


def _url() -> str:
    return os.environ["GENIOS_TEST_DATABASE_URL"]


def test_the_gate_passes_on_an_activated_tenant_and_names_every_units_four_states(pg_store):
    """The K1a row, measured the way the gate measures it: the tenant's own situations, its own
    corpus, its own manifests, and the orchestrator production runs."""
    org = "pk_reach_pass"
    _pilot(pg_store, org, activate_roster=True)

    report = collect(database_url=_url(), org_id=org, at=NOW, limit=50)

    assert "roster_v2" in report.activated_features
    assert report.executions > 0, dict(report.counts)
    assert len(report.units_emitting) >= MINIMUM_UNITS_EMITTING, report.units_emitting
    assert not report.unreceipted, report.unreceipted
    assert not report.plan_hash_mismatches
    assert not report.unregistered_sources
    assert report.ok, report.checks
    # Four states, not one silence: every registered unit is registered, and every one that did
    # not emit says whether it was declined, dropped, dormant by decision, or ran and had nothing.
    for row in report.units.values():
        assert row.registered
        assert row.receipted, row.unit_id
    rendered = render(report)
    assert "K1a: PASS" in rendered
    assert "core.tradeoff" in rendered


def test_an_unactivated_tenant_measures_the_six_unit_lane_and_the_gate_refuses_it(pg_store):
    """Fail closed. A tenant nobody switched on reasons through the DAG it reasons through today,
    and a gate that passed on that measurement would be certifying the defect."""
    org = "pk_reach_dark"
    _pilot(pg_store, org, activate_roster=False)

    report = collect(database_url=_url(), org_id=org, at=NOW, limit=50)

    assert report.activated_features == ()
    assert report.executions > 0
    declared = {unit_id for unit_id, row in report.units.items() if row.declared}
    assert declared == {"core.context", "core.risk", "core.constraint", "core.priority",
                        "core.confidence", "core.planning"}
    assert not report.checks["roster_v2_activated"]
    assert not report.ok


def test_the_report_writes_nothing_it_was_not_asked_to_write(pg_store):
    org = "pk_reach_readonly"
    _pilot(pg_store, org, activate_roster=True)
    tables = ("expertise_packages", "signals", "reasoning_runs", "graph_facts")

    def counts() -> dict[str, int]:
        with pg_store.engine.connect() as conn:
            return {name: conn.execute(text(f"select count(*) from {name} where org_id=:o"),
                                       {"o": org}).scalar() for name in tables}

    before = counts()
    collect(database_url=_url(), org_id=org, at=NOW, limit=50)

    assert counts() == before


def test_the_reports_engine_is_read_only_at_the_server_not_by_convention(pg_store):
    engine = read_only_engine(_url())
    try:
        with pytest.raises(Exception, match="read-only|read only"):
            with engine.begin() as conn:
                conn.execute(text("create table zz_reachability_should_not_exist (id int)"))
    finally:
        engine.dispose()


def test_the_instrumentation_point_is_restored_even_when_the_pass_fails(pg_store, monkeypatch):
    """One seam is patched to observe the real lane. If a failure could leave it patched, the
    next caller in the process would be reasoning through a report's recorder."""
    from genios_engine.reason import domain_shadow

    org = "pk_reach_restore"
    _pilot(pg_store, org, activate_roster=True)
    original = domain_shadow.reason_native_capability

    def explode(**kwargs):
        raise RuntimeError("the pass fell over")

    monkeypatch.setattr(domain_shadow, "shadow_compile", explode)
    with pytest.raises(RuntimeError):
        collect(database_url=_url(), org_id=org, at=NOW, limit=50)

    assert domain_shadow.reason_native_capability is original


def test_main_exits_non_zero_when_a_row_fails(pg_store, capsys):
    org = "pk_reach_exit"
    _pilot(pg_store, org, activate_roster=False)

    code = main(["--org", org, "--at", "2026-08-20T00:00:00Z", "--database-url", _url()])

    assert code == 1
    assert "K1a: FAIL" in capsys.readouterr().out


def test_main_exits_zero_when_every_row_holds(pg_store, capsys):
    org = "pk_reach_exit_ok"
    _pilot(pg_store, org, activate_roster=True)

    code = main(["--org", org, "--at", "2026-08-20T00:00:00Z", "--database-url", _url(), "--json"])

    assert code == 0
    assert '"ok": true' in capsys.readouterr().out


# ── the gate's own arithmetic, without a database ─────────────────────────────────────────────

def test_a_registered_unit_nothing_accounts_for_fails_the_gate():
    """The state this report exists to make impossible: a unit that is neither declared, nor
    declined, nor skipped, nor run — silence with nobody's name on it."""
    report = Reachability(org_id="org_1", at=NOW, activated_features=("roster_v2",))
    for index in range(MINIMUM_UNITS_EMITTING):
        row = report.row(f"core.u{index}")
        row.registered, row.scheduled, row.situations_with_findings = True, 1, 1
    ghost = report.row("core.forgotten")
    ghost.registered = True

    assert report.unreceipted == ("core.forgotten",)
    assert not report.ok
    assert "UNRECEIPTED SILENCE: core.forgotten" in render(report)


def test_a_unit_dormant_by_a_stated_decision_is_receipted_not_counted_as_silence():
    row = UnitRow("core.signal_composition", registered=True)

    assert row.receipted
    assert STATED_DORMANT["core.signal_composition"].startswith("dormant by decision")


def test_a_plan_hash_that_moved_between_two_plans_of_one_request_fails_the_gate():
    report = Reachability(org_id="org_1", at=NOW, activated_features=("roster_v2",))
    for index in range(MINIMUM_UNITS_EMITTING):
        row = report.row(f"core.u{index}")
        row.registered, row.scheduled, row.situations_with_findings = True, 1, 1
    assert report.ok
    report.plan_hash_mismatches = ("expertise.deal@exp.1",)

    assert not report.checks["plan_hash_deterministic"]
    assert not report.ok


def test_fewer_than_twelve_emitting_units_is_a_failure_however_many_ran():
    report = Reachability(org_id="org_1", at=NOW, activated_features=("roster_v2",))
    for index in range(MINIMUM_UNITS_EMITTING - 1):
        row = report.row(f"core.u{index}")
        row.registered, row.scheduled, row.situations_with_findings = True, 1, 1

    assert not report.ok


def test_the_report_refuses_to_guess_its_own_database(monkeypatch):
    """`.env` on a developer machine is the production tenant. A report is exactly the kind of
    harmless-looking tool that ends up pointed at it."""
    monkeypatch.delenv("GENIOS_TARGET_DATABASE_URL", raising=False)

    with pytest.raises(UnsafeDatabaseTarget, match="without an explicit database target"):
        main(["--org", "pk_whatever"])


def test_the_instant_is_an_argument_and_must_carry_a_timezone():
    assert parse_instant("2026-09-01T00:00:00Z") == datetime(2026, 9, 1, tzinfo=timezone.utc)
    with pytest.raises(Exception, match="timezone"):
        parse_instant("2026-09-01T00:00:00")
