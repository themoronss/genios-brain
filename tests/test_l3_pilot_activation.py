"""J5 · Layer 3 pilot activation — the request path that can actually flip a domain on.

THE DEFECT THIS FILE WAS WRITTEN AGAINST, and it is the third time the same one has appeared.
`l1_semantic_activation` shipped with a read on the sweep path and no writer outside its own unit
test. `l2_v2_activation` landed with its routes in the same wave, deliberately, because of that.
`l3_activation` then shipped in wave Y0 with a reader, a fail-closed gate, an erasure row — and
`activate`/`deactivate` reachable from nothing, which the J0-J4 gate reported as "correct for this
wave, and BLOCKING for J5: until then the only way to start a pilot is a hand-written INSERT."

A pilot begun by SQL has no `enabled_by` anybody trusts and no audit row at all, and doc 00's
Law 5 exists because of the standing counterexample — `use_domain_compiler=False`, set in no
environment, 152 capabilities dark.

PER DOMAIN IS THE POINT, and this file pins it. L3's key is (org_id, domain) because the corpus is
three authored domains and doc 00's V1 scope rule is "Admin domain first ... Sales and CS corpora
stay compiled and stamped but activate later". A per-tenant boolean would turn all three on in one
request, which is the retired global flag with a nicer name. So: no "all" shorthand on the way in,
and `domain` is a REQUIRED parameter on the way out — a reversal that defaulted to "everything"
would silently end two other domains' seven-day windows.

THE ORDERING THIS ROUTE MUST NOT VIOLATE. Doc 06: "the one ordering that must not be violated is
Y1 before Y5", because activation without the typed consumers produces the fake success the
adapter's own docstring warns about. Y1 landed and J1 passed before this file was written.

The Postgres cases need GENIOS_TEST_DATABASE_URL, like every other real-DB file in this suite.
"""
from __future__ import annotations

import inspect
import os

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsMarker
from sqlalchemy import text

from genios_engine.api import admin_routes as A
from genios_engine.platform import l3_activation as ACT
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
        c.execute(text("delete from l3_activation where org_id = :o"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from l3_activation where org_id = :o"), {"o": ORG})


def _ctx() -> AuthCtx:
    return AuthCtx(org_id="org_genios_internal", actor_id="harsh@genios.ai", source="jwt")


# ── THE SEAM: a request path exists, and it is the admin one ────────────────────────────────

def test_a_request_path_can_switch_a_domain_on_and_off():
    """Read structurally so it cannot be satisfied by a helper a router never reaches."""
    paths = {(r.path, tuple(sorted(r.methods))) for r in A.router.routes}
    assert ("/admin/l3-activation/{target_org}", ("POST",)) in paths, \
        "no request path puts a tenant's domain on the L3 pilot — the only way in is raw SQL"
    assert ("/admin/l3-activation/{target_org}", ("DELETE",)) in paths, \
        "no request path takes a domain off — a cutover you cannot reverse"
    assert ("/admin/l3-activation/{target_org}", ("GET",)) in paths, \
        "no request path answers 'which domains is this org compiling'"
    assert ("/admin/l3-activation", ("GET",)) in paths, \
        "no request path answers 'who is on the pilot'"


def test_the_activation_routes_are_registered_on_the_running_application():
    """A router nobody includes is the same defect one level up. Read off the OpenAPI schema
    because this FastAPI includes routers lazily, so walking `app.routes` finds no paths at all."""
    from genios_engine.main import app
    paths = app.openapi()["paths"]
    assert {"post", "delete", "get"} <= set(paths["/admin/l3-activation/{target_org}"])
    assert "get" in paths["/admin/l3-activation"]


def test_every_activation_route_is_behind_require_admin():
    """A tenant must not be able to put ITSELF on the pilot. `require_admin` is the only boundary
    in the engine that means 'is this us?', and an L3 activation changes which corpus compiles
    against a customer's data."""
    for name in ("activate_l3_pilot", "deactivate_l3_pilot", "get_l3_pilot_activation",
                 "list_l3_pilot_activation"):
        endpoint = getattr(A, name, None)
        assert endpoint is not None, f"admin_routes has no {name} — that side is unwired"
        assert any(isinstance(p.default, DependsMarker) and p.default.dependency is require_admin
                   for p in inspect.signature(endpoint).parameters.values()), \
            f"{name} is not behind require_admin"


def test_a_scoped_key_is_refused_before_any_database_lookup():
    """A tenant key with read scopes is not us, and the refusal happens before any lookup."""
    with pytest.raises(HTTPException) as exc:
        require_admin(AuthCtx(org_id=ORG, scopes=["read:context"], source="api_key"))
    assert exc.value.status_code == 403


# ── PER DOMAIN, not per tenant ───────────────────────────────────────────────────────────────

def test_turning_admin_on_does_not_turn_sales_on(engine):
    """The whole reason the key is (org, domain). Doc 00: Admin first; Sales and CS stay compiled
    and stamped but activate later. A per-tenant boolean would ship 1,394 files in one request."""
    A.activate_l3_pilot(ORG, A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN, notes="pilot"), ctx=_ctx())

    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_ADMIN) is True
    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_SALES) is False
    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_CUSTOMER_SUPPORT) is False
    assert ACT.activated_domains(engine, ORG) == frozenset({ACT.DOMAIN_ADMIN})


