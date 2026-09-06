"""H8 · Layer 2 v2 pilot activation — the table, the two switches, and the request path that can
actually flip them.

THE DEFECT THIS FILE WAS WRITTEN AGAINST, ONE LAYER UP FROM ITS TWIN. `l1_semantic_activation`
shipped with a read on the sweep path and no writer outside its own unit test, so the only way to
start a pilot was an operator typing INSERT against the production tenant database — and doc 09's
activation rule exists precisely because a switch nothing can flip is a switch that is always off
(`use_domain_compiler=False`, set in no environment, 152 capabilities dark). `l2_v2_activation`
lands in the same wave as the routes that move it, so it cannot repeat that.

THE TWO SWITCHES ARE NOT SYMMETRIC AND THIS FILE PINS THE ASYMMETRY. `patterns` is a real gate on
`context/runner.process_pending`'s shadow pass; `analytic` is a declaration, because the analytic
stratum already runs unconditionally for every tenant and gating it now would switch it OFF for
everyone already on it — a founder-visible regression introduced by an activation table, against a
gate whose last row is "founder-visible regressions: 0". A switch that gates nothing is a
dangerous thing to ship silently, so `EFFECTS` states it, the route returns it, and
`test_the_analytic_switch_is_honest_about_gating_nothing` asserts that no code reads it as a gate.

The behaviour the `patterns` switch controls is proven through the REAL drain in
`tests/context/test_l2_shadow_diff.py`; this file owns the switch, its idempotency and its
reversal.

The Postgres cases need GENIOS_TEST_DATABASE_URL, like every other real-DB file in this suite.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsMarker
from sqlalchemy import text

from genios_engine.api import admin_routes as A
from genios_engine.platform import l2_activation as ACT
from genios_engine.platform.auth import AuthCtx, require_admin

NOW = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK
ENGINE_ROOT = Path(__file__).resolve().parents[1] / "genios_engine"


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
        c.execute(text("delete from l2_v2_activation where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l2_v2_activation where org_id = :o"), {"o": ORG})


def _ctx() -> AuthCtx:
    return AuthCtx(org_id="org_genios_internal", actor_id="harsh@genios.ai", source="jwt")


# ── THE SEAM: a request path exists, and it is the admin one ────────────────────────────────

def test_a_request_path_can_switch_the_pilot_on_and_off():
    """Read structurally so it cannot be satisfied by a helper a router never reaches."""
    paths = {(r.path, tuple(sorted(r.methods))) for r in A.router.routes}
    assert ("/admin/l2-activation/{target_org}", ("POST",)) in paths, \
        "no request path puts a tenant on the L2 v2 pilot"
    assert ("/admin/l2-activation/{target_org}", ("DELETE",)) in paths, \
        "no request path takes a tenant off — a cutover you cannot reverse"
    assert ("/admin/l2-activation/{target_org}", ("GET",)) in paths, \
        "no request path answers 'is this org activated, and what did that turn on'"
    assert ("/admin/l2-activation", ("GET",)) in paths, \
        "no request path answers 'who is on the pilot'"


def test_the_activation_routes_are_registered_on_the_running_application():
    """A router nobody includes is the same defect one level up. Read off the OpenAPI schema
    because this FastAPI includes routers lazily, so walking `app.routes` finds no paths at all."""
    from genios_engine.main import app
    paths = app.openapi()["paths"]
    assert {"post", "delete", "get"} <= set(paths["/admin/l2-activation/{target_org}"])
    assert "get" in paths["/admin/l2-activation"]


@pytest.mark.parametrize("name", ["activate_l2_pilot", "deactivate_l2_pilot",
                                  "list_l2_pilot_activation", "get_l2_pilot_activation"])
def test_only_geniOS_staff_may_move_a_tenant_onto_the_pilot(name):
    """Activation is not a tenant preference: `patterns` turns on a graph read per sweep that
    nobody has budgeted for this tenant. A customer-facing route here would let a tenant switch on
    their own unbudgeted work."""
    import inspect
    endpoint = getattr(A, name, None)
    assert endpoint is not None, f"admin_routes has no {name} — the write side is unwired"
    assert any(isinstance(p.default, DependsMarker) and p.default.dependency is require_admin
               for p in inspect.signature(endpoint).parameters.values())


def test_a_scoped_key_is_refused_before_any_database_lookup():
    with pytest.raises(HTTPException) as exc:
        require_admin(AuthCtx(org_id=ORG, scopes=["read:context"], source="api_key"))
    assert exc.value.status_code == 403


# ── the plan's rule: per tenant, in a table, never a config boolean ─────────────────────────

def test_no_global_boolean_was_added_to_config():
    """Doc 09: *"No global boolean in platform/config.py. use_domain_compiler=False has been set
    in no environment since it was written and has left 152 capabilities dark. Do not build a
    second one."*"""
    config = (ENGINE_ROOT / "platform" / "config.py").read_text()
    for name in ("l2_v2", "l2_pattern", "patterns_enabled", "analytic_enabled"):
        assert name not in config, f"{name} is a global switch; activation is per tenant"


