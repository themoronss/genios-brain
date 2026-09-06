"""G10 · pilot activation — the table, and the request path that can actually flip it.

THE DEFECT THIS FILE WAS WRITTEN AGAINST. Migration 0085 shipped `l1_semantic_activation` and
`api/routes.py::_semantic_activated_orgs` reads it on every sweep, so the READ was wired. The
WRITE was not: `activate_semantic` and `deactivate_semantic` had no caller anywhere outside their
own unit test, which made the only way to start a pilot an operator typing INSERT into a psql
session against the production tenant database. A switch nothing can flip is a switch that is
always off — which is the exact failure `use_domain_compiler=False` is cited for in the plan's
"activation rule".

So the tests here are about the SEAM, not about the SQL helpers (`tests/capture/
test_semantic_activation.py` already owns those): a route that exists, is admin-only, is
audited, is idempotent, and whose effect is visible to the thing that decides whether a tenant's
mail goes through the new extraction path.

The Postgres cases need GENIOS_TEST_DATABASE_URL and skip without it, like every other real-DB
file in this suite.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsMarker
from sqlalchemy import text

from genios_engine.api import admin_routes as A
from genios_engine.platform import activation as ACT
from genios_engine.platform.auth import AuthCtx, require_admin

NOW = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK


def _engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the activation table is not exercised")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture
def engine():
    eng = _engine()
    with eng.begin() as c:
        c.execute(text("delete from l1_semantic_activation where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l1_semantic_activation where org_id = :o"), {"o": ORG})


# ── THE SEAM: a request path exists, and it is the admin one ────────────────────────────────

def test_a_request_path_can_switch_the_pilot_on_and_off():
    """The wiring assertion. Read structurally so it cannot be satisfied by a helper somewhere
    that a router never reaches: the writes must be reachable from a REGISTERED route."""
    paths = {(r.path, tuple(sorted(r.methods))) for r in A.router.routes}
    assert ("/admin/l1-activation/{target_org}", ("POST",)) in paths, \
        "no request path switches a tenant ON to the L1 v2 semantic lane"
    assert ("/admin/l1-activation/{target_org}", ("DELETE",)) in paths, \
        "no request path switches a tenant OFF — a cutover you cannot reverse"
    assert ("/admin/l1-activation", ("GET",)) in paths, \
        "no request path answers 'who is on the pilot'"


def test_the_activation_routes_are_registered_on_the_running_application():
    """A router nobody includes is the same defect one level up.

    Read off the OpenAPI schema rather than `app.routes`: this FastAPI includes routers lazily
    (`fastapi.routing._IncludedRouter`), so walking `app.routes` finds 28 opaque objects and no
    paths at all — a check that would pass for a router that was never included.
    """
    from genios_engine.main import app
    paths = app.openapi()["paths"]
    assert "/admin/l1-activation/{target_org}" in paths
    assert {"post", "delete"} <= set(paths["/admin/l1-activation/{target_org}"])
    assert "get" in paths["/admin/l1-activation"]


@pytest.mark.parametrize("name", ["activate_pilot", "deactivate_pilot",
                                 "list_pilot_activation"])
def test_only_geniOS_staff_may_move_a_tenant_between_extraction_paths(name):
    """Activation is not a tenant preference: it changes what a customer's sweep costs us. A
    customer-facing route here would let a tenant switch on their own unbudgeted model calls.

    Resolved by NAME at call time rather than at import: a missing endpoint must fail as this
    assertion, not as a collection error in every other test in the file."""
    import inspect
    endpoint = getattr(A, name, None)
    assert endpoint is not None, f"admin_routes has no {name} — the write side is unwired"
    assert any(isinstance(p.default, DependsMarker) and p.default.dependency is require_admin
               for p in inspect.signature(endpoint).parameters.values())


def test_a_scoped_key_is_refused_before_any_database_lookup():
    """The gate itself, restated at this seam: an extension/agent key is a customer credential."""
    with pytest.raises(HTTPException) as exc:
        require_admin(AuthCtx(org_id=ORG, scopes=["read:context"], source="api_key"))
    assert exc.value.status_code == 403


# ── the route, against the real table ───────────────────────────────────────────────────────

def _ctx() -> AuthCtx:
    return AuthCtx(org_id="org_genios_internal", actor_id="harsh@genios.ai", source="jwt")


def test_the_route_turns_the_lane_on_for_exactly_one_tenant(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    assert ACT.is_semantic_activated(engine, ORG) is False, "precondition: nobody is on the lane"

    body = A.activate_pilot(ORG, A.PilotActivation(notes="design partner, 7-day trial"), _ctx())
    assert body["org_id"] == ORG and body["live"] is True
    assert body["enabled_by"] == "harsh@genios.ai"
    assert body["notes"] == "design partner, 7-day trial"

    # the point of the whole exercise: the thing that decides which extraction path runs
    assert ACT.is_semantic_activated(engine, ORG) is True
    assert ORG in ACT.semantic_activated_orgs(engine)


def test_switching_on_twice_does_not_restart_the_pilot(engine, monkeypatch):
    """A double-click must not move the start date: "since when has this tenant been on the new
    lane" is the question the shadow diff's window is read against."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    first = A.activate_pilot(ORG, A.PilotActivation(notes="first"), _ctx())
    second = A.activate_pilot(ORG, A.PilotActivation(notes="second"),
                              AuthCtx(org_id="org_genios_internal", actor_id="someone.else@genios.ai",
                                      source="jwt"))
    assert second["enabled_at"] == first["enabled_at"]
    assert second["enabled_by"] == "harsh@genios.ai"
    assert second["notes"] == "first", "a re-click must not silently rewrite why the org was chosen"


