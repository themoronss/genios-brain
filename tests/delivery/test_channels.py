"""Tests for channel adapters — Slack / email / webhook_out."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.delivery.channels.base import DeliveryError, DeliveryStatus
from core.delivery.channels.email import EmailChannel, EmailMessage
from core.delivery.channels.slack import SlackChannel
from core.delivery.channels.webhook_out import WebhookChannel, verify_webhook_signature
from core.delivery.envelope import build_envelope


def _env(*, decision_id: str = "dec_1") -> Any:
    return build_envelope(
        org_id="o",
        decision_id=decision_id,
        recommendation={"conclusion": "churn_risk_high", "recommend": "follow_up"},
        confidence=0.85,
        derivation=[{"rule_id": "r1", "conclusion": "churn_risk_high"}],
        uncertainty=[{"kind": "low_trust_edge", "detail": "edge under N_min"}],
        route="notify",
        triggered_by="query",
        as_of_version=1,
        as_of_timestamp=datetime(2026, 6, 1, tzinfo=UTC),
    )


# ── Slack ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_slack_sends_when_mapping_exists() -> None:
    posted: list[tuple[str, dict[str, Any]]] = []

    def poster(slack_id: str, msg: dict[str, Any]) -> dict[str, Any]:
        posted.append((slack_id, msg))
        return {"ok": True}

    ch = SlackChannel(poster=poster, user_id_to_slack_id=lambda u: f"U_{u}")
    attempt = ch.send(envelope=_env(), user_id="alice", is_digest=False)
    assert attempt.status == DeliveryStatus.SENT
    assert len(posted) == 1
    assert posted[0][0] == "U_alice"
    # Confidence + uncertainty must be visible in the Slack blocks
    msg = posted[0][1]
    text_blob = str(msg)
    assert "85%" in text_blob or "0.85" in text_blob.replace(",", "")
    assert "uncertainty flag" in text_blob


@pytest.mark.unit
def test_slack_suppresses_when_no_mapping() -> None:
    ch = SlackChannel(poster=lambda *_: {"ok": True}, user_id_to_slack_id=lambda _: None)
    attempt = ch.send(envelope=_env(), user_id="alice", is_digest=False)
    assert attempt.status == DeliveryStatus.SUPPRESSED


@pytest.mark.unit
def test_slack_raises_on_transport_failure() -> None:
    def boom(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("network down")

    ch = SlackChannel(poster=boom, user_id_to_slack_id=lambda u: f"U_{u}")
    with pytest.raises(DeliveryError):
        ch.send(envelope=_env(), user_id="alice", is_digest=False)


# ── Email ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_email_sends() -> None:
    sent: list[EmailMessage] = []

    def sender(msg: EmailMessage) -> dict[str, Any]:
        sent.append(msg)
        return {"MessageId": "x"}

    ch = EmailChannel(sender=sender, user_id_to_email=lambda u: f"{u}@acme.com")
    attempt = ch.send(envelope=_env(), user_id="alice", is_digest=True)
    assert attempt.status == DeliveryStatus.SENT
    assert sent[0].to_email == "alice@acme.com"
    assert "Digest" in sent[0].subject  # digest mode tagged in subject


@pytest.mark.unit
def test_email_rate_limit_suppresses() -> None:
    """Rate cap 1/min/user — second send in same minute is suppressed."""
    ch = EmailChannel(
        sender=lambda _: {"ok": True},
        user_id_to_email=lambda u: f"{u}@acme.com",
        rate_per_min=1,
    )
    first = ch.send(envelope=_env(decision_id="d1"), user_id="alice", is_digest=True)
    second = ch.send(envelope=_env(decision_id="d2"), user_id="alice", is_digest=True)
    assert first.status == DeliveryStatus.SENT
    assert second.status == DeliveryStatus.SUPPRESSED


# ── Webhook out ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_webhook_sends_signed_payload() -> None:
    captured: dict[str, Any] = {}

    def poster(url: str, headers: dict[str, str], body: bytes) -> int:
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return 200

    ch = WebhookChannel(
        poster=poster,
        user_id_to_webhook=lambda u: ("https://acme.com/hook", "secret-123"),
    )
    env = _env()
    attempt = ch.send(envelope=env, user_id="alice", is_digest=False)

    assert attempt.status == DeliveryStatus.SENT
    assert captured["url"] == "https://acme.com/hook"
    sig_header = captured["headers"]["X-Genios-Signature"]
    # Signature verifies with the secret
    assert verify_webhook_signature(
        body=captured["body"], signature_header=sig_header, secret="secret-123"
    )


@pytest.mark.unit
def test_webhook_signature_rejects_tampered_payload() -> None:
    sig = "sha256=" + "0" * 64
    assert not verify_webhook_signature(body=b"x", signature_header=sig, secret="s")


@pytest.mark.unit
def test_webhook_non_2xx_marked_failed() -> None:
    ch = WebhookChannel(
        poster=lambda *_: 502,
        user_id_to_webhook=lambda u: ("https://acme.com/h", "s"),
    )
    attempt = ch.send(envelope=_env(), user_id="alice", is_digest=False)
    assert attempt.status == DeliveryStatus.FAILED
    assert "502" in (attempt.error or "")


@pytest.mark.unit
def test_webhook_suppressed_when_no_config() -> None:
    ch = WebhookChannel(poster=lambda *_: 200, user_id_to_webhook=lambda _: None)
    attempt = ch.send(envelope=_env(), user_id="alice", is_digest=False)
    assert attempt.status == DeliveryStatus.SUPPRESSED
