"""STEP-02 · the change gate is counted every sweep, in every lane — zero included.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_gate_is_counted.py -q

Tree `yc2_w27_s02/M20.C6.L-interface.V4.U01`. `run_all`'s outcomes carry `skipped_unchanged` (every
lane: legacy, native and compiled) and `deferred` (a live DEFER that kept its card) on every sweep,
as zeros when nothing was skipped or deferred — a count that appears only when it fires is a count
nobody knows exists. And the compiled lane's share is named on its own, because `run_all` used to
throw the compiled pass's whole result away: nothing it counted reached the sweep.

Not funnel stages: `platform/funnel.STAGES` is closed (migration 0188's check), and `no_new_evidence`
already sits on the same outcomes for the same reason.
"""
from __future__ import annotations

import collections
import dataclasses
import datetime as dt
import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

NOW = dt.datetime(2026, 9, 10, 12, 0, tzinfo=dt.timezone.utc)


def test_a_sweep_with_nothing_to_skip_counts_zeros(pg_store):
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.runner import run_all

    org = "gate_counted_empty"
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from orgs where id = :o"), {"o": org})
        conn.execute(text("insert into orgs (id, name, email) values (:o, :o, 'gce@example.test')"),
                     {"o": org})
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    outcomes = run_all(org_id=org, store=pg_store, eval_time=NOW, registry=registry)["outcomes"]
    assert outcomes["skipped_unchanged"] == 0 and outcomes["deferred"] == 0, outcomes
    assert outcomes["skipped_unchanged_compiled"] == 0, outcomes


def test_the_compiled_lanes_skips_reach_the_sweep(monkeypatch):
    """On the real chain: F13 and one more sweep with nothing new — the sweep's own outcomes say the
    compiled lane skipped, and the legacy lanes' skips are in the same total."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("needs GENIOS_TEST_DATABASE_URL")
    from tests.replays.engine_runner import run_case
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader
    from genios_engine.reason import runner

    base = next(c for c in load_cases() if c.case_id == "F13")
    case = dataclasses.replace(
        base, sweeps=base.sweeps + (base.sweeps[-1] + dt.timedelta(minutes=15),))
    seen: list[dict] = []
    original = runner.run_all

    def spy(**kw):
        result = original(**kw)
        seen.append(result["outcomes"])
        return result

    monkeypatch.setattr(runner, "run_all", spy)
    run_case(case, CassetteRecorder(IdealReader(case)))
    last = seen[-1]
    assert last["skipped_unchanged_compiled"] >= 1, last
    assert last["skipped_unchanged"] >= last["skipped_unchanged_compiled"], last
    assert "deferred" in last, last