def test_switching_off_keeps_the_row_so_the_window_can_say_when(engine, monkeypatch):
    """`deactivate` used to DELETE. G10 compares seven days; a window containing a mid-week
    switch-off has to be readable as four days of shadow running, not seven."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    A.activate_pilot(ORG, A.PilotActivation(notes="pilot"), _ctx())
    off = A.deactivate_pilot(ORG, _ctx())

    assert off["switched_off"] is True
    assert off["activation"]["live"] is False
    assert off["activation"]["disabled_at"] is not None
    assert off["activation"]["disabled_by"] == "harsh@genios.ai"
    # the lane sees exactly what a DELETE would have left it
    assert ACT.is_semantic_activated(engine, ORG) is False
    assert ORG not in ACT.semantic_activated_orgs(engine)
    # ...but the history survives
    record = ACT.get_semantic_activation(engine, ORG)
    assert record is not None and record.live is False and record.notes == "pilot"


def test_switching_off_a_tenant_that_is_already_off_is_not_an_error(engine, monkeypatch):
    """The caller's intent — "this tenant must not be on the new lane" — is satisfied either way,
    and a 404 would make a retry after a dropped connection look like a failure."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)
    assert A.deactivate_pilot(ORG, _ctx())["switched_off"] is False


def test_reviving_a_switched_off_tenant_starts_a_NEW_pilot_period(engine, monkeypatch):
    """The opposite case to the double-click, and it must not be answered the same way: dating a
    second period from the first would hand the shadow diff a window containing days the lane did
    not run at all."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    first = ACT.activate_semantic(engine, ORG, by="harsh@genios.ai", notes="round one",
                                  at=NOW - timedelta(days=30))
    ACT.deactivate_semantic(engine, ORG, by="harsh@genios.ai", at=NOW - timedelta(days=20))
    again = ACT.activate_semantic(engine, ORG, by="pratap@genios.ai", notes="round two", at=NOW)

    assert again.enabled_at != first.enabled_at
    assert again.enabled_by == "pratap@genios.ai" and again.notes == "round two"
    assert again.live is True and again.disabled_at is None


def test_a_typo_in_the_org_id_is_a_404_not_a_stack_trace(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    with pytest.raises(HTTPException) as exc:
        A.activate_pilot("org_does_not_exist", A.PilotActivation(), _ctx())
    assert exc.value.status_code == 404


def test_the_list_route_separates_the_live_from_the_switched_off(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    A.activate_pilot(ORG, A.PilotActivation(notes="pilot"), _ctx())
    assert [r["org_id"] for r in A.list_pilot_activation(False, _ctx())["activations"]] == [ORG]

    A.deactivate_pilot(ORG, _ctx())
    assert A.list_pilot_activation(False, _ctx())["activations"] == []
    off = A.list_pilot_activation(True, _ctx())
    assert [r["org_id"] for r in off["activations"]] == [ORG]
    assert off["live"] == 0 and off["total"] == 1


def test_switching_on_is_audited_against_the_admin_who_did_it(engine, monkeypatch):
    """A tenant whose bill changed needs an answer to "who decided this". `enabled_by` answers it
    on the row; the audit log answers it in the place every other admin act is recorded."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    seen: list[dict] = []
    monkeypatch.setattr("genios_engine.platform.audit.record",
                        lambda org, action, **kw: seen.append({"org": org, "action": action, **kw}))

    A.activate_pilot(ORG, A.PilotActivation(notes="why"), _ctx())
    A.deactivate_pilot(ORG, _ctx())

    assert [e["metadata"]["value"] for e in seen] == [True, False]
    assert all(e["metadata"]["field"] == "l1_semantic_activation" for e in seen)
    assert all(e["actor_id"] == "harsh@genios.ai" and e["target_id"] == ORG for e in seen)


