"""Z0 / G-07 · Layer 4 pilot activation — the table, the fail-closed reads, and the request path.

THE DEFECT THIS FILE WAS WRITTEN AGAINST, AND IT IS THE FOURTH TIME. `l1_semantic_activation`
shipped with a read on the sweep path and no writer outside its own unit test.
`l2_v2_activation` landed its routes in the same wave, deliberately, because of that.
`l3_activation` then shipped in Y0 with a reader, a fail-closed gate and an erasure row — and
`activate`/`deactivate` reachable from nothing, so the only way to start a pilot was a hand-written
INSERT, and a pilot begun by SQL has no `enabled_by` anybody trusts and no audit row at all. Doc 07
says not to repeat that a fourth time, so the routes exist in this wave and are pinned here.

PER FEATURE IS THE POINT, and this file pins it. L4's key is (org_id, feature) because doc 07 names
five independently flippable features landing in five different waves — a per-tenant boolean would
turn the narrative on in the same request that wakes the roster, which is the retired global flag
with a nicer name. So: no "all" shorthand on the way in, and `feature` is a REQUIRED parameter on
the way out.

The Postgres cases need GENIOS_TEST_DATABASE_URL, like every other real-DB file in this suite. The
structural cases (routes registered, auth-gated, key validated) do not, and are the ones that would
have caught the defect above.
"""
from __future__ import annotations

import inspect
import os

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsMarker
from sqlalchemy import text

from genios_engine.api import account_routes as ACC
from genios_engine.api import admin_routes as A
from genios_engine.platform import l4_activation as ACT
from genios_engine.platform.auth import AuthCtx, require_admin

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
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})


def _ctx() -> AuthCtx:
    return AuthCtx(org_id="org_genios_internal", actor_id="harsh@genios.ai", source="jwt")


# ── THE SEAM: a request path exists, and it is the admin one ────────────────────────────────

def test_a_request_path_can_switch_a_feature_on_and_off():
    """Read structurally so it cannot be satisfied by a helper a router never reaches."""
    paths = {(r.path, tuple(sorted(r.methods))) for r in A.router.routes}
    assert ("/admin/l4-activation/{target_org}", ("POST",)) in paths, \
        "no request path puts a tenant's feature on the L4 pilot — the only way in is raw SQL"
    assert ("/admin/l4-activation/{target_org}", ("DELETE",)) in paths, \
        "no request path takes a feature off — a cutover you cannot reverse"
    assert ("/admin/l4-activation/{target_org}", ("GET",)) in paths, \
        "no request path answers 'which features is this org running'"
    assert ("/admin/l4-activation", ("GET",)) in paths, \
        "no request path answers 'who is on the pilot'"


def test_the_activation_routes_are_registered_on_the_running_application():
    """A router nobody includes is the same defect one level up. Read off the OpenAPI schema
    because this FastAPI includes routers lazily, so walking `app.routes` finds no paths at all."""
    from genios_engine.main import app
    paths = app.openapi()["paths"]
    assert {"post", "delete", "get"} <= set(paths["/admin/l4-activation/{target_org}"])
    assert "get" in paths["/admin/l4-activation"]


def test_every_activation_route_is_behind_require_admin():
    """A tenant able to switch on their own pilot is a tenant able to change what their engine
    decides. Asserted on the DEPENDENCY, not on a decorator, because that is what actually runs."""
    for fn in (A.list_l4_pilot_activation, A.get_l4_pilot_activation,
               A.activate_l4_pilot, A.deactivate_l4_pilot):
        gates = [p.default.dependency for p in inspect.signature(fn).parameters.values()
                 if isinstance(p.default, DependsMarker)]
        assert require_admin in gates, f"{fn.__name__} is not behind require_admin"


def test_a_scoped_key_is_refused_before_any_database_lookup():
    """A typo must be a 400 naming the legal features, not a row under `bundel` that reads as an
    activated tenant and narrates nothing."""
    with pytest.raises(HTTPException) as caught:
        A._l4_feature("bundel")
    assert caught.value.status_code == 400
    assert "roster_v2" in str(caught.value.detail)
    with pytest.raises(ValueError):
        ACT.require_feature("all")


