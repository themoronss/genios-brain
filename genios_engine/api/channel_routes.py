"""Channel settings — where a tenant tells GeniOS where to speak (Settings → Channels).

Slack keeps its backwards-compatible convenience routes. The generic route registers Teams,
signed customer webhooks and durable pull surfaces. Credentials and full endpoint URLs are
never echoed; ``POST /test`` exercises the same adapter the outbox uses.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt, encrypt
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _require_db():
    if _graph is None:
        raise HTTPException(400, "graph store not configured (needs DATABASE_URL)")


def _mask(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(str(url))
    # A webhook path/query is commonly the credential. Return only the destination host; even a
    # short URL must never expose the secret-bearing suffix merely because it fits on one line.
    return f"{parsed.scheme}://{parsed.hostname}/…" if parsed.scheme and parsed.hostname else "configured"


def _safe_config(config: dict) -> dict:
    """Return operational metadata without returning credentials or full endpoints."""
    out = {}
    for key, value in config.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("secret", "token", "password", "webhook_url")):
            out[f"{key}_configured"] = bool(value)
        elif isinstance(value, (bool, int, float)) or value is None:
            out[key] = value
        elif key in {"mode", "purpose"}:
            out[key] = str(value)[:80]
    return out


def _routing_config(config: dict) -> dict:
    return {key: value for key, value in config.items()
            if key in {"priority", "push_enabled", "digest_enabled", "mode", "purpose"}}


def _seal_config(config: dict) -> bytes:
    key = get_settings().crypto_key
    if not key:
        raise HTTPException(503, "GENIOS_CRYPTO_KEY is required to store channel credentials")
    return encrypt(json.dumps(config, separators=(",", ":"), sort_keys=True), key)


def _row_config(row) -> dict:
    encrypted = getattr(row, "config_encrypted", None)
    if encrypted:
        try:
            raw = bytes(encrypted) if not isinstance(encrypted, bytes) else encrypted
            return json.loads(decrypt(raw, get_settings().crypto_key))
        except Exception as exc:  # noqa: BLE001 - expose no ciphertext or credential detail
            raise HTTPException(500, "channel credentials cannot be decrypted") from exc
    legacy = getattr(row, "config", None)
    return legacy if isinstance(legacy, dict) else json.loads(legacy or "{}")


@router.get("/api/org/{org_id}/channels")
def list_channels(org_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select channel, config, config_encrypted, active, last_digest_date, updated_at "
            "from org_channels where org_id=:o"), {"o": org}).fetchall()
    out = []
    for r in rows:
        cfg = _row_config(r)
        out.append({"channel": r.channel, "active": bool(r.active),
                    "webhook_url_masked": _mask(cfg.get("webhook_url")),
                    "config_summary": _safe_config(cfg),
                    "last_digest_date": r.last_digest_date.isoformat() if r.last_digest_date else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None})
    return {"channels": out}


class SlackConfig(BaseModel):
    webhook_url: str
    active: bool = True


@router.put("/api/org/{org_id}/channels/slack")
def set_slack(org_id: str, body: SlackConfig,
              ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    from genios_engine.deliver.channels.slack import valid_webhook_url
    if not valid_webhook_url(body.webhook_url):
        raise HTTPException(422, "webhook_url must start with https://hooks.slack.com/")
    with _graph.engine.begin() as c:
        c.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        c.execute(text(
            "insert into org_channels (org_id, channel, config, config_encrypted, active) "
            "values (:o, 'slack', '{}', :sealed, :a) "
            "on conflict (org_id, channel) do update set "
            "config=excluded.config,config_encrypted=excluded.config_encrypted, "
            "active=excluded.active, updated_at=now()"),
            {"o": ctx.org_id,
             "sealed": _seal_config({"webhook_url": body.webhook_url}),
             "a": body.active})
    return {"saved": True, "channel": "slack", "active": body.active}


@router.delete("/api/org/{org_id}/channels/slack")
def remove_slack(org_id: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    with _graph.engine.begin() as c:
        c.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        c.execute(text("delete from org_channels where org_id=:o and channel='slack'"),
                  {"o": ctx.org_id})
    return {"removed": True}


@router.post("/api/org/{org_id}/channels/slack/test")
def test_slack(org_id: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Send a real test message NOW — configuration proof, not hope."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    from genios_engine.deliver.channels.base import get_channel
    with _graph.engine.connect() as c:
        row = c.execute(text(
            "select config,config_encrypted from org_channels "
            "where org_id=:o and channel='slack' and active"),
            {"o": ctx.org_id}).first()
    if row is None:
        raise HTTPException(404, "no active slack channel configured")
    cfg = _row_config(row)
    res = get_channel("slack").send(
        {"text": "✅ GeniOS is connected — high-priority cards will arrive here."}, cfg)
    if not res.ok:
        raise HTTPException(502, f"slack send failed: {res.detail}")
    return {"sent": True}


class GenericChannelConfig(BaseModel):
    """Configuration for Atlas adapters other than the dedicated Slack convenience route."""

    active: bool = True
    config: dict = Field(default_factory=dict)


def _validate_channel_config(channel: str, config: dict) -> None:
    from genios_engine.deliver.channels.base import get_channel
    if get_channel(channel) is None:
        raise HTTPException(422, "unsupported channel")
    if channel == "agent":
        raise HTTPException(422, "agent delivery is configured per agent via /v1/agents")
    if channel == "teams":
        from genios_engine.deliver.channels.teams import valid_teams_webhook_url
        if not valid_teams_webhook_url(config.get("webhook_url")):
            raise HTTPException(422, "invalid or missing Teams webhook_url")
    elif channel == "webhook":
        from genios_engine.deliver.channels.webhook import valid_endpoint_url
        if not valid_endpoint_url(config.get("webhook_url")):
            raise HTTPException(422, "webhook_url must be a public HTTPS URL")
        if len(str(config.get("webhook_secret") or "")) < 16:
            raise HTTPException(422, "webhook_secret must be at least 16 characters")
    elif config:
        # Pull surfaces need no secret-shaped configuration. Refusing extras prevents a client
        # from believing settings such as an APNs token are being used when no push adapter exists.
        raise HTTPException(422, f"{channel} is a durable pull surface and takes no config")


@router.put("/api/org/{org_id}/channels/{channel}")
def set_channel(org_id: str, channel: str, body: GenericChannelConfig,
                ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Register Teams, signed webhooks, or authenticated pull surfaces."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    if channel == "slack":
        raise HTTPException(422, "use the dedicated /channels/slack endpoint")
    _validate_channel_config(channel, body.config)
    with _graph.engine.begin() as conn:
        conn.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        conn.execute(text(
            "insert into org_channels (org_id, channel, config, config_encrypted, active) "
            "values (:o,:ch,cast(:cfg as jsonb),:sealed,:active) "
            "on conflict (org_id, channel) do update set config=excluded.config, "
            "config_encrypted=excluded.config_encrypted,active=excluded.active, updated_at=now()"),
            {"o": ctx.org_id, "ch": channel,
             "cfg": json.dumps(_routing_config(body.config)),
             "sealed": _seal_config(body.config) if body.config else None,
             "active": body.active})
    return {"saved": True, "channel": channel, "active": body.active,
            "config_summary": _safe_config(body.config)}


@router.delete("/api/org/{org_id}/channels/{channel}")
def remove_channel(org_id: str, channel: str,
                   ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    with _graph.engine.begin() as conn:
        conn.execute(text("select id from orgs where id=:o for update"), {"o": ctx.org_id})
        result = conn.execute(text(
            "delete from org_channels where org_id=:o and channel=:ch"),
            {"o": ctx.org_id, "ch": channel})
    return {"removed": bool(result.rowcount), "channel": channel}


@router.post("/api/org/{org_id}/channels/{channel}/test")
def test_channel(org_id: str, channel: str,
                 ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Exercise the real registered adapter; pull surfaces prove their durable seam locally."""
    _require_db()
    if org_id != ctx.org_id:
        raise HTTPException(403, "org mismatch")
    from genios_engine.deliver.channels.base import get_channel
    adapter = get_channel(channel)
    if adapter is None:
        raise HTTPException(422, "unsupported channel")
    with _graph.engine.connect() as conn:
        row = conn.execute(text(
            "select config,config_encrypted from org_channels "
            "where org_id=:o and channel=:ch and active"),
            {"o": ctx.org_id, "ch": channel}).first()
    if row is None:
        raise HTTPException(404, "no active channel configured")
    cfg = _row_config(row)
    result = adapter.send({"kind": "channel_test", "text": "GeniOS is connected."}, cfg)
    if not result.ok:
        raise HTTPException(502, f"{channel} send failed: {result.detail}")
    return {"sent": True, "channel": channel}
