"""P6 §3.1 action request — `send_action` headers, v1 signature, outcome classes, retries.
Hermetic: httpx.MockTransport, literal public IP (no DNS)."""
from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest

from genios_engine.deliver.channels import agent as A
from genios_engine.platform.auth import verify_webhook_hmac

SECRET = "gnwh_test_secret"
CFG = {"agent_id": "hermes", "webhook_url": "https://93.184.215.14/genios/action",
       "webhook_secret": SECRET}
BODY = json.dumps({"type": "action.requested", "version": 1, "delegation_id": "dlg_1",
                   "play": "email.reschedule", "params": {}}, separators=(",", ":")).encode()
T = 1_800_000_000


def _client(responses, seen):
    it = iter(responses)

    def handler(request: httpx.Request):
        seen.append(request)
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_headers_body_and_v1_signature():
    seen: list[httpx.Request] = []
    out = A.send_action(BODY, CFG, delegation_id="dlg_1", now=T,
                        client=_client([httpx.Response(200)], seen))
    assert out.status == A.DELIVERED and out.ok and not out.retry and out.timestamp == T
    req = seen[0]
    h = req.headers
    assert req.content == BODY and req.method == "POST"
    assert h["x-genios-event"] == "action.requested"
    assert h["x-genios-agent-id"] == "hermes"
    assert h["x-genios-delivery-id"] == "dlg_1" and h["idempotency-key"] == "dlg_1"
    assert h["x-genios-timestamp"] == str(T)
    expected = hmac.new(SECRET.encode(), f"{T}.".encode() + BODY, hashlib.sha256).hexdigest()
    assert h["x-genios-signature"] == f"v1={expected}"


def test_verifier_accepts_within_300s_and_rejects_skew_tamper_and_wrong_secret():
    sig = A.sign_v1(SECRET, T, BODY)
    ok = dict(timestamp=str(T), signature=sig, secret=SECRET)
    assert A.verify_action_signature(BODY, **ok, now=T + 300)
    assert A.verify_action_signature(BODY, **ok, now=T - 300)
    assert not A.verify_action_signature(BODY, **ok, now=T + 301)      # > 300 s skew
    assert not A.verify_action_signature(BODY, **ok, now=T - 301)
    assert not A.verify_action_signature(BODY + b" ", **ok, now=T)      # body tampered
    assert not A.verify_action_signature(BODY, timestamp=str(T + 1), signature=sig,
                                         secret=SECRET, now=T)           # timestamp swapped
    assert not A.verify_action_signature(BODY, timestamp=str(T), signature=sig,
                                         secret="other", now=T)
    legacy = "sha256=" + hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert not A.verify_action_signature(BODY, timestamp=str(T), signature=legacy,
                                         secret=SECRET, now=T)           # old body-only scheme
    # rotation: any matching v1 entry verifies
    assert A.verify_action_signature(BODY, timestamp=str(T), signature=f"v1=deadbeef, {sig}",
                                     secret=SECRET, now=T)


def test_retry_keeps_delivery_id_and_body_with_a_fresh_signed_timestamp():
    seen: list[httpx.Request] = []
    client = _client([httpx.Response(503), httpx.Response(200)], seen)
    first = A.send_action(BODY, CFG, delegation_id="dlg_1", now=T, client=client)
    second = A.send_action(BODY, CFG, delegation_id="dlg_1", now=T + 60, client=client)
    assert first.status == A.RETRYABLE and first.retry and first.http_status == 503
    assert second.status == A.DELIVERED
    a, b = seen
    assert a.content == b.content == BODY
    for k in ("x-genios-delivery-id", "idempotency-key"):
        assert a.headers[k] == b.headers[k] == "dlg_1"
    assert a.headers["x-genios-timestamp"] != b.headers["x-genios-timestamp"]
    for req, now in ((a, T), (b, T + 60)):
        assert A.verify_action_signature(req.content, timestamp=req.headers["x-genios-timestamp"],
                                         signature=req.headers["x-genios-signature"],
                                         secret=SECRET, now=now)


@pytest.mark.parametrize("response,status", [
    (httpx.ReadTimeout("slow"), A.TIMEOUT_UNKNOWN),
    (httpx.RemoteProtocolError("dropped"), A.TIMEOUT_UNKNOWN),
    (httpx.ConnectError("refused"), A.RETRYABLE),
    (httpx.ConnectTimeout("no route"), A.RETRYABLE),
    (httpx.Response(500), A.RETRYABLE),
    (httpx.Response(408), A.RETRYABLE),
    (httpx.Response(400), A.PERMANENT),
    (httpx.Response(401), A.PERMANENT),
    (httpx.Response(404), A.PERMANENT),
    (httpx.Response(302, headers={"Location": "https://10.0.0.1/"}), A.PERMANENT),
])
def test_outcome_classes(response, status):
    seen: list[httpx.Request] = []
    out = A.send_action(BODY, CFG, delegation_id="dlg_1", now=T, client=_client([response], seen))
    assert out.status == status
    assert len(seen) == 1, "never follows a redirect, never retries inside one attempt"


def test_429_carries_retry_after():
    out = A.send_action(BODY, CFG, delegation_id="dlg_1", now=T, client=_client(
        [httpx.Response(429, headers={"Retry-After": "30"})], []))
    assert out.status == A.RETRYABLE and out.retry_after_s == 30


def test_egress_refusal_sends_nothing():
    seen: list[httpx.Request] = []
    for url in ("https://10.0.0.1/x", "https://169.254.169.254/", "http://evil.example/"):
        out = A.send_action(BODY, {**CFG, "webhook_url": url}, delegation_id="dlg_1", now=T,
                            client=_client([httpx.Response(200)], seen))
        assert out.status == A.PERMANENT and out.detail.startswith("egress_refused:")
    assert seen == []


def test_missing_secret_or_id_is_permanent():
    assert A.send_action(BODY, {**CFG, "webhook_secret": None}, delegation_id="d").status == A.PERMANENT
    assert A.send_action(BODY, CFG, delegation_id="").status == A.PERMANENT
    assert A.send_action(b"", CFG, delegation_id="d").status == A.PERMANENT


def test_signal_created_wire_format_unchanged_and_result_has_ok(monkeypatch):
    seen: list[httpx.Request] = []
    client = _client([httpx.Response(200), httpx.Response(500)], seen)
    real = A._post
    monkeypatch.setattr(A, "_post", lambda url, **kw: real(url, client=client, **kw))
    payload = {"type": "signal.created", "org_id": "o", "signal": {"signal_id": "s1"}}
    res = A.AgentWebhookChannel().send(payload, CFG)
    assert res.ok and bool(res)             # the drain reads .ok; older callers read it as a bool
    req = seen[0]
    assert req.content == json.dumps(payload, default=str).encode()
    assert verify_webhook_hmac(req.content, req.headers["x-genios-signature"], SECRET)
    assert req.headers["x-genios-signature"].startswith("sha256=")
    assert req.headers["x-genios-event"] == "signal.created"
    assert "x-genios-timestamp" not in req.headers
    bad = A.AgentWebhookChannel().send(payload, CFG)
    assert not bad.ok and not bad and bad.detail == "http 500"
    refused = A.AgentWebhookChannel().send(payload, {**CFG, "webhook_url": "https://10.0.0.1/"})
    assert not refused.ok and refused.detail == "egress_refused:private_address"