def test_the_switch_names_are_validated_and_never_interpolated_from_caller_text():
    """Both writers build a column name from the switch. `require_switch` is the only place a name
    becomes SQL, so a typo is a refusal rather than an update of zero columns reported as success
    — and so a caller cannot spell a column of their own."""
    assert ACT.require_switch("patterns") == "patterns"
    with pytest.raises(ValueError):
        ACT.require_switch("analytics")          # the plural typo, which is the likely one
    with pytest.raises(ValueError):
        ACT.require_switch("patterns_enabled_at = null, enabled_by")


def test_the_analytic_switch_is_honest_about_gating_nothing():
    """The asymmetry, stated in code and asserted here.

    `patterns_enabled_at` gates the runner's shadow pass. `analytic_enabled_at` gates nothing —
    the analytic stratum runs for every tenant — and the danger of shipping a switch that gates
    nothing is that somebody later believes it does. So: it has no gate reader in the tree, and
    the sentence saying so travels in every API response.
    """
    readers = [path for path in ENGINE_ROOT.rglob("*.py")
               if "analytic_enabled_at" in path.read_text()
               and path.name not in ("l2_activation.py",)]
    assert readers == [], f"{readers} reads the analytic switch as if it gated something"
    assert "declaration only" in ACT.EFFECTS[ACT.SWITCH_ANALYTIC]
    assert "context/runner.process_pending" in ACT.EFFECTS[ACT.SWITCH_PATTERNS]


def test_the_gate_reader_is_the_one_the_runner_calls():
    """The other half: the `patterns` switch must have exactly one gate reader, and it must be on
    the drain. A switch read nowhere is the defect; a switch read in two places is the next one."""
    runner = (ENGINE_ROOT / "context" / "runner.py").read_text()
    assert "is_patterns_activated" in runner
    assert "evaluate_org" in runner


# ── the table, through the route ────────────────────────────────────────────────────────────

def test_the_route_turns_one_switch_on_for_exactly_one_tenant(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    assert ACT.is_patterns_activated(engine, ORG) is False, "precondition: nobody is on the pilot"

    body = A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="patterns", notes="design partner"),
                               _ctx())
    assert body["switched_on"] == ["patterns"]
    switches = body["activation"]["switches"]
    assert switches["patterns"]["live"] is True
    assert switches["analytic"]["live"] is False, "one switch at a time, as the plan asks"
    assert body["activation"]["enabled_by"] == "harsh@genios.ai"
    assert body["activation"]["notes"] == "design partner"

    # the point of the whole exercise: the thing that decides whether the drain runs the pass
    assert ACT.is_patterns_activated(engine, ORG) is True
    assert ORG in ACT.activated_orgs(engine, ACT.SWITCH_PATTERNS)
    assert ORG not in ACT.activated_orgs(engine, ACT.SWITCH_ANALYTIC)