def test_the_post_body_has_no_domain_default_and_refuses_an_unknown_one():
    """No `all` shorthand and no default: an operator who wants three domains says so three
    times. An unknown domain is a 400 naming the legal values, not a 422 to decode."""
    with pytest.raises(HTTPException) as exc:
        A.activate_l3_pilot(ORG, A.L3PilotActivation(domain="marketing"), ctx=_ctx())
    assert exc.value.status_code == 400
    assert "marketing" in str(exc.value.detail) or "domain" in str(exc.value.detail).lower()
    assert "domain" in A.L3PilotActivation.model_fields
    assert A.L3PilotActivation.model_fields["domain"].is_required(), \
        "a defaulted domain lets an operator activate the one they were not thinking about"


def test_the_reversal_requires_the_domain_it_is_ending(engine):
    """Everywhere else in admin_routes a reversal defaults to the widest reading, because taking
    something off is the safe direction. Not here: the widest reading would silently end two other
    domains' seven-day windows, and a pilot ended by accident is a window nobody can read."""
    from pydantic_core import PydanticUndefined
    marker = inspect.signature(A.deactivate_l3_pilot).parameters["domain"].default
    # `Query(...)` normalises Ellipsis to PydanticUndefined, so "required" is the absence of a
    # value rather than a sentinel one — assert on that, not on a spelling.
    assert getattr(marker, "default", marker) in (..., PydanticUndefined), \
        "domain defaults on the reversal — one DELETE would end every domain's pilot"
    # And the same fact through the schema a caller actually meets.
    from genios_engine.main import app
    params = app.openapi()["paths"]["/admin/l3-activation/{target_org}"]["delete"]["parameters"]
    domain = next(p for p in params if p["name"] == "domain")
    assert domain["required"] is True


# ── IDEMPOTENCE, REVERSAL, AUDIT ─────────────────────────────────────────────────────────────

def test_activating_twice_does_not_re_date_the_pilot(engine):
    """The window is the product here: `scripts/l3_pilot_report.py --days 7` is measured from
    `enabled_at`, so a retry after a dropped connection must not move day one."""
    first = A.activate_l3_pilot(ORG, A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN), ctx=_ctx())
    again = A.activate_l3_pilot(ORG, A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN), ctx=_ctx())
    assert first["activation"]["enabled_at"] == again["activation"]["enabled_at"]


