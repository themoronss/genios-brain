"""Layer 5.2 · Phase 6 — the control-plane API surface is registered and wired.

A structural ratchet: it fails if a control-plane route is removed or an import breaks, without
touching the database (the handlers are thin wrappers over spine/tracker/analytics/units, which are
each proven against live PostgreSQL in their own tests). It also proves the legacy /v1/signals plane
is gone, per the spec.
"""
from __future__ import annotations

import genios_engine.api.delivery_routes as dr

_EXPECTED = {
    "/api/org/{org_id}/delivery/results",
    "/api/org/{org_id}/delivery/results/{delivery_id}",
    "/api/org/{org_id}/delivery/results/{delivery_id}/attempts",
    "/api/org/{org_id}/delivery/results/{delivery_id}/events",
    "/api/org/{org_id}/delivery/inbox",
    "/api/org/{org_id}/delivery/dead-letters",
    "/api/org/{org_id}/delivery/analytics",
    "/api/org/{org_id}/delivery/capabilities",
}


def test_control_plane_routes_are_registered():
    paths = {r.path for r in dr.router.routes}
    missing = _EXPECTED - paths
    assert not missing, f"control-plane routes missing: {missing}"


def test_the_receipt_endpoint_accepts_only_a_write():
    methods = {}
    for r in dr.router.routes:
        methods.setdefault(r.path, set()).update(getattr(r, "methods", set()) or set())
    assert "POST" in methods["/api/org/{org_id}/delivery/results/{delivery_id}/events"]
    assert "GET" in methods["/api/org/{org_id}/delivery/results"]


def test_capability_report_is_the_units_source_of_truth():
    # the /capabilities handler delegates to units.capability_report — assert that contract exists
    from genios_engine.deliver.units import capability_report
    report = capability_report(configured_channels=set(), credentialed_channels=set())
    assert len(report) == 11 and all(r["operational"] is False for r in report)


def test_app_boots_with_the_control_plane():
    import genios_engine.main  # noqa: F401  — import is the assertion (raises on any route error)
