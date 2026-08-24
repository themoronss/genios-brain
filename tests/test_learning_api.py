"""Layer 6 · Phase 7 — the /v1/learning API surface (structural ratchet)."""
from __future__ import annotations

import genios_engine.api.learning_routes as lr

_EXPECTED = {
    "/v1/learning/overview", "/v1/learning/objects", "/v1/learning/brains",
    "/v1/learning/suggestions", "/v1/learning/memories", "/v1/learning/policy",
    "/v1/learning/objects/{learning_id}/rollback", "/v1/learning/objects/{learning_id}/review",
}


def test_learning_routes_are_registered():
    paths = {r.path for r in lr.router.routes}
    assert not (_EXPECTED - paths), f"missing: {_EXPECTED - paths}"


def test_there_is_no_expert_endpoint():
    for r in lr.router.routes:
        assert "expert" not in r.path.lower(), "Layer 6 must never expose an Expert-Brain edit"


def test_review_and_rollback_are_writes():
    methods = {}
    for r in lr.router.routes:
        methods.setdefault(r.path, set()).update(getattr(r, "methods", set()) or set())
    assert "POST" in methods["/v1/learning/objects/{learning_id}/review"]
    assert "POST" in methods["/v1/learning/objects/{learning_id}/rollback"]
    assert "GET" in methods["/v1/learning/overview"]


def test_app_boots_with_learning_routes():
    import genios_engine.main  # noqa: F401
