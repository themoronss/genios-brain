"""Signed generic webhook delivery for customer APIs and automation endpoints."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
from urllib.parse import urlparse

from genios_engine.deliver.channels.base import ChannelResult


def valid_endpoint_url(url: str | None) -> bool:
    """Require public HTTPS and reject obvious SSRF destinations.

    Production egress should additionally enforce a network-level allowlist; application
    validation is defense in depth, not a substitute for it.
    """
    if not url:
        return False
    parsed = urlparse(str(url))
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        return False
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (address.is_private or address.is_loopback or address.is_link_local
                or address.is_multicast or address.is_reserved or address.is_unspecified)


class SignedWebhookChannel:
    name = "webhook"

    def send(self, payload: dict, config: dict) -> ChannelResult:
        url = (config or {}).get("webhook_url")
        secret = str((config or {}).get("webhook_secret") or "")
        if not valid_endpoint_url(url):
            return ChannelResult(ok=False, detail="invalid or missing public https webhook_url")
        if len(secret) < 16:
            return ChannelResult(ok=False, detail="webhook_secret must be at least 16 characters")
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True,
                          default=str).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        try:
            import httpx
            response = httpx.post(
                str(url), content=body, timeout=10.0,
                headers={"Content-Type": "application/json",
                         "X-Genios-Signature": f"sha256={signature}",
                         "Idempotency-Key": str((config or {}).get("_idempotency_key") or "")})
            if 200 <= response.status_code < 300:
                return ChannelResult(ok=True, http_status=response.status_code,
                                     provider_message_id=response.headers.get("x-request-id"))
            retry_after = response.headers.get("retry-after")
            return ChannelResult(
                ok=False,
                detail=f"webhook http {response.status_code}: {response.text[:120]}",
                retryable=(response.status_code in {408, 425, 429}
                           or response.status_code >= 500),
                unknown=(response.status_code in {408, 425}
                         or response.status_code >= 500),
                http_status=response.status_code,
                retry_after_seconds=(int(retry_after) if retry_after and retry_after.isdigit()
                                     else None))
        except Exception as exc:  # noqa: BLE001 — the outbox owns retry policy
            return ChannelResult(ok=False, retryable=True, unknown=True,
                                 detail=f"{type(exc).__name__}: {str(exc)[:160]}")


__all__ = ["SignedWebhookChannel", "valid_endpoint_url"]