def test_a_reversal_stamps_the_row_rather_than_deleting_it(engine):
    """A seven-day window that silently contains a mid-week switch-off is a diff nobody can read,
    so the record survives the reversal — the same rule L1's and L2's tables follow."""
    A.activate_l3_pilot(ORG, A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN), ctx=_ctx())
    out = A.deactivate_l3_pilot(ORG, domain=ACT.DOMAIN_ADMIN, ctx=_ctx())

    assert out["switched_off"] == ACT.DOMAIN_ADMIN
    assert out["activation"] is not None, "the row was deleted; the window is now unreadable"
    assert out["activation"]["disabled_at"] is not None
    assert ACT.is_l3_activated(engine, ORG, ACT.DOMAIN_ADMIN) is False
    with engine.connect() as c:
        assert c.execute(text("select count(*) from l3_activation where org_id=:o and domain=:d"),
                         {"o": ORG, "d": ACT.DOMAIN_ADMIN}).scalar() == 1


def test_taking_an_already_off_domain_off_is_not_an_error(engine):
    """The caller's intent — 'this tenant must not be compiling Admin' — is satisfied either way,
    and a 404 would make a retry after a dropped connection look like a failure."""
    out = A.deactivate_l3_pilot(ORG, domain=ACT.DOMAIN_ADMIN, ctx=_ctx())
    assert out["switched_off"] is None


def test_a_typod_tenant_is_a_404_not_a_500(engine):
    """Without the existence check the org FK raises a 500, and an operator who mistypes a pilot
    tenant should be told which word was wrong."""
    with pytest.raises(HTTPException) as exc:
        A.activate_l3_pilot("org_does_not_exist", A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN),
                            ctx=_ctx())
    assert exc.value.status_code == 404


def test_the_switch_on_and_the_switch_off_are_both_audited(engine, monkeypatch):
    """Who turned this on, for which domain, and why. A pilot is a decision about one customer's
    compiled output, and `enabled_by` from a hand-written INSERT is nobody.

    The call is CAPTURED rather than written: the admin acting here is `org_genios_internal`,
    which is not a seeded tenant, so the audit table's own org FK would refuse the row. That is a
    fact about the fixture's operator, not about whether the route audits."""
    calls: list[dict] = []
    monkeypatch.setattr("genios_engine.platform.audit.record",
                        lambda *a, **k: calls.append({"args": a, "kw": k}))

    A.activate_l3_pilot(ORG, A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN, notes="week 1"),
                        ctx=_ctx())
    assert calls, "an activation left no audit call"
    meta = calls[-1]["kw"]["metadata"]
    assert meta["field"] == "l3_activation"
    assert meta["domain"] == ACT.DOMAIN_ADMIN
    assert meta["value"] is True and meta["notes"] == "week 1"
    assert calls[-1]["kw"]["target_id"] == ORG

    A.deactivate_l3_pilot(ORG, domain=ACT.DOMAIN_ADMIN, ctx=_ctx())
    off = calls[-1]["kw"]["metadata"]
    assert off["field"] == "l3_activation" and off["value"] is False
    assert off["domain"] == ACT.DOMAIN_ADMIN, "a reversal that does not name its domain"


def test_the_reads_report_which_domains_are_live(engine):
    """'Is this org on the L3 pilot' has no yes/no answer once the key is (org, domain) — a tenant
    can be compiling Admin and not Sales, and an operator told only `activated: true` assumes
    both."""
    A.activate_l3_pilot(ORG, A.L3PilotActivation(domain=ACT.DOMAIN_ADMIN), ctx=_ctx())

    one = A.get_l3_pilot_activation(ORG, _ctx=_ctx())
    assert one["in_pilot"] is True
    assert one["live_domains"] == [ACT.DOMAIN_ADMIN]

    listed = A.list_l3_pilot_activation(include_disabled=False, _ctx=_ctx())
    assert ACT.DOMAIN_ADMIN in listed["live_domains"]
    assert any(r["org_id"] == ORG for r in listed["activations"])

    # A switched-off domain disappears from the live read and returns under include_disabled —
    # which is how the seven-day report knows the window had a hole in it.
    A.deactivate_l3_pilot(ORG, domain=ACT.DOMAIN_ADMIN, ctx=_ctx())
    assert A.get_l3_pilot_activation(ORG, _ctx=_ctx())["live_domains"] == []
    with_off = A.list_l3_pilot_activation(include_disabled=True, _ctx=_ctx())
    assert any(r["org_id"] == ORG for r in with_off["activations"])
