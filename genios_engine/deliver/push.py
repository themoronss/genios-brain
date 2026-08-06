from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# Outbound delivery to agents (GeniOS -> executor). Two flavours, one transport:
#   • push_card_to_agents   — proactive "here's a new signal" (fired by L5 when a card is emitted).
# Body == the /v1/signals poll projection, so push and poll are interchangeable. HMAC-SHA256 signed
# (X-Genios-Signature). Proactive delivery is executor-agnostic and carries no execution request.
# in the org that registered a webhook (Hermes or the client's own tool) — GeniOS never executes
# itself. Best-effort: a slow/dead webhook is swallowed-and-logged, never blocks the caller. Uses only
# `store.engine`, so any store (CardStore or GraphStore) works.

_log = get_logger("genios.deliver.push")
_TIMEOUT_S = 4.0


def _active_agent_webhooks(conn, org_id: str) -> list[dict]:
    rows = conn.execute(text(
        "select agent_id, webhook_url, webhook_secret from agent_registry "
        "where org_id=:o and coalesce(status,'active')='active' "
        "and 'signals.read'=any(coalesce(allowed_actions,array[]::text[])) "
        "and webhook_url is not null and webhook_url <> ''"), {"o": org_id}).mappings().all()
    return [dict(r) for r in rows]


def _card_projection(conn, org_id: str, card_id: str) -> dict | None:
    """Exactly the poll_signals shape (deliver/agent_api.py) — push == poll."""
    r = conn.execute(text(
        "select k.signal_id, k.card_id, k.urgency_band, k.headline, k.situation, "
        + AUTHORITATIVE_SCORE_SQL + " as score, k.score_block, k.state, k.created_at "
        "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id "
        + AUTHORITATIVE_SIGNAL_JOINS +
        " where k.org_id=:o and k.card_id=:c and s.status='open' "
        "and k.state in ('queued','surfaced','snoozed','delivered') "
        "and k.expires_at > :authority_time and " + AUTHORITATIVE_SIGNAL_PREDICATE),
        {"o": org_id, "c": card_id,
         "authority_time": datetime.now(timezone.utc)}).mappings().first()
    return dict(r) if r else None


def authoritative_card_projection(store, org_id: str, card_id: str) -> dict | None:
    with store.engine.connect() as c:
        return _card_projection(c, org_id, card_id)


def _log_event(store, card_id: str, org_id: str, agent_id: str, kind: str,
               status_code, ok: bool) -> None:
    """Observability row per delivery attempt — via store.engine so it's store-agnostic."""
    try:
        with store.engine.begin() as c:
            c.execute(text(
                "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail) "
                "values (:i,:c,:o,:k,'webhook',:a,cast(:d as jsonb))"),
                {"i": new_id("cev"), "c": card_id, "o": org_id, "k": kind, "a": agent_id,
                 "d": json.dumps({"agent_id": agent_id, "status_code": status_code, "ok": ok})})
    except Exception:                                          # noqa: BLE001
        _log.exception("push event log failed org=%s card=%s", org_id, card_id)


def _deliver(store, org_id: str, event_type: str, payload: dict, card_id: str, log_kind: str) -> int:
    """Sign + POST `payload` to every active webhook-agent in the org. Returns 2xx-ack count."""
    try:
        import httpx
    except Exception:                                          # pragma: no cover - httpx ships transitively
        _log.warning("httpx unavailable; skipping agent delivery org=%s", org_id)
        return 0
    with store.engine.connect() as c:
        agents = _active_agent_webhooks(c, org_id)
    if not agents:
        return 0
    body = json.dumps({"type": event_type, "org_id": org_id, **payload}, default=str).encode()
    delivered = 0
    for a in agents:
        # Recheck immediately before every irreversible network dispatch. A graph/config/pack/
        # expiry transition during rendering or fan-out invalidates the remaining deliveries.
        with store.engine.connect() as c:
            live = _card_projection(c, org_id, card_id)
        projected = payload.get("signal") if isinstance(payload, dict) else None
        if (live is None or not isinstance(projected, dict)
                or live.get("signal_id") != projected.get("signal_id")):
            break
        secret = a.get("webhook_secret") or ""
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Genios-Signature": f"sha256={sig}",   # mirror platform/auth.verify_webhook_hmac
            "X-Genios-Event": event_type,
            "X-Genios-Agent-Id": a["agent_id"],
        }
        status_code = None
        ok = False
        try:
            resp = httpx.post(a["webhook_url"], content=body, headers=headers, timeout=_TIMEOUT_S)
            status_code = resp.status_code
            ok = 200 <= status_code < 300
            if ok:
                delivered += 1
        except Exception as e:                                # noqa: BLE001 - never break the caller
            _log.warning("agent delivery failed org=%s agent=%s url=%s: %s",
                         org_id, a["agent_id"], a["webhook_url"], e)
        if card_id:
            _log_event(store, card_id, org_id, a["agent_id"], log_kind, status_code, ok)
    return delivered


def push_card_to_agents(store, org_id: str, card_id: str) -> int:
    """Proactive: fan a freshly-emitted card out to every active agent with a webhook. Org-wide,
    independent of human seat routing. Returns the count that acknowledged (2xx). Never raises."""
    proj = authoritative_card_projection(store, org_id, card_id)
    if proj is None:
        return 0
    return _deliver(store, org_id, "signal.created", {"signal": proj}, card_id, "card.pushed")


def push_action_to_agents(store, org_id: str, card_id: str,
                          draft: str | None = None, instruction: str | None = None) -> int:
    """External actions require a single-executor transactional approval protocol.

    Kept as an explicit fail-closed shim for older callers; no network request is made.
    """
    del store, org_id, card_id, draft, instruction
    raise RuntimeError("external action push is disabled")
