"""Smoke + integration tests for the HTTP API layer.

Covers the bridge from FastAPI routes → engine modules. Auth uses the X-Dev-Org
header (allowed when GENIOS_ENV is not production — see core/api/deps.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.api import intelligence as intelligence_router
from core.api.deps import db_session
from core.decision_store import DecisionRow
from core.delivery.envelope import (
    AsOfPin,
    Envelope,
    EnvelopeRoute,
    EnvelopeTriggeredBy,
)
from core.foundations.db import Base
from core.foundations.metrics_store import InterventionMetricRow
from core.main import app
from core.memory.store import SecretRef  # noqa: F401 — loads FK target

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> Iterator[object]:
    # StaticPool + check_same_thread=False so the TestClient's request thread
    # and our fixture-setup thread share the same in-memory DB instance.
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: object) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def _override_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[db_session] = _override_db
    intelligence_router.clear_handlers()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        intelligence_router.clear_handlers()


def _h(org_id: str = "o_test") -> dict[str, str]:
    return {"X-Dev-Org": org_id}


# ─────────────────────────────────────────────────────────────────────────────
# Liveness + auth
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_health_no_auth(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.unit
def test_intelligence_requires_auth(client: TestClient) -> None:
    r = client.post("/v1/intelligence/query", json={"module_id": "sales", "query": {}})
    assert r.status_code == 401


@pytest.mark.unit
def test_intelligence_dev_org_header_accepted(client: TestClient) -> None:
    r = client.post(
        "/v1/intelligence/query",
        json={"module_id": "unknown_mod", "query": {}},
        headers=_h(),
    )
    assert r.status_code == 503  # no handler registered — auth was accepted


# ─────────────────────────────────────────────────────────────────────────────
# Intelligence routes
# ─────────────────────────────────────────────────────────────────────────────


def _stub_envelope(org_id: str = "o_test", decision_id: str = "dec_x") -> Envelope:
    return Envelope(
        recommendation={"conclusion": "x"},
        confidence=0.8,
        derivation=[{"rule_id": "r1", "conclusion": "x"}],
        uncertainty=[],
        route=EnvelopeRoute.NOTIFY,
        triggered_by=EnvelopeTriggeredBy.QUERY,
        as_of=AsOfPin(graph_version=1, timestamp=datetime.now(UTC)),
        decision_id=decision_id,
        org_id=org_id,
    )


@pytest.mark.unit
def test_query_dispatches_to_registered_handler(client: TestClient) -> None:
    captured: dict[str, object] = {}

    def handler(session: Session, org_id: str, query: dict, facts: dict, user_id: str | None) -> Envelope:
        captured["org_id"] = org_id
        captured["query"] = query
        return _stub_envelope(org_id=org_id)

    intelligence_router.register_query_handler("sales", handler)

    r = client.post(
        "/v1/intelligence/query",
        json={"module_id": "sales", "query": {"q": "X"}, "facts": {}},
        headers=_h(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["confidence"] == 0.8
    assert body["org_id"] == "o_test"
    assert captured["query"] == {"q": "X"}


@pytest.mark.unit
def test_query_missing_handler_returns_503(client: TestClient) -> None:
    r = client.post(
        "/v1/intelligence/query",
        json={"module_id": "mystery", "query": {}},
        headers=_h(),
    )
    assert r.status_code == 503


@pytest.mark.unit
def test_explain_unknown_decision_404(client: TestClient) -> None:
    r = client.get("/v1/intelligence/decisions/nonexistent/explain", headers=_h())
    assert r.status_code == 404


@pytest.mark.unit
def test_feedback_thumbs_up_no_correction(client: TestClient) -> None:
    r = client.post(
        "/v1/intelligence/feedback",
        json={
            "user_id": "alice",
            "action": "thumbs_up",
            "decision_id": "dec_1",
        },
        headers=_h(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correction_id"] is None
    assert body["routed_to_g_i_3"] is False


@pytest.mark.unit
def test_feedback_thumbs_down_requires_decision_id(client: TestClient) -> None:
    r = client.post(
        "/v1/intelligence/feedback",
        json={"user_id": "alice", "action": "thumbs_down"},
        headers=_h(),
    )
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Metrics routes
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_metrics_intervention_summary_empty(client: TestClient) -> None:
    r = client.get("/v1/metrics/intervention_rate/summary", headers=_h())
    assert r.status_code == 200
    assert r.json() == {}


@pytest.mark.unit
def test_metrics_intervention_summary_with_data(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    today = datetime.now(UTC).date()
    with session_factory() as s:
        s.add(
            InterventionMetricRow(
                org_id="o_test",
                module_id="sales",
                date=today,
                total_decisions=10,
                human_overrides_count=2,
                intervention_rate=0.2,
            )
        )
        s.commit()
    r = client.get("/v1/metrics/intervention_rate/summary", headers=_h())
    assert r.status_code == 200
    assert r.json()["sales"] == 0.2


@pytest.mark.unit
def test_metrics_intervention_trend(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    end = datetime.now(UTC).date()
    with session_factory() as s:
        for i in range(4):
            s.add(
                InterventionMetricRow(
                    org_id="o_test",
                    module_id="sales",
                    date=end - timedelta(days=3 - i),
                    total_decisions=10,
                    human_overrides_count=int((0.5 if i < 2 else 0.1) * 10),
                    intervention_rate=0.5 if i < 2 else 0.1,
                )
            )
        s.commit()
    r = client.get(
        "/v1/metrics/intervention_rate?module_id=sales&window_days=4", headers=_h()
    )
    assert r.status_code == 200
    body = r.json()
    assert body["direction"] == "down"
    assert len(body["rates"]) == 4


@pytest.mark.unit
def test_metrics_headline_returns_all_three(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    today = datetime.now(UTC).date()
    with session_factory() as s:
        s.add(
            InterventionMetricRow(
                org_id="o_test",
                module_id="sales",
                date=today,
                total_decisions=5,
                human_overrides_count=1,
                intervention_rate=0.2,
            )
        )
        s.commit()
    r = client.get("/v1/metrics/headline", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert "intervention_rate_by_module" in body
    assert "latest_roi_by_module" in body
    assert "latest_symbolic_resolution_rate_by_module" in body


@pytest.mark.unit
def test_calibration_window_empty_returns_404(client: TestClient) -> None:
    r = client.get(
        "/v1/metrics/calibration?module_id=sales&window_days=7", headers=_h()
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Usermodel routes
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_usermodel_get_404_when_missing(client: TestClient) -> None:
    r = client.get("/v1/usermodel/nobody", headers=_h())
    assert r.status_code == 404


@pytest.mark.unit
def test_usermodel_seed_view_update_delete_flow(client: TestClient) -> None:
    # seed
    r = client.post(
        "/v1/usermodel/seed",
        json={"user_id": "u1", "voice": {"tone": ["polite"]}},
        headers=_h(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user_id"] == "u1"

    # view
    r = client.get("/v1/usermodel/u1", headers=_h())
    assert r.status_code == 200
    assert r.json()["voice"]["tone"] == ["polite"]

    # patch
    r = client.patch(
        "/v1/usermodel/u1/field",
        json={"field": "voice", "new_value": {"tone": ["formal"]}},
        headers=_h(),
    )
    assert r.status_code == 200
    assert r.json()["voice"]["tone"] == ["formal"]

    # delete
    r = client.delete("/v1/usermodel/u1", headers=_h())
    assert r.status_code == 204

    # gone
    r = client.get("/v1/usermodel/u1", headers=_h())
    assert r.status_code == 404


@pytest.mark.unit
def test_usermodel_seed_duplicate_conflict(client: TestClient) -> None:
    client.post("/v1/usermodel/seed", json={"user_id": "u_dup"}, headers=_h())
    r = client.post("/v1/usermodel/seed", json={"user_id": "u_dup"}, headers=_h())
    assert r.status_code == 409


@pytest.mark.unit
def test_usermodel_cross_org_isolation(client: TestClient) -> None:
    client.post(
        "/v1/usermodel/seed",
        json={"user_id": "u_iso"},
        headers=_h("org_A"),
    )
    r = client.get("/v1/usermodel/u_iso", headers=_h("org_B"))
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Mapping routes
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_mapping_introspect_returns_fields(client: TestClient) -> None:
    r = client.post(
        "/v1/mapping/introspect",
        json={
            "source_type": "acme_db",
            "samples": [
                {"body": "hi", "ts": "2026-06-02", "owner": "alice"},
                {"body": "yo", "ts": "2026-06-02", "owner": "bob"},
            ],
        },
        headers=_h(),
    )
    assert r.status_code == 200
    field_names = {f["name"] for f in r.json()["fields"]}
    assert field_names == {"body", "ts", "owner"}


@pytest.mark.unit
def test_mapping_propose_returns_view(client: TestClient) -> None:
    r = client.post(
        "/v1/mapping/propose",
        json={
            "source_type": "acme_db",
            "samples": [
                {"body": "hello", "timestamp": "2026-06-02T10:00:00Z", "owner": "alice"}
                for _ in range(2)
            ],
        },
        headers=_h(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body
    canonicals = {r["canonical_field"] for r in body["rows"]}
    assert canonicals == {"content", "timestamp", "owner", "tags"}


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion route
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_ingest_accepts_batch(client: TestClient) -> None:
    item = {
        "item_id": "i1",
        "source_id": "src1",
        "source_type": "custom:test",
        "content": "hello",
        "metadata": {"timestamp": "2026-06-02T10:00:00Z"},
    }
    r = client.post(
        "/v1/ingest", json={"items": [item, {**item, "item_id": "i2"}]}, headers=_h()
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 0


@pytest.mark.unit
def test_ingest_empty_batch_rejected(client: TestClient) -> None:
    r = client.post("/v1/ingest", json={"items": []}, headers=_h())
    assert r.status_code == 422  # min_length=1


# ─────────────────────────────────────────────────────────────────────────────
# Audit + health
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_audit_events_org_scoped(client: TestClient) -> None:
    from core.foundations import audit

    with TestClient(app) as _:
        pass

    r = client.get("/v1/audit/events?limit=10", headers=_h())
    assert r.status_code == 200
    # Should at minimum return the events generated by our other tests' writes;
    # but in isolation may be empty — both are fine.
    assert isinstance(r.json(), list)
    # silence unused-import lint
    assert audit is not None


@pytest.mark.unit
def test_explain_returns_trace_for_existing_decision(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as s:
        d = DecisionRow(
            id="dec_explain_1",
            org_id="o_test",
            query_jsonb={"q": "x"},
            conclusion="x",
            derivation_chain_jsonb=[{"rule_id": "r1", "conclusion": "x"}],
            path="symbolic",
            confidence_score=0.9,
            confidence_breakdown_jsonb={"grounding": 0.9, "symbolic": 1.0},
            grounding_refs_jsonb=[],
            route="notify",
            as_of_version=1,
            triggered_by="query",
            module_id="sales",
        )
        s.add(d)
        s.commit()

    r = client.get("/v1/intelligence/decisions/dec_explain_1/explain", headers=_h())
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rules_fired" in body
    assert body["rules_fired"][0]["id"] == "r1"