# ── THE VOCABULARY ──────────────────────────────────────────────────────────────────────────

def test_the_five_features_are_the_plans_five_in_wave_order():
    """Doc 07 names five. Wave order rather than alphabetical, because alphabetical would put
    `bundle` — the narrative — before `ranking_v2`, the formula it narrates."""
    assert ACT.L4_FEATURES == ("roster_v2", "ranking_v2", "bundle", "critique", "brief")
    assert set(ACT.EFFECTS) == set(ACT.L4_FEATURES) == set(ACT.FEATURE_WAVES)
    assert set(ACT.PRECONDITIONS) == set(ACT.L4_FEATURES)
    assert ACT.FEATURE_WAVES["bundle"] == "Z4"


def test_the_wave_order_is_reported_and_not_enforced(engine):
    """Enforcing it would stop an operator switching one thing on in isolation to debug it at 2am;
    saying nothing would let `bundle` reach a tenant whose formula has not been woken. So it is
    said, on the way in — and the switch still happens."""
    assert ACT.missing_preconditions(engine, ORG, "bundle") == ("ranking_v2",)
    ACT.activate(engine, ORG, feature="bundle", by="harsh")
    assert ACT.is_l4_activated(engine, ORG, "bundle") is True
    ACT.activate(engine, ORG, feature="ranking_v2", by="harsh")
    assert ACT.missing_preconditions(engine, ORG, "bundle") == ()
    assert ACT.missing_preconditions(engine, ORG, "roster_v2") == ()


# ── FAIL CLOSED ─────────────────────────────────────────────────────────────────────────────

def test_every_gate_read_answers_not_activated_without_a_database():
    """No engine, an unreadable table, a query that errored — every one answers 'off'. The cost of a
    wrong False is a tenant whose engine behaves exactly as every tenant's does today; the cost of a
    wrong True is a narrative on a tenant nobody chose."""
    assert ACT.is_l4_activated(None, ORG, "bundle") is False
    assert ACT.l4_activated_orgs(None, "bundle") == frozenset()
    assert ACT.activated_features(None, ORG) == frozenset()


class _ExplodingEngine:
    def connect(self):
        raise RuntimeError("connection pool exhausted")


def test_a_broken_connection_is_an_off_switch_not_an_exception():
    """The read is on the hot path of every reasoning run. A raise here would turn a database blip
    into a failed run; an 'on' here would turn it into an unwatched behaviour change."""
    broken = _ExplodingEngine()
    assert ACT.is_l4_activated(broken, ORG, "brief") is False
    assert ACT.l4_activated_orgs(broken, "brief") == frozenset()
    assert ACT.activated_features(broken, ORG) == frozenset()


def test_the_console_reads_do_not_swallow(engine):
    """Deliberately NOT fail-closed: an operator asking 'what is the state of the pilot' must see a
    database error rather than the word 'off'."""
    with pytest.raises(RuntimeError):
        ACT.get_l4_activation(_ExplodingEngine(), ORG, "bundle")
    with pytest.raises(RuntimeError):
        ACT.list_l4_activations(_ExplodingEngine())


# ── THE WRITERS ─────────────────────────────────────────────────────────────────────────────

def test_turning_the_roster_on_does_not_turn_the_narrative_on(engine):
    """The whole reason the key is (org, feature)."""
    ACT.activate(engine, ORG, feature="roster_v2", by="harsh")
    assert ACT.is_l4_activated(engine, ORG, "roster_v2") is True
    assert ACT.is_l4_activated(engine, ORG, "bundle") is False
    assert ACT.activated_features(engine, ORG) == frozenset({"roster_v2"})