# ── erasure ─────────────────────────────────────────────────────────────────────────────────

def test_the_activation_row_leaves_with_the_tenant():
    """`_ORG_SCOPED_TABLES` runs `delete from {tbl}` with no try/except by design, so a name
    missing from it leaks silently rather than failing loudly. The row names a person
    (`enabled_by`, `disabled_by`) and carries free text about the tenant (`notes`)."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    assert "l1_semantic_activation" in _ORG_SCOPED_TABLES


def test_a_reset_leaves_the_tenant_on_the_OLD_extraction_path(engine, monkeypatch):
    """The one entry in that list whose removal changes behaviour — and it changes it in the safe
    direction. A tenant whose graph was just wiped goes back to the path every tenant that never
    joined the pilot is on, until somebody deliberately switches them on again."""
    from genios_engine.api.account_routes import _wipe
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)
    ACT.activate_semantic(engine, ORG, by="harsh@genios.ai", notes="pilot")
    assert ACT.is_semantic_activated(engine, ORG) is True

    with engine.begin() as c:
        wiped = _wipe(c, ORG)
    assert wiped["l1_semantic_activation"] == 1
    assert ACT.is_semantic_activated(engine, ORG) is False


def test_the_migration_cascades_the_activation_row_on_account_deletion():
    """Read out of the migration text, the same way tests/test_account_erasure.py does it: a
    table that survives a tenant deletion is a compliance defect found during an audit."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "migrations"
    ddl = (root / "0085_l1_semantic_activation.sql").read_text()
    assert "references orgs (id) on delete cascade" in ddl


# ── the table is still the ONLY switch ──────────────────────────────────────────────────────

def test_there_is_no_second_activation_table():
    """The plan prints `l1_v2_activation` and forbids building a second switch. This tree spells
    the same table `l1_semantic_activation` and migration 0090 extends it to the printed shape —
    so the plan's name must appear nowhere as a real table."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for path in list((root / "migrations").glob("*.sql")) + \
            list((root / "genios_engine").rglob("*.py")):
        body = path.read_text()
        assert "create table if not exists l1_v2_activation" not in body, path


def test_activation_is_never_a_config_boolean():
    """The rule, asserted where it can actually be broken: no setting whose name says activation
    may appear on Settings. The one that started this — `use_domain_compiler` — is a different
    subsystem's and is left alone; what must never grow is a SECOND one for this lane."""
    from genios_engine.platform.config import Settings
    for name in Settings.model_fields:
        assert "semantic_activ" not in name and "l1_v2" not in name, \
            f"{name} is a global boolean for a per-tenant decision"