def test_both_switches_can_be_thrown_in_one_request(engine, monkeypatch):
    """A tenant joining the pilot usually joins it for both, and making that two requests invites
    a half-activated tenant nobody notices."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    body = A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both", notes="7-day pilot"),
                               _ctx())
    assert body["switched_on"] == ["analytic", "patterns"]
    assert all(body["activation"]["switches"][s]["live"] for s in ACT.SWITCHES)
    assert set(body["effects"]) == set(ACT.SWITCHES)


def test_an_unknown_switch_is_a_400_naming_the_legal_values(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    with pytest.raises(HTTPException) as exc:
        A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="everything"), _ctx())
    assert exc.value.status_code == 400 and "analytic" in str(exc.value.detail)


def test_a_typo_in_the_org_id_is_a_404_not_a_stack_trace(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    with pytest.raises(HTTPException) as exc:
        A.activate_l2_pilot("org_does_not_exist", A.L2PilotActivation(switch="both"), _ctx())
    assert exc.value.status_code == 404


# ── idempotency, and the thing it is really about ───────────────────────────────────────────

def test_switching_on_twice_does_not_restart_the_pilot(engine, monkeypatch):
    """A double-click must not move the start date: "since when has this tenant been in the
    pilot" is the question the shadow diff's window is read against."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    first = A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both", notes="first"), _ctx())
    second = A.activate_l2_pilot(
        ORG, A.L2PilotActivation(switch="both", notes="second"),
        AuthCtx(org_id="org_genios_internal", actor_id="someone.else@genios.ai", source="jwt"))

    for switch in ACT.SWITCHES:
        assert (second["activation"]["switches"][switch]["enabled_at"]
                == first["activation"]["switches"][switch]["enabled_at"])
    assert second["activation"]["enabled_by"] == "harsh@genios.ai"
    assert second["activation"]["notes"] == "first", \
        "a re-click must not silently rewrite why the org was chosen"


def test_activating_starts_no_backfill_of_its_own(engine, monkeypatch):
    """THE IDEMPOTENCY THAT COSTS MONEY. `sampler.backfill_history_for_drain` already runs the
    once-per-tenant 18-month reconstruction, guarded on history EXISTENCE rather than on a marker.
    Activation must cooperate with that, not duplicate it — so it starts no work at all, and
    activating twice writes exactly one row and reads exactly one table.
    """
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    def _count(table: str) -> int:
        with engine.connect() as c:
            return c.execute(text(f"select count(*) from {table} where org_id = :o"),
                             {"o": ORG}).scalar() or 0

    before = {t: _count(t) for t in ("metric_history", "graph_facts", "pattern_fires",
                                     "pattern_runs", "context_situations")}
    A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both"), _ctx())
    A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both"), _ctx())
    assert {t: _count(t) for t in before} == before, \
        "activation wrote something outside its own table"
    assert _count("l2_v2_activation") == 1, "two activations, one row"

    # And it CANNOT start one: read off the module's own imports rather than its prose, because
    # the docstring says the word "backfill" on purpose. A module that imports nothing from
    # `genios_engine.context` cannot reach `sampler.backfill_history_for_drain`, the trend pass or
    # the cohort pass, whatever a future edit adds to its body.
    import ast
    tree = ast.parse((ENGINE_ROOT / "platform" / "l2_activation.py").read_text())
    imported = {node.module for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module}
    assert not any(name.startswith("genios_engine.context") for name in imported), \
        f"the activation module reaches into Layer 2's passes: {sorted(imported)}"


# ── reversal, and the window it has to stay readable in ─────────────────────────────────────