def test_activating_twice_does_not_re_date_the_pilot(engine):
    """'Since when has this tenant been on the pilot' is what the seven-day K7 report is read
    against; an upsert that refreshed `enabled_at` would answer with the date of the last click."""
    first = ACT.activate(engine, ORG, feature="ranking_v2", by="harsh", notes="design partner")
    again = ACT.activate(engine, ORG, feature="ranking_v2", by="someone_else", notes="oops")
    assert again.enabled_at == first.enabled_at
    assert again.enabled_by == "harsh"
    assert again.notes == "design partner"


def test_a_note_fills_in_a_blank_reason_and_never_overwrites_one(engine):
    ACT.activate(engine, ORG, feature="brief", by="harsh")
    filled = ACT.activate(engine, ORG, feature="brief", by="harsh", notes="why this tenant")
    assert filled.notes == "why this tenant"


def test_a_reversal_stamps_the_row_rather_than_deleting_it(engine):
    """K7 reads a seven-day window and has to be able to say 'the narrative was switched off on day
    four', which a missing row cannot say. Every read filters the stamped rows out, so the engine
    sees exactly what a delete would have left it."""
    ACT.activate(engine, ORG, feature="bundle", by="harsh")
    assert ACT.deactivate(engine, ORG, feature="bundle", by="harsh") is True
    record = ACT.get_l4_activation(engine, ORG, "bundle")
    assert record is not None and record.live is False and record.disabled_by == "harsh"
    assert ACT.is_l4_activated(engine, ORG, "bundle") is False
    assert ACT.activated_features(engine, ORG) == frozenset()
    with engine.connect() as c:
        assert c.execute(text("select count(*) from l4_activation where org_id=:o and "
                              "feature='bundle'"), {"o": ORG}).scalar() == 1


def test_re_activating_a_stamped_row_starts_a_new_window(engine):
    """The opposite case to the idempotent one: a new pilot period with a new decision behind it,
    and dating it from the first would hand the report a window containing days it was off."""
    first = ACT.activate(engine, ORG, feature="critique", by="harsh")
    ACT.deactivate(engine, ORG, feature="critique", by="harsh")
    revived = ACT.activate(engine, ORG, feature="critique", by="pratap", notes="round two")
    assert revived.live is True and revived.enabled_by == "pratap"
    assert revived.enabled_at > first.enabled_at
    assert revived.notes == "round two"


def test_taking_an_already_off_feature_off_is_not_an_error(engine):
    assert ACT.deactivate(engine, ORG, feature="brief") is False


def test_the_reads_report_which_features_are_live(engine):
    ACT.activate(engine, ORG, feature="roster_v2", by="harsh")
    ACT.activate(engine, ORG, feature="ranking_v2", by="harsh")
    ACT.deactivate(engine, ORG, feature="ranking_v2", by="harsh")
    assert ACT.l4_activated_orgs(engine, "roster_v2") >= {ORG}
    assert ORG not in ACT.l4_activated_orgs(engine, "ranking_v2")
    live = {(r.org_id, r.feature) for r in ACT.list_l4_activations(engine)}
    everything = {(r.org_id, r.feature) for r in ACT.list_l4_activations(engine,
                                                                        include_disabled=True)}
    assert (ORG, "ranking_v2") not in live and (ORG, "ranking_v2") in everything
    record = ACT.get_l4_activation(engine, ORG, "roster_v2").as_record()
    assert record["live"] is True and record["wave"] == "Z1" and record["effect"]


# ── THE ROUTES, END TO END ──────────────────────────────────────────────────────────────────

def test_the_post_body_has_no_feature_default_and_refuses_an_unknown_one():
    assert A.L4PilotActivation.model_fields["feature"].is_required(), \
        "a defaulted feature lets an operator switch on the one they were not thinking about"
    with pytest.raises(HTTPException):
        A.activate_l4_pilot(ORG, A.L4PilotActivation(feature="everything"), ctx=_ctx())


