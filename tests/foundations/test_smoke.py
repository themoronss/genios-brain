"""Phase 1 smoke tests — proves the skeleton boots and foundations work."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_config_imports() -> None:
    """All tunables importable; settings load from test env."""
    from core.foundations import config

    assert config.N_MIN_EVIDENCE == 20
    assert config.CONFIDENCE_WEIGHTS["grounding"] == 0.4
    assert config.LLM_DAILY_BUDGET_USD["default"] == 10.0
    assert config.settings.GENIOS_ENV == "test"


@pytest.mark.unit
def test_encryption_round_trip() -> None:
    """Encrypt then decrypt returns the original."""
    from core.foundations.encryption import decrypt, encrypt

    plaintext = "ya29.fake-oauth-token-for-test"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


@pytest.mark.unit
def test_encryption_rejects_empty() -> None:
    """Empty strings rejected (defensive — no silent no-op)."""
    from core.foundations.encryption import EncryptionError, decrypt, encrypt

    with pytest.raises(EncryptionError):
        encrypt("")
    with pytest.raises(EncryptionError):
        decrypt("")


@pytest.mark.unit
def test_encryption_rejects_tampered() -> None:
    """Tampered ciphertext fails cleanly."""
    from core.foundations.encryption import EncryptionError, decrypt, encrypt

    ciphertext = encrypt("real-secret")
    tampered = ciphertext[:-4] + "XXXX"
    with pytest.raises(EncryptionError):
        decrypt(tampered)


@pytest.mark.unit
def test_audit_record_does_not_raise() -> None:
    """Audit writer accepts a well-formed event."""
    from core.foundations import audit

    audit.record(
        org_id="org_test",
        actor_type="system",
        actor_id="phase1_smoke",
        action="config_changed",
        target_type="tunable",
        target_id="N_MIN_EVIDENCE",
        metadata={"old": 30, "new": 20},
    )


@pytest.mark.unit
def test_fastapi_health() -> None:
    """FastAPI app boots and /health returns ok."""
    from core.main import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.unit
def test_fastapi_ready() -> None:
    """/ready endpoint reachable."""
    from core.main import app

    client = TestClient(app)
    r = client.get("/ready")
    assert r.status_code == 200