def test_switching_off_keeps_the_row_so_the_window_can_say_when(engine, monkeypatch):
    """H8 compares seven days; a window containing a mid-week switch-off has to be readable as
    four days of shadow running, not seven. A DELETE cannot say that."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both", notes="pilot"), _ctx())
    off = A.deactivate_l2_pilot(ORG, switch="patterns", ctx=_ctx())

    assert off["switched_off"] == ["patterns"]
    assert off["activation"]["switches"]["patterns"]["live"] is False
    assert off["activation"]["switches"]["patterns"]["disabled_at"] is not None
    assert off["activation"]["switches"]["analytic"]["live"] is True, "one switch, not both"
    # the drain sees exactly what a DELETE would have left it...
    assert ACT.is_patterns_activated(engine, ORG) is False
    assert ORG not in ACT.activated_orgs(engine, ACT.SWITCH_PATTERNS)
    # ...but the history survives, and so does why the tenant was chosen
    record = ACT.get_l2_activation(engine, ORG)
    assert record is not None and record.patterns_live is False and record.notes == "pilot"
    assert record.patterns_enabled_at is not None, "when it started is still readable"


def test_switching_off_a_tenant_that_is_already_off_is_not_an_error(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)
    assert A.deactivate_l2_pilot(ORG, switch="both", ctx=_ctx())["switched_off"] == []


def test_reviving_a_switched_off_tenant_starts_a_NEW_pilot_period(engine):
    """The opposite case to the double-click, and it must not be answered the same way: dating a
    second period from the first would hand the shadow diff a window containing days the pass did
    not run at all."""
    first = ACT.activate(engine, ORG, switch=ACT.SWITCH_PATTERNS, by="harsh@genios.ai",
                         notes="round one", at=NOW - timedelta(days=30))
    ACT.deactivate(engine, ORG, switch=ACT.SWITCH_PATTERNS, at=NOW - timedelta(days=20))
    again = ACT.activate(engine, ORG, switch=ACT.SWITCH_PATTERNS, by="pratap@genios.ai", at=NOW)

    assert again.patterns_enabled_at != first.patterns_enabled_at
    assert again.patterns_enabled_at == NOW
    assert again.patterns_live is True and again.patterns_disabled_at is None


# ── the operator's reads ────────────────────────────────────────────────────────────────────

def test_the_list_route_separates_the_live_from_the_switched_off(engine, monkeypatch):
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both", notes="pilot"), _ctx())
    live = A.list_l2_pilot_activation(False, _ctx())
    assert [r["org_id"] for r in live["activations"]] == [ORG]
    assert live["analytic_live"] == live["patterns_live"] == 1

    A.deactivate_l2_pilot(ORG, switch="both", ctx=_ctx())
    assert A.list_l2_pilot_activation(False, _ctx())["activations"] == []
    assert [r["org_id"] for r in
            A.list_l2_pilot_activation(True, _ctx())["activations"]] == [ORG]


def test_the_single_org_read_says_what_activation_turned_on(engine, monkeypatch):
    """An operator who can see a switch is live and cannot see what it turned on will assume it
    turned on everything — and one of these two switches turns on nothing."""
    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)

    absent = A.get_l2_pilot_activation(ORG, _ctx())
    assert absent["in_pilot"] is False and absent["activation"] is None
    assert set(absent["effects"]) == set(ACT.SWITCHES), "the effects are readable before you ask"

    A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both"), _ctx())
    body = A.get_l2_pilot_activation(ORG, _ctx())
    assert body["in_pilot"] is True
    for switch in ACT.SWITCHES:
        assert body["activation"]["switches"][switch]["effect"] == ACT.EFFECTS[switch]


def test_an_unreadable_switch_is_an_OFF_switch_for_the_drain_and_an_ERROR_for_a_human(engine):
    """The two reads have opposite failure modes on purpose. The drain's must fail closed — a
    wrong `True` is an unbudgeted graph read on a tenant nobody chose. The console's must not —
    an operator asking "what is the state of the pilot" has to see the database error rather than
    the word "off"."""
    class _Broken:
        def connect(self):
            raise RuntimeError("no route to host")

    assert ACT.is_patterns_activated(_Broken(), ORG) is False
    assert ACT.activated_orgs(_Broken(), ACT.SWITCH_PATTERNS) == frozenset()
    with pytest.raises(RuntimeError):
        ACT.get_l2_activation(_Broken(), ORG)


def test_the_switch_leaves_with_the_tenant(engine, monkeypatch):
    """It names a person and carries free text about the customer, so it is theirs to have erased —
    and removing it returns them to the state every org that never joined the pilot is in."""
    from genios_engine.api import account_routes
    assert "l2_v2_activation" in account_routes._ORG_SCOPED_TABLES

    monkeypatch.setattr(A, "_graph", type("G", (), {"engine": engine})())
    monkeypatch.setattr("genios_engine.platform.audit.record", lambda *a, **k: None)
    A.activate_l2_pilot(ORG, A.L2PilotActivation(switch="both"), _ctx())
    with engine.begin() as c:
        c.execute(text("delete from l2_v2_activation where org_id = :o"), {"o": ORG})
    assert ACT.is_patterns_activated(engine, ORG) is False
