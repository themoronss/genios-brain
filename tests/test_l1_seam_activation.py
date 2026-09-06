"""S-3 — IS THE L1 -> L2 SEAM LIVE-ABLE FOR ONE TENANT, OR IS IT DARK FOR EVERYONE?

THE DEFECT. Layer 1 publishes `qualified_signals`; the one production reader of that table is
`context/situation_bso.gather_l1_signals`, and its only caller on any live path is
`reason/domain_shadow.shadow_compile`, which `reason/runner.run_all` entered ONLY behind
`platform/config.py::Settings.use_domain_compiler` — a global boolean that is `False` in the class
and set in no environment. So the seam had two states and both were wrong: off (today) means Layer
3 never reads a single thing Layer 1 published, and on means every tenant's Layer 3 changes at
once on one deploy. The build order's own rule covers exactly this — *"NO GLOBAL BOOLEAN FLAGS.
Activation is a table"* — and the activation table already exists: `l1_semantic_activation`, the
row that says which tenant's Layer 1 v2 lane is live.

WHAT IS ASSERTED HERE. Two tenants, one scratch Postgres, the SAME email captured through the
same production door for both, and one row in `l1_semantic_activation` between them. The activated
tenant's situation must reach Layer 3 carrying the importance Layer 1 stored; the other tenant must
stay on the old path — and the global setting must still be `False` the whole time, because if the
switch were the setting the second tenant would have moved too.

Real Postgres: skips without GENIOS_TEST_DATABASE_URL, the same gate every other seam test has.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import text

from genios_engine.platform.activation import (
    activate_semantic,
    deactivate_semantic,
)
from tests.test_l2_reads_what_l1_publishes import NOW, _capture, _drain

pytestmark = pytest.mark.pg

ORG_ON = "seam_gate_on"
ORG_OFF = "seam_gate_off"


@pytest.fixture(autouse=True)
def _no_activation_rows_left_behind(pg_store):
    """This file is the only one that writes `l1_semantic_activation` for orgs that are not its
    own scratch tenant, and a deactivation deliberately KEEPS the row (migration 0090). Left in
    place, those rows are a cross-org listing that another file reads — `test_l1_pilot_activation`
    asserts the exact contents of `/admin/pilot/activation`, and a stale `seam_gate_on` there is a
    failure this file caused in a suite it never ran with. Deleted, not deactivated, at both ends.
    """
    def _clear():
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from l1_semantic_activation where org_id = any(:o)"),
                         {"o": [ORG_ON, ORG_OFF]})
    _clear()
    yield
    _clear()


@pytest.fixture
def url() -> str:
    value = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres seam tests skipped")
    return value


def _seed(url: str, pg_store, org: str, monkeypatch, object_id: str) -> int:
    """One email through the real sync door, then the real drain. Returns the importance Layer 1
    stored for it — the number the seam is supposed to carry into Layer 3."""
    from genios_engine.capture.esqe.signal_store import PostgresSignalStore

    store = PostgresSignalStore(url)
    _capture(url, pg_store, org, monkeypatch, signal_store=store, object_id=object_id)
    published = store.list(org)
    assert published, f"Layer 1 published no qualified signal for {org}"
    out = _drain(pg_store, org)
    assert out["situation_rows"] >= 1, f"the drain built no situation for {org}: {out}"
    return max(r.importance_bp for r in published)


def _run_reasoning(pg_store, org: str, monkeypatch) -> list[Any]:
    """`reason/runner.run_all` — THE production entry. Every BSO the L2 -> L3 pass builds during
    this org's sweep is recorded; an empty list means the seam never ran for this tenant."""
    from genios_engine.reason import domain_shadow, runner

    seen: list[Any] = []
    real = domain_shadow.build_business_situation

    def _spy(**kwargs):
        bso = real(**kwargs)
        seen.append(bso)
        return bso

    monkeypatch.setattr(domain_shadow, "build_business_situation", _spy)
    runner.run_all(org_id=org, store=pg_store, eval_time=NOW)
    return seen


def _l1_scored(bsos: list[Any]) -> list[Any]:
    return [b for b in bsos if b.metadata.get("importance_source") == "l1_qualified_signals"]


