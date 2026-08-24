"""Public benchmarks scorecard + methodology — shape + no-auth (hermetic, no DB needed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import genios_engine.main as m

client = TestClient(m.app)


def test_scorecard_is_public_and_well_shaped():
    r = client.get("/v1/benchmarks/scorecard")            # no Authorization header
    assert r.status_code == 200
    body = r.json()
    for key in ("version", "build_sha", "generated_at", "window_days",
                "min_n_gate", "k_anonymous", "scale", "tier1", "per_detector"):
        assert key in body
    # tier1 metrics gate honestly when there is no data
    assert body["tier1"] == {} or "faithfulness" in body["tier1"]


def test_methodology_is_public():
    r = client.get("/v1/benchmarks/methodology")
    assert r.status_code == 200
    assert r.json()["k_anonymous"] is True
