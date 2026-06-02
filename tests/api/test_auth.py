"""Smoke + integration tests for /auth/* routes (signup/login/me/logout)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.api.deps import db_session
from core.foundations.config import settings
from core.foundations.db import Base
from core.main import app
from core.memory.store import SecretRef  # noqa: F401 — loads FK target


@pytest.fixture(autouse=True)
def _ensure_jwt_secret() -> Iterator[None]:
    prev = settings.JWT_SECRET
    if not prev:
        settings.JWT_SECRET = "test-jwt-secret-not-for-production"  # noqa: S105
    try:
        yield
    finally:
        settings.JWT_SECRET = prev


@pytest.fixture
def engine() -> Iterator[object]:
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
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


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
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _signup_payload(email: str = "alice@acme.com", **overrides: object) -> dict:
    base = {
        "email": email,
        "password": "correct-horse-battery-staple",
        "name": "Alice Cooper",
        "org_name": "Acme Corp",
    }
    base.update(overrides)  # type: ignore[arg-type]
    return base


@pytest.mark.unit
def test_signup_creates_user_org_and_api_key(client: TestClient) -> None:
    r = client.post("/auth/signup", json=_signup_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "alice@acme.com"
    assert body["org"]["name"] == "Acme Corp"
    assert body["org"]["role"] == "admin"
    assert body["org"]["plan"] == "trial"
    assert body["token"]
    assert body["api_key"].startswith("gn_live_")
    # Cookie set
    cookie = r.cookies.get("genios_session")
    assert cookie


@pytest.mark.unit
def test_signup_duplicate_email_409(client: TestClient) -> None:
    client.post("/auth/signup", json=_signup_payload())
    r = client.post("/auth/signup", json=_signup_payload())
    assert r.status_code == 409


@pytest.mark.unit
def test_login_with_wrong_password_401(client: TestClient) -> None:
    client.post("/auth/signup", json=_signup_payload())
    r = client.post(
        "/auth/login",
        json={"email": "alice@acme.com", "password": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.unit
def test_login_returns_jwt_and_sets_cookie(client: TestClient) -> None:
    client.post("/auth/signup", json=_signup_payload())
    r = client.post(
        "/auth/login",
        json={"email": "alice@acme.com", "password": "correct-horse-battery-staple"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["api_key"] is None  # only on signup
    assert r.cookies.get("genios_session")


@pytest.mark.unit
def test_me_via_cookie(client: TestClient) -> None:
    client.post("/auth/signup", json=_signup_payload())
    # TestClient persists cookies across requests
    r = client.get("/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == "alice@acme.com"
    assert body["org"]["name"] == "Acme Corp"


@pytest.mark.unit
def test_me_via_bearer(client: TestClient) -> None:
    signup = client.post("/auth/signup", json=_signup_payload())
    token = signup.json()["token"]
    # Wipe cookies — force Bearer path
    client.cookies.clear()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.unit
def test_me_without_session_401(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.unit
def test_logout_clears_cookie(client: TestClient) -> None:
    client.post("/auth/signup", json=_signup_payload())
    r = client.post("/auth/logout")
    assert r.status_code == 204
    # After logout, /me should fail (cookie cleared)
    r2 = client.get("/auth/me")
    assert r2.status_code == 401


@pytest.mark.unit
def test_protected_route_accepts_jwt_cookie(client: TestClient) -> None:
    """A v1/* route should accept the cookie session set by signup."""
    client.post("/auth/signup", json=_signup_payload())
    # Hit a route protected by require_org — usermodel /seed
    r = client.post("/v1/usermodel/seed", json={"user_id": "u_test"})
    # 201 (created) or at least not 401 — the session cookie was accepted
    assert r.status_code in (200, 201), r.text


@pytest.mark.unit
def test_signup_minted_api_key_works_for_v1_routes(client: TestClient) -> None:
    """The first API key from signup should authenticate /v1/* calls."""
    signup = client.post("/auth/signup", json=_signup_payload())
    api_key = signup.json()["api_key"]
    client.cookies.clear()
    r = client.get(
        "/v1/metrics/intervention_rate/summary",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert r.status_code == 200, r.text