# =============================================================================================
# THE TEST THAT COUNTS — one row, one tenant, and nobody else
# =============================================================================================
def test_one_activation_row_makes_the_seam_live_for_that_tenant_only(url, pg_store, monkeypatch):
    """Same email, same code, two tenants. The only difference is a row."""
    from genios_engine.platform.config import get_settings

    expected_on = _seed(url, pg_store, ORG_ON, monkeypatch, "msg_gate_on")
    expected_off = _seed(url, pg_store, ORG_OFF, monkeypatch, "msg_gate_off")
    assert expected_on == expected_off, "the two tenants were not given the same email"

    # The switch. One tenant, named, by a person, with a reason — nothing global is touched.
    activate_semantic(pg_store.engine, ORG_ON, by="founder@genios.test",
                      notes="S-3 pilot: first tenant on the L1 -> L2 seam")
    assert get_settings().use_domain_compiler is False, (
        "this test proves per-tenant activation; a global flag set to True would prove nothing")

    on = _run_reasoning(pg_store, ORG_ON, monkeypatch)
    off = _run_reasoning(pg_store, ORG_OFF, monkeypatch)

    from genios_engine.context.situation_bso import DEFAULT_IMPORTANCE_BP
    assert expected_on != DEFAULT_IMPORTANCE_BP, (
        "this email happens to score exactly the constant the old path stamps, so the assertions "
        "below would pass against the defect — change the fixture, never the assertion")

    carried = _l1_scored(on)
    assert carried, (
        "the activated tenant's sweep built no situation carrying Layer 1's score — the seam is "
        f"still dark. sources seen: {sorted({b.metadata.get('importance_source') for b in on})}")
    assert all(b.importance_bp == expected_on for b in carried), (
        f"the activated tenant's situation carries {sorted({b.importance_bp for b in carried})} "
        f"while Layer 1 stored {expected_on}")

    assert not _l1_scored(off), (
        "a tenant with NO activation row read Layer 1's published signals — enabling one pilot "
        "org moved somebody else too")


def test_the_row_switches_the_seam_back_off(url, pg_store, monkeypatch):
    """A migration you cannot reverse is a cutover with extra steps. The same tenant, before and
    after `deactivate_semantic`, on one already-seeded org."""
    expected = _seed(url, pg_store, ORG_ON, monkeypatch, "msg_gate_rollback")

    activate_semantic(pg_store.engine, ORG_ON, by="founder@genios.test", notes="rollback drill")
    live = _l1_scored(_run_reasoning(pg_store, ORG_ON, monkeypatch))
    assert live and all(b.importance_bp == expected for b in live), (
        "the seam did not come up for the activated tenant")

    assert deactivate_semantic(pg_store.engine, ORG_ON, by="founder@genios.test") is True
    assert not _l1_scored(_run_reasoning(pg_store, ORG_ON, monkeypatch)), (
        "switching the tenant off left the seam running — the pilot cannot be rolled back")

    # The row SURVIVES the switch-off (migration 0090), so the diff window can still say when.
    with pg_store.engine.connect() as conn:
        row = conn.execute(text(
            "select disabled_at, disabled_by from l1_semantic_activation where org_id=:o"),
            {"o": ORG_ON}).first()
    assert row is not None and row.disabled_at is not None


# =============================================================================================
# THE GATE ITSELF — read once, fail closed, and never a global boolean
# =============================================================================================
def test_the_gate_is_the_table_and_fails_closed(pg_store):
    from genios_engine.platform.config import l1_seam_enabled

    deactivate_semantic(pg_store.engine, ORG_ON)
    assert l1_seam_enabled(pg_store.engine, ORG_ON) is False
    activate_semantic(pg_store.engine, ORG_ON, by="founder@genios.test")
    assert l1_seam_enabled(pg_store.engine, ORG_ON) is True
    assert l1_seam_enabled(pg_store.engine, "org_never_in_the_pilot") is False
    # No engine, an unreadable table, a database that is gone: every one of them is OFF. The
    # failure mode of this lookup is a tenant on the path they are already on.
    assert l1_seam_enabled(None, ORG_ON) is False
    deactivate_semantic(pg_store.engine, ORG_ON)


def test_the_seams_gate_is_not_the_domain_compiler_flag():
    """`use_domain_compiler` is a DIFFERENT subsystem's switch (the Layer 3 compiled-brain
    cutover) that merely happened to gate this reader. The enablement path must not consult it to
    decide which TENANTS read what Layer 1 published."""
    import inspect

    from genios_engine.platform import config

    # The CODE, not the prose: the docstring has to be able to name the flag it replaced, and a
    # substring check over the whole source would forbid explaining the defect at the one place a
    # reader will look for it.
    body = inspect.getsource(config.l1_seam_enabled).replace(
        config.l1_seam_enabled.__doc__ or "\0", "")
    assert "use_domain_compiler" not in body, (
        "the per-tenant seam gate reads a global boolean again")
    assert "is_semantic_activated" in body, "the seam gate no longer reads the activation table"

    from genios_engine.reason import runner
    gate = inspect.getsource(runner.run_all)
    assert "l1_seam_enabled" in gate, (
        "reason/runner.run_all no longer enters the L2 -> L3 pass through the per-tenant gate")
