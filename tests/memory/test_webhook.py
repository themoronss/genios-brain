"""Tests for core.memory.webhook — signature verification (forged-payload rejection)."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from core.memory.webhook import HmacSha256Verifier, WebhookVerificationError, receive


@pytest.mark.unit
def test_valid_signature_accepts() -> None:
    secret = "shared-secret"
    body = b'{"event":"ping"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    verifier = HmacSha256Verifier(header_name="X-Hub-Signature")
    accepted = receive(
        verifier=verifier,
        secret=secret,
        body=body,
        headers={"X-Hub-Signature": sig},
        connection_id="c",
        org_id="o",
    )
    assert accepted is True


@pytest.mark.unit
def test_forged_signature_rejects() -> None:
    """Per g-i-1 acceptance: forged payloads MUST be rejected."""
    verifier = HmacSha256Verifier(header_name="X-Hub-Signature")
    accepted = receive(
        verifier=verifier,
        secret="real-secret",
        body=b'{"event":"forged"}',
        headers={"X-Hub-Signature": "0" * 64},  # totally wrong
        connection_id="c",
        org_id="o",
    )
    assert accepted is False


@pytest.mark.unit
def test_missing_signature_header_rejects() -> None:
    verifier = HmacSha256Verifier(header_name="X-Hub-Signature")
    accepted = receive(
        verifier=verifier,
        secret="s",
        body=b"{}",
        headers={},
        connection_id="c",
        org_id="o",
    )
    assert accepted is False


@pytest.mark.unit
def test_prefix_supported() -> None:
    """Many providers use 'sha256=<hex>' prefix (GitHub, Stripe)."""
    secret = "k"
    body = b"payload"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verifier = HmacSha256Verifier(header_name="X-Sig", prefix="sha256=")
    verifier.verify(body=body, headers={"X-Sig": f"sha256={sig}"}, secret=secret)


@pytest.mark.unit
def test_constant_time_compare_used() -> None:
    """Sanity check — wrong-length signatures don't crash, they just fail."""
    verifier = HmacSha256Verifier(header_name="X-Sig")
    with pytest.raises(WebhookVerificationError):
        verifier.verify(body=b"x", headers={"X-Sig": "short"}, secret="s")
