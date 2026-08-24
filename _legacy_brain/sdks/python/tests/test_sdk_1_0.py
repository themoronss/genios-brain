"""SDK 1.0 unit tests — retries, idempotency, webhook signature verify."""
from __future__ import annotations

import hashlib
import hmac
import time
from unittest.mock import MagicMock, patch

import pytest

from genios.client import GeniOS, GeniOSError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GENIOS_API_KEY", "test-key")
    return GeniOS(base_url="http://test.local", timeout=1)


# ── Retries ──────────────────────────────────────────────────────────────────

def _mock_resp(status, text="{}"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json.return_value = {} if text == "{}" else {"ok": True}
    return r


def test_retries_on_5xx_then_success(client):
    calls = []
    def fake_request(method, url, **kw):
        calls.append(1)
        return _mock_resp(200 if len(calls) > 2 else 503, '{"ok": true}')
    with patch("genios.client.requests.request", side_effect=fake_request):
        with patch("genios.client.time.sleep"):  # fast-forward backoff
            result = client.context("Foo", "bar")
    assert result == {"ok": True}
    assert len(calls) == 3  # 2 fails + 1 success


def test_retries_on_429_then_success(client):
    calls = []
    def fake_request(method, url, **kw):
        calls.append(1)
        return _mock_resp(200 if len(calls) > 1 else 429)
    with patch("genios.client.requests.request", side_effect=fake_request):
        with patch("genios.client.time.sleep"):
            client.context("Foo", "bar")
    assert len(calls) == 2


def test_no_retry_on_400(client):
    calls = []
    def fake_request(method, url, **kw):
        calls.append(1)
        return _mock_resp(400, "bad request")
    with patch("genios.client.requests.request", side_effect=fake_request):
        with pytest.raises(GeniOSError):
            client.context("Foo", "bar")
    assert len(calls) == 1


def test_retries_exhausted_raises(client):
    def fake_request(method, url, **kw):
        return _mock_resp(503, "down")
    with patch("genios.client.requests.request", side_effect=fake_request):
        with patch("genios.client.time.sleep"):
            with pytest.raises(GeniOSError):
                client.context("Foo", "bar")


# ── Idempotency header ───────────────────────────────────────────────────────

def test_feedback_sends_idempotency_header(client):
    captured = {}
    def fake_request(method, url, **kw):
        captured.update(kw.get("headers", {}))
        return _mock_resp(200)
    with patch("genios.client.requests.request", side_effect=fake_request):
        client.feedback("rec-1", "acted", idempotency_key="abc-123")
    assert captured.get("Idempotency-Key") == "abc-123"


def test_feedback_omits_header_when_no_key(client):
    captured = {}
    def fake_request(method, url, **kw):
        captured.update(kw.get("headers", {}))
        return _mock_resp(200)
    with patch("genios.client.requests.request", side_effect=fake_request):
        client.feedback("rec-1", "acted")
    assert "Idempotency-Key" not in captured


# ── Webhook signature verify ─────────────────────────────────────────────────

def test_verify_webhook_signature_valid():
    secret = "shhh"
    body = b'{"event":"recommendation"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert GeniOS.verify_webhook_signature(secret, body, sig) is True


def test_verify_webhook_signature_invalid():
    assert GeniOS.verify_webhook_signature("shhh", b"x", "deadbeef") is False


def test_verify_webhook_signature_wrong_secret():
    body = b"test"
    sig = hmac.new(b"right", body, hashlib.sha256).hexdigest()
    assert GeniOS.verify_webhook_signature("wrong", body, sig) is False
