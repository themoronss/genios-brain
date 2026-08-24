"""Channel settings — where a tenant tells GeniOS where to speak (Settings → Channels).
v1: one Slack incoming-webhook per org. The webhook URL is tenant-entered, stored in
org_channels.config, validated on write, and NEVER echoed back in full (secret-shaped).
POST /test sends a real message immediately so 'did I paste the right URL' is a button,
not a support ticket."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
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
    return url[:30] + "…" if len(url) > 30 else url


@router.get("/api/org/{org_id}/channels")
def list_channels(org_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select channel, config, active, last_digest_date, updated_at "
            "from org_channels where org_id=:o"), {"o": org}).fetchall()
    out = []
    for r in rows:
        cfg = r.config if isinstance(r.config, dict) else json.loads(r.config or "{}")
        out.append({"channel": r.channel, "active": bool(r.active),
                    "webhook_url_masked": _mask(cfg.get("webhook_url")),
                    "last_digest_date": r.last_digest_date.isoformat() if r.last_digest_date else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None})
    return {"channels": out}


class SlackConfig(BaseModel):
    webhook_url: str
    active: bool = True


@router.put("/api/org/{org_id}/channels/slack")
def set_slack(org_id: str, body: SlackConfig, org: str = Depends(_org)) -> dict:
    _require_db()
    from genios_engine.deliver.channels.slack import valid_webhook_url
    if not valid_webhook_url(body.webhook_url):
        raise HTTPException(422, "webhook_url must start with https://hooks.slack.com/")
    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into org_channels (org_id, channel, config, active) "
            "values (:o, 'slack', cast(:cfg as jsonb), :a) "
            "on conflict (org_id, channel) do update set "
            "config=excluded.config, active=excluded.active, updated_at=now()"),
            {"o": org, "cfg": json.dumps({"webhook_url": body.webhook_url}),
             "a": body.active})
    return {"saved": True, "channel": "slack", "active": body.active}


@router.delete("/api/org/{org_id}/channels/slack")
def remove_slack(org_id: str, org: str = Depends(_org)) -> dict:
    _require_db()
    with _graph.engine.begin() as c:
        c.execute(text("delete from org_channels where org_id=:o and channel='slack'"),
                  {"o": org})
    return {"removed": True}


@router.post("/api/org/{org_id}/channels/slack/test")
def test_slack(org_id: str, org: str = Depends(_org)) -> dict:
    """Send a real test message NOW — configuration proof, not hope."""
    _require_db()
    from genios_engine.deliver.channels.base import get_channel
    with _graph.engine.connect() as c:
        row = c.execute(text(
            "select config from org_channels where org_id=:o and channel='slack' and active"),
            {"o": org}).first()
    if row is None:
        raise HTTPException(404, "no active slack channel configured")
    cfg = row.config if isinstance(row.config, dict) else json.loads(row.config or "{}")
    res = get_channel("slack").send(
        {"text": "✅ GeniOS is connected — high-priority cards will arrive here."}, cfg)
    if not res.ok:
        raise HTTPException(502, f"slack send failed: {res.detail}")
    return {"sent": True}
