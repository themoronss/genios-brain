"""Signed, retry-aware Layer 5.2 transport for registered agent runtimes."""
from __future__ import annotations

import hashlib
import hmac
import json

from genios_engine.deliver.channels.base import ChannelResult
from genios_engine.deliver.channels.webhook import valid_endpoint_url


class AgentWebhookChannel:
    name = "agent"

    def send(self, payload: dict, config: dict) -> ChannelResult:
        url = (config or {}).get("webhook_url")
        secret = str((config or {}).get("webhook_secret") or "")
        agent_id = str((config or {}).get("agent_id") or "")
        if not valid_endpoint_url(url):
            return ChannelResult(False, "invalid or missing agent webhook_url")
        if len(secret) < 16 or not agent_id:
            return ChannelResult(False, "agent webhook credentials are incomplete")
        envelope = {"type": "execution.delivery", "agent_id": agent_id, "payload": payload}
        body = json.dumps(envelope, separators=(",", ":"), sort_keys=True,
                          default=str).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        try:
            import httpx
            response = httpx.post(
                str(url), content=body, timeout=10.0,
                headers={"Content-Type": "application/json",
                         "X-Genios-Agent-Id": agent_id,
                         "X-Genios-Event": "execution.delivery",
                         "X-Genios-Signature": f"sha256={signature}",
                         "Idempotency-Key": str(config.get("_idempotency_key") or "")})
            if 200 <= response.status_code < 300:
                return ChannelResult(True, http_status=response.status_code,
                                     provider_message_id=response.headers.get("x-request-id"))
            retry_after = response.headers.get("retry-after")
            return ChannelResult(
                False, f"agent http {response.status_code}: {response.text[:120]}",
                retryable=(response.status_code in {408, 425, 429}
                           or response.status_code >= 500),
                unknown=(response.status_code in {408, 425}
                         or response.status_code >= 500),
                http_status=response.status_code,
                retry_after_seconds=(int(retry_after) if retry_after and retry_after.isdigit()
                                     else None))
        except Exception as exc:  # noqa: BLE001 - the outbox owns retry/reconciliation
            return ChannelResult(False, f"{type(exc).__name__}: {str(exc)[:160]}",
                                 retryable=True, unknown=True)


__all__ = ["AgentWebhookChannel"]
