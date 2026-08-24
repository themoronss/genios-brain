"""GeniOS Python SDK 1.0.

Features added in 1.0 (Phase 5.5):
  - Retries with exp backoff on 5xx / 429 (250ms, 1s, 4s)
  - idempotency_key param on feedback() / outcome()
  - verify_webhook_signature() helper
  - Async SSE client: client.stream.recommendations(...)

Usage:
    from genios import GeniOS
    client = GeniOS(api_key="gn_live_...")
    bundle = client.context("John Smith", "about to close a deal")
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import AsyncIterator, Optional

import requests


_DEFAULT_BASE_URL = "https://squid-app-2zuqf.ondigitalocean.app"
_DEFAULT_TIMEOUT = 10
_RETRY_BACKOFF_SECONDS = (0.25, 1.0, 4.0)


class GeniOSError(Exception):
    """Raised on non-retryable errors or when retries are exhausted."""


class AgentsNamespace:
    """Per-agent identity + scope (Agent Registry, PRD §03).

    The bearer key in this client identifies the calling agent. The server
    enforces scope at the SQL layer — never trust prompt-level filtering.

    Common flow for a customer with multiple agents:
        admin = GeniOS(api_key="gn_live_<brain_or_default_key>")
        admin.agents.create(
            agent_id="sales_ae",
            scope={
                "segments": ["Customer"],
                "fact_types": ["deal_state","commitment","engagement_state"],
                "max_age_days": 90,
            },
        )  # → returns a new key for the sales_ae agent
    """

    def __init__(self, client: "GeniOS"):
        self._client = client

    # Legacy 1.x — keep for backwards compat
    def register(self, name: str, description: str = "") -> dict:
        return self._client._post("/v1/agent", {"agent_id": name, "name": description or name})

    # New (Agent Registry)
    def create(
        self,
        agent_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scope: Optional[dict] = None,
    ) -> dict:
        """Register an agent + scope policy in one call. Server returns a new
        bearer key bound to this agent."""
        body = {"agent_id": agent_id}
        if name is not None: body["name"] = name
        if description is not None: body["description"] = description
        if scope is not None: body["scope"] = scope
        return self._client._post("/v1/agents", body)

    def list(self) -> dict:
        return self._client._get("/v1/agents")

    def get(self, agent_id: str) -> dict:
        return self._client._get(f"/v1/agents/{agent_id}")

    def whoami(self) -> dict:
        """Server-derived identity for this client's bearer key."""
        return self._client._get("/v1/agents/me")

    def edit_scope(self, agent_id: str, scope: dict) -> dict:
        return self._client._patch(f"/v1/agents/{agent_id}/scope", {"scope": scope})

    def rotate_key(self, agent_id: str, revoke_old: bool = False) -> dict:
        return self._client._post(
            f"/v1/agents/{agent_id}/keys",
            {"revoke_old": revoke_old},
        )

    def archive(self, agent_id: str) -> dict:
        return self._client._delete(f"/v1/agents/{agent_id}")

    def audit(self, agent_id: str, limit: int = 50) -> dict:
        return self._client._get(f"/v1/agents/{agent_id}/audit?limit={limit}")

    # ── Per-agent connectors (Phase 6 — Inkbox / custom integrations) ─────
    def list_connectors(self, agent_id: str) -> dict:
        return self._client._get(f"/v1/agents/{agent_id}/connectors")

    def add_connector(
        self,
        agent_id: str,
        source: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create or rotate a connector for this agent. Returns a `signing_secret`
        that the caller MUST save and configure in their provider (e.g. Inkbox)
        for X-Genios-Signature HMAC verification."""
        return self._client._post(
            f"/v1/agents/{agent_id}/connectors",
            {"source": source, "metadata": metadata or {}},
        )

    def remove_connector(self, agent_id: str, connector_id: str) -> dict:
        return self._client._delete(f"/v1/agents/{agent_id}/connectors/{connector_id}")

    # ── Per-agent trust list (Phase 6.5) ──────────────────────────────────
    def list_trust(self, agent_id: str) -> dict:
        return self._client._get(f"/v1/agents/{agent_id}/trust")

    def add_trust(
        self,
        agent_id: str,
        contact_id: Optional[str] = None,
        match_email: Optional[str] = None,
        match_phone: Optional[str] = None,
        note: Optional[str] = None,
    ) -> dict:
        body = {"note": note}
        if contact_id:  body["contact_id"]  = contact_id
        if match_email: body["match_email"] = match_email
        if match_phone: body["match_phone"] = match_phone
        return self._client._post(f"/v1/agents/{agent_id}/trust", body)

    def remove_trust(self, agent_id: str, trust_id: str) -> dict:
        return self._client._delete(f"/v1/agents/{agent_id}/trust/{trust_id}")


class IngestNamespace:
    """Push-based ingest from external systems (e.g. Inkbox webhooks).

    All endpoints are agent-keyed — the bearer key identifies which agent
    this data belongs to. Server enforces idempotency via `external_id`.

    Common flow (Inkbox example):
        client = GeniOS(api_key="<agent_key>")
        client.ingest.email(
            external_id="msg_abc123",
            from_address="lead@acme.com",
            to=["sales-bot@inkboxmail.com"],
            subject="Re: pricing",
            body_text="...",
            sent_at="2026-05-07T10:00:00Z",
        )
    """

    def __init__(self, client: "GeniOS"):
        self._client = client

    def email(
        self,
        external_id: str,
        from_address: str,
        to: list,
        sent_at: str,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        direction: str = "inbound",
        in_reply_to_external_id: Optional[str] = None,
        thread_external_id: Optional[str] = None,
    ) -> dict:
        payload = {
            "external_id": external_id,
            "from_address": from_address,
            "to": to,
            "sent_at": sent_at,
            "direction": direction,
        }
        for k, v in (
            ("subject", subject), ("body_text", body_text), ("body_html", body_html),
            ("in_reply_to_external_id", in_reply_to_external_id),
            ("thread_external_id", thread_external_id),
        ):
            if v is not None:
                payload[k] = v
        return self._client._post("/v1/ingest/email", payload)

    def call(
        self,
        external_id: str,
        from_number: str,
        to_number: str,
        started_at: str,
        duration_sec: int = 0,
        transcript: Optional[str] = None,
        direction: str = "inbound",
    ) -> dict:
        payload = {
            "external_id": external_id,
            "from_number": from_number,
            "to_number": to_number,
            "started_at": started_at,
            "duration_sec": duration_sec,
            "direction": direction,
        }
        if transcript is not None:
            payload["transcript"] = transcript
        return self._client._post("/v1/ingest/call", payload)

    def sms(
        self,
        external_id: str,
        from_number: str,
        to_number: str,
        body: str,
        sent_at: str,
        direction: str = "inbound",
    ) -> dict:
        return self._client._post("/v1/ingest/sms", {
            "external_id": external_id,
            "from_number": from_number,
            "to_number": to_number,
            "body": body,
            "sent_at": sent_at,
            "direction": direction,
        })

    def events(self, limit: int = 50) -> dict:
        """Recent ingest events for this agent (audit log)."""
        return self._client._get(f"/v1/ingest/events?limit={limit}")


class StreamNamespace:
    """Async SSE client. Requires `pip install httpx`."""

    def __init__(self, client: "GeniOS"):
        self._client = client

    async def recommendations(
        self,
        min_priority: float = 0.6,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[dict]:
        """Yield one dict per recommendation as the server emits it."""
        try:
            import httpx
        except ImportError as e:
            raise GeniOSError("httpx required for SSE streaming: pip install httpx") from e

        url = f"{self._client.base_url}/v1/stream/recommendations"
        params = {"min_priority": min_priority}
        headers = {
            "Authorization": f"Bearer {self._client.api_key}",
            "Accept": "text/event-stream",
        }

        async with httpx.AsyncClient(timeout=timeout) as http:
            async with http.stream("GET", url, params=params, headers=headers) as resp:
                resp.raise_for_status()
                event: Optional[str] = None
                async for line in resp.aiter_lines():
                    if not line:
                        event = None
                        continue
                    if line.startswith(":"):
                        continue  # heartbeat comment
                    if line.startswith("event:"):
                        event = line[6:].strip()
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if not data or event == "ping":
                            continue
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue


class GeniOS:
    """GeniOS API client (1.0)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.environ.get("GENIOS_API_KEY")
        if not self.api_key:
            raise ValueError("api_key is required. Pass it directly or set GENIOS_API_KEY env var.")
        self.base_url = (base_url or os.environ.get("GENIOS_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout
        self.agents = AgentsNamespace(self)
        self.ingest = IngestNamespace(self)
        self.stream = StreamNamespace(self)

    # ── Public methods ──────────────────────────────────────────────────────

    def context(
        self,
        entity: str,
        situation: str,
        agent_id: Optional[str] = None,
        segment_id: Optional[str] = None,
        context_size: Optional[str] = None,
    ) -> dict:
        payload = {"entity": entity, "situation": situation}
        if agent_id:     payload["agent_id"] = agent_id
        if segment_id:   payload["segment_id"] = segment_id
        if context_size: payload["context_size"] = context_size
        return self._post("/v1/context", payload)

    def feedback(
        self,
        recommendation_id: str,
        outcome: str,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Record outcome for a recommendation. outcome ∈ {acted, dismissed, ignored}."""
        payload = {"recommendation_id": recommendation_id, "outcome": outcome}
        if notes:
            payload["notes"] = notes
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._post("/v1/feedback", payload, extra_headers=headers)

    def outcome(
        self,
        context_id: str,
        outcome: str,
        signals: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """DEPRECATED — prefer feedback(). Server returns a Sunset header."""
        payload = {"context_id": context_id, "outcome": outcome}
        if signals:
            payload["signals"] = signals
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._post("/v1/outcome", payload, extra_headers=headers)

    def org(self) -> dict:
        return self._get("/v1/org")

    def sync_status(self) -> dict:
        return self._get("/v1/sync")

    @staticmethod
    def verify_webhook_signature(secret: str, body, signature: str) -> bool:
        """Constant-time HMAC-SHA256 check against X-Genios-Signature header."""
        if isinstance(body, str):
            body = body.encode()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    # ── HTTP with retries ──────────────────────────────────────────────────

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    def _post(self, path: str, payload: dict, extra_headers: Optional[dict] = None) -> dict:
        return self._request("POST", path, json_body=payload, extra_headers=extra_headers)

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", path, params=params)

    def _patch(self, path: str, payload: dict) -> dict:
        return self._request("PATCH", path, json_body=payload)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        params: Optional[dict] = None,
        extra_headers: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        last_exc: Optional[Exception] = None
        for delay in (0.0, *_RETRY_BACKOFF_SECONDS):
            if delay:
                time.sleep(delay)
            try:
                resp = requests.request(
                    method, url, json=json_body, params=params,
                    headers=self._headers(extra_headers), timeout=self.timeout,
                )
            except requests.RequestException as e:
                last_exc = e
                continue
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError:
                    return {"raw": resp.text}
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last_exc = GeniOSError(f"{resp.status_code} {resp.text[:200]}")
                continue
            raise GeniOSError(f"{resp.status_code} {resp.text[:500]}")
        raise GeniOSError(f"retries exhausted: {last_exc}")