def test_the_reversal_requires_the_feature_it_is_ending(engine):
    """`feature` is a REQUIRED query parameter with no default: the widest reading here would
    silently end four other features' pilots."""
    from pydantic_core import PydanticUndefined
    marker = inspect.signature(A.deactivate_l4_pilot).parameters["feature"].default
    # `Query(...)` normalises Ellipsis to PydanticUndefined, so "required" is the absence of a
    # value rather than a sentinel one — assert on that, not on a spelling.
    assert getattr(marker, "default", marker) in (..., PydanticUndefined), \
        "feature defaults on the reversal — one DELETE would end every feature's pilot"
    # And the same fact through the schema a caller actually meets.
    from genios_engine.main import app
    params = app.openapi()["paths"]["/admin/l4-activation/{target_org}"]["delete"]["parameters"]
    feature = next(p for p in params if p["name"] == "feature")
    assert feature["required"] is True


def test_a_typod_tenant_is_a_404_not_a_500(engine):
    """Without the check the org FK raises a 500, and an operator who mistypes a pilot tenant should
    be told which word was wrong."""
    with pytest.raises(HTTPException) as caught:
        A.activate_l4_pilot("org_does_not_exist", A.L4PilotActivation(feature="bundle"),
                            ctx=_ctx())
    assert caught.value.status_code == 404


def test_the_switch_on_and_the_switch_off_are_both_audited(engine, monkeypatch):
    """A pilot begun by SQL has no `enabled_by` anybody trusts and no audit row at all — the whole
    reason this route exists rather than a psql session."""
    seen: list[dict] = []
    import genios_engine.platform.audit as audit_mod
    monkeypatch.setattr(audit_mod, "record",
                        lambda *a, **k: seen.append({"args": a, "kw": k}))
    body = A.L4PilotActivation(feature="bundle", notes="design partner")
    on = A.activate_l4_pilot(ORG, body, ctx=_ctx())
    off = A.deactivate_l4_pilot(ORG, feature="bundle", ctx=_ctx())
    assert on["switched_on"] == "bundle" and off["switched_off"] == "bundle"
    assert on["missing_preconditions"] == ["ranking_v2"], \
        "the wave order must be reported on the way in, not discovered at the gate"
    assert len(seen) == 2
    assert all(item["kw"]["metadata"]["field"] == "l4_activation" for item in seen)
    assert [item["kw"]["metadata"]["value"] for item in seen] == [True, False]


def test_the_reads_answer_which_features_and_what_they_turned_on(engine):
    A.activate_l4_pilot(ORG, A.L4PilotActivation(feature="roster_v2"), ctx=_ctx())
    one = A.get_l4_pilot_activation(ORG, _ctx=_ctx())
    assert one["in_pilot"] is True and one["live_features"] == ["roster_v2"]
    assert one["missing_preconditions"] == {"roster_v2": []}
    everyone = A.list_l4_pilot_activation(_ctx=_ctx())
    assert "roster_v2" in everyone["live_features"] and everyone["live"] >= 1
    assert set(everyone["effects"]) == set(ACT.L4_FEATURES)


# ── ERASURE ─────────────────────────────────────────────────────────────────────────────────

def test_the_table_is_named_in_the_erasure_list():
    """Three waves in Layer 2 forgot an equivalent. The list runs with no try/except by design, so a
    name missing from it leaks silently rather than failing."""
    assert "l4_activation" in ACC._ORG_SCOPED_TABLES


def test_reset_actually_erases_the_row_through_the_wipe_that_runs(engine):
    """DRIVEN THROUGH `_wipe`, not asserted against the constant: the list being right and the loop
    reaching the table are two different facts, and only the second one is the erasure.

    It names a person (`enabled_by`, `disabled_by`) and carries free text about the tenant, so it is
    theirs to have erased — and removing it returns them to the state every org that never joined
    the pilot is in, which is where every tenant sits today.
    """
    ACT.activate(engine, ORG, feature="bundle", by="harsh", notes="design partner")
    with engine.begin() as c:
        wiped = ACC._wipe(c, ORG)
        assert wiped["l4_activation"] == 1
        c.rollback()
    # The rollback above proves the delete ran inside the transaction; re-read outside it.
    assert ACT.is_l4_activated(engine, ORG, "bundle") is True
