"""The agent webhook as a CHANNEL adapter — so an agent delivery is an outbox row, not an
inline POST from the card build.

`deliver/push.py` did its HTTP synchronously inside `build_cards_for_org`, which is the exact
anti-pattern the outbox module's own docstring names as its reason to exist: one slow client
endpoint degrades the card build for the whole org, and the send appears in no outbox, no retry
schedule, no dead letter, and no analytics. Routing it here gives an agent push the same
lifecycle every human delivery already has — claimed, retried on the bounded backoff ladder,
terminal with a recorded reason — and the drain's authority recheck replaces push.py's
hand-rolled pre-send projection comparison.

Two wire formats, one per event:

  * `signal.created` (`AgentWebhookChannel.send`) — UNCHANGED: HMAC-SHA256 over the exact body,
    `X-Genios-Signature: sha256=<hex>`, mirrored by `platform/auth.verify_webhook_hmac`.
  * `action.requested` (`send_action`, SCREEN_INTEL_P6 §3.1, frozen) — the body bytes are frozen at
    approval and reused on every retry; the timestamp is fresh per attempt and signed WITH the body
    (`v1 = HMAC-SHA256(secret, f"{ts}.{raw_body}")`) so a captured request cannot be replayed after
    the receiver's 300 s window; `Idempotency-Key` / `X-Genios-Delivery-Id` carry the delegation id
    so a retried send (including one after an ambiguous timeout) is deduplicated by the receiver.
    `verify_action_signature` is the receiver-side reference the client templates mirror.

Both paths pass the egress guard (`platform/egress.check_url`) immediately before the POST and
connect to the checked address; redirects are never followed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from genios_engine.deliver.channels.base import ChannelResult
from genios_engine.platform.egress import EgressRefused, check_url, pinned_request
from genios_engine.platform.logging import get_logger

_TIMEOUT_S = 4.0
#: An action receiver may do real work before it answers (the templates ack first, but a thin
#: n8n flow may not). Connect stays short: an unreachable host is a clean retry.
ACTION_TIMEOUT_S = 10.0
ACTION_CONNECT_TIMEOUT_S = 4.0
#: Receivers reject a timestamp further than this from their clock (§3.1).
SIGNATURE_TOLERANCE_S = 300
ACTION_EVENT = "action.requested"

# Outcomes of one action attempt. The outbox owns the policy; the channel only classifies.
DELIVERED = "delivered"              # 2xx — the receiver has it
RETRYABLE = "retryable"              # never reached / 408 / 425 / 429 / 5xx — send again, same bytes
TIMEOUT_UNKNOWN = "timeout_unknown"  # sent, no answer — MAY have executed; retry with the same key
PERMANENT = "permanent"              # 3xx / other 4xx / refused URL / no secret — do not retry

_log = get_logger("genios.deliver.channels.agent")


@dataclass(frozen=True)
class AgentSendResult(ChannelResult):
    """A ChannelResult that is also truthy on success. The drain reads `.ok`; older callers of
    this channel read it as a bool — both keep working."""

    def __bool__(self) -> bool:
        return self.ok


@dataclass(frozen=True)
class ActionOutcome:
    status: str
    delivery_id: str
    http_status: int | None = None
    detail: str = ""                    # never includes the secret or the body
    timestamp: int | None = None        # the X-Genios-Timestamp this attempt carried
    retry_after_s: int | None = None    # the receiver's Retry-After, when it sent one

    @property
    def ok(self) -> bool:
        return self.status == DELIVERED

    @property
    def retry(self) -> bool:
        return self.status in (RETRYABLE, TIMEOUT_UNKNOWN)


def sign_v1(secret: str, timestamp: int | str, raw_body: bytes) -> str:
    """`v1=<hex HMAC-SHA256(secret, "{ts}.{raw_body}")>` — the X-Genios-Signature value."""
    msg = f"{int(timestamp)}.".encode() + bytes(raw_body)
    return "v1=" + hmac.new(str(secret).encode(), msg, hashlib.sha256).hexdigest()


def verify_action_signature(raw_body: bytes, *, timestamp: str | int | None,
                            signature: str | None, secret: str,
                            tolerance_s: int = SIGNATURE_TOLERANCE_S,
                            now: float | None = None) -> bool:
    """Receiver-side reference for §3.1 (the templates mirror it): the timestamp is within
    ±`tolerance_s` of now, and one `v1=` entry of the header equals the HMAC of `{ts}.{body}`.
    Constant-time. Several comma/space separated entries are accepted (secret rotation)."""
    if not (signature and secret) or timestamp is None:
        return False
    try:
        ts = int(str(timestamp).strip())
    except (TypeError, ValueError):
        return False
    if abs(int(time.time() if now is None else now) - ts) > tolerance_s:
        return False
    expected = sign_v1(secret, ts, raw_body)[3:]
    entries = [e.strip() for e in signature.replace(",", " ").split() if e.strip()]
    return any(e.startswith("v1=") and hmac.compare_digest(e[3:], expected) for e in entries)


def action_headers(*, secret: str, agent_id: str, delivery_id: str, timestamp: int,
                   raw_body: bytes) -> dict:
    """The §3.1 header set for one attempt."""
    return {
        "Content-Type": "application/json",
        "X-Genios-Event": ACTION_EVENT,
        "X-Genios-Agent-Id": agent_id,
        "X-Genios-Delivery-Id": delivery_id,
        "Idempotency-Key": delivery_id,
        "X-Genios-Timestamp": str(int(timestamp)),
        "X-Genios-Signature": sign_v1(secret, timestamp, raw_body),
    }


def _retry_after(resp) -> int | None:
    try:
        v = int(str(resp.headers.get("retry-after") or "").strip())
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def _classify_status(code: int) -> str:
    if 200 <= code < 300:
        return DELIVERED
    if code in (408, 425, 429) or code >= 500:
        return RETRYABLE
    return PERMANENT                     # 1xx/3xx (redirects are refused) and every other 4xx


def _post(url: str, *, body: bytes, headers: dict, timeout, client=None):
    """POST to the egress-checked URL, pinned to the checked address, never following redirects."""
    import httpx
    target = check_url(url)
    pinned_url, pin_headers, extensions = pinned_request(target)
    request_headers = {**headers, **pin_headers}
    if client is not None:
        return client.request("POST", pinned_url, content=body, headers=request_headers,
                              extensions=extensions, timeout=timeout, follow_redirects=False)
    with httpx.Client(follow_redirects=False) as c:
        return c.request("POST", pinned_url, content=body, headers=request_headers,
                         extensions=extensions, timeout=timeout)


def send_action(body: bytes, cfg: dict, *, delegation_id: str, now: float | None = None,
                client=None) -> ActionOutcome:
    """POST one frozen `action.requested` body to one agent (cfg = its agent_registry row:
    `agent_id`, `webhook_url`, `webhook_secret`). One attempt; never raises. The caller retries
    with the SAME `body` and `delegation_id`; each attempt gets a fresh timestamp + signature."""
    cfg = cfg or {}
    delivery_id = str(delegation_id or "").strip()
    if not delivery_id:
        return ActionOutcome(PERMANENT, "", detail="delegation_id missing")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ActionOutcome(PERMANENT, delivery_id, detail="body must be the frozen request bytes")
    secret = str(cfg.get("webhook_secret") or "")
    if not secret:
        return ActionOutcome(PERMANENT, delivery_id, detail="agent has no webhook signing secret")
    url = cfg.get("webhook_url")
    ts = int(time.time() if now is None else now)
    headers = action_headers(secret=secret, agent_id=str(cfg.get("agent_id") or ""),
                             delivery_id=delivery_id, timestamp=ts, raw_body=bytes(body))
    try:
        import httpx
    except Exception:      # pragma: no cover — httpx ships transitively
        return ActionOutcome(RETRYABLE, delivery_id, detail="httpx unavailable", timestamp=ts)
    timeout = httpx.Timeout(ACTION_TIMEOUT_S, connect=ACTION_CONNECT_TIMEOUT_S)
    try:
        resp = _post(url, body=bytes(body), headers=headers, timeout=timeout, client=client)
    except EgressRefused as e:
        _log.warning("action delivery refused by egress guard delivery=%s code=%s",
                     delivery_id, e.code)
        return ActionOutcome(PERMANENT, delivery_id, detail=f"egress_refused:{e.code}",
                             timestamp=ts)
    except (httpx.ConnectTimeout, httpx.ConnectError, httpx.PoolTimeout) as e:
        # The request never reached the receiver: a clean retry.
        return ActionOutcome(RETRYABLE, delivery_id, detail=f"connect failed: {type(e).__name__}",
                             timestamp=ts)
    except (httpx.UnsupportedProtocol, httpx.InvalidURL) as e:
        return ActionOutcome(PERMANENT, delivery_id, detail=f"invalid url: {type(e).__name__}",
                             timestamp=ts)
    except Exception as e:      # noqa: BLE001 — read/write timeout, dropped connection, …
        # Bytes may have reached the receiver and been executed. Retrying is safe ONLY because the
        # receiver dedupes on Delivery-Id; the outcome says so, so the outbox can tell it apart.
        return ActionOutcome(TIMEOUT_UNKNOWN, delivery_id,
                             detail=f"no response: {type(e).__name__}", timestamp=ts)
    status = _classify_status(resp.status_code)
    detail = "" if status == DELIVERED else f"http {resp.status_code}"
    return ActionOutcome(status, delivery_id, http_status=resp.status_code, detail=detail,
                         timestamp=ts, retry_after_s=_retry_after(resp))


class AgentWebhookChannel:
    """POST one payload to one agent's webhook. cfg = one agent_registry row."""

    name = "agent_push"

    def send(self, payload: dict, cfg: dict) -> AgentSendResult:
        try:
            import httpx  # noqa: F401
        except Exception:      # pragma: no cover — httpx ships transitively
            _log.warning("httpx unavailable; agent delivery skipped")
            return AgentSendResult(False, "httpx unavailable")
        url = (cfg or {}).get("webhook_url")
        if not url:
            return AgentSendResult(False, "agent has no webhook_url")
        body = json.dumps(payload, default=str).encode()
        secret = str((cfg or {}).get("webhook_secret") or "")
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        try:
            resp = _post(url, body=body, timeout=_TIMEOUT_S, headers={
                "Content-Type": "application/json",
                "X-Genios-Signature": f"sha256={sig}",
                "X-Genios-Event": str(payload.get("type") or "signal.created"),
                "X-Genios-Agent-Id": str((cfg or {}).get("agent_id") or ""),
            })
            ok = 200 <= resp.status_code < 300
            return AgentSendResult(ok, "" if ok else f"http {resp.status_code}")
        except EgressRefused as e:
            _log.warning("agent delivery refused by egress guard code=%s", e.code)
            return AgentSendResult(False, f"egress_refused:{e.code}")
        except Exception as e:      # noqa: BLE001 — a failed send is a retry, never a crash
            _log.warning("agent delivery failed: %s", type(e).__name__)
            return AgentSendResult(False, f"send failed: {type(e).__name__}")


__all__ = ["ACTION_EVENT", "ActionOutcome", "AgentSendResult", "AgentWebhookChannel", "DELIVERED",
           "PERMANENT", "RETRYABLE", "SIGNATURE_TOLERANCE_S", "TIMEOUT_UNKNOWN", "action_headers",
           "send_action", "sign_v1", "verify_action_signature"]
