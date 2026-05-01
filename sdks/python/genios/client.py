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
    def __init__(self, client: "GeniOS"):
        self._client = client

    def register(self, name: str, description: str = "") -> dict:
        return self._client._post("/v1/agent", {"agent_id": name, "name": description or name})


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
