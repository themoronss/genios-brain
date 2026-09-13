"""Secrets at rest — agent webhook signing secrets (P6).

`agent_registry.webhook_secret` was stored in plain text. It is now sealed with the deployment's
Fernet key (`GENIOS_CRYPTO_KEY`, the key raw payloads already use) and marked `enc:v1:`. Reads
accept both forms, so rows written before this change keep working, and
`backfill_agent_webhook_secrets` seals those in place at startup — migrations here are SQL-only
and cannot encrypt.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt, encrypt
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.secret_box")
PREFIX = "enc:v1:"


def _key() -> str:
    return (get_settings().crypto_key or "").strip()


def seal(plain: str | None) -> str | None:
    """Encrypt for storage. None/empty pass through; an already-sealed value is returned as is.
    With no key configured (a dev box) the value is stored as given, with a warning."""
    if not plain or plain.startswith(PREFIX):
        return plain
    key = _key()
    if not key:
        _log.warning("GENIOS_CRYPTO_KEY not set — webhook secret stored unencrypted")
        return plain
    return PREFIX + encrypt(plain, key).decode()


def unseal(value: str | None) -> str:
    """The plain secret. A legacy plain-text row is returned as is. A sealed one that cannot be
    opened (key missing or changed) gives "" — the send then fails the agent's signature check
    rather than signing with garbage."""
    v = value or ""
    if not v.startswith(PREFIX):
        return v
    key = _key()
    if not key:
        _log.error("sealed webhook secret but GENIOS_CRYPTO_KEY is not set")
        return ""
    try:
        return decrypt(v[len(PREFIX):].encode(), key)
    except Exception:  # noqa: BLE001 — a wrong or rotated key must not crash a delivery
        _log.error("webhook secret could not be decrypted (GENIOS_CRYPTO_KEY changed?)")
        return ""


def unsealed_row(row: Any) -> dict:
    """An `agent_registry` mapping with its `webhook_secret` opened, for a channel send."""
    d = dict(row)
    d["webhook_secret"] = unseal(d.get("webhook_secret"))
    return d


def backfill_agent_webhook_secrets(engine) -> int:
    """Seal every plain-text agent webhook secret in place. Idempotent; never raises."""
    if not _key():
        return 0
    n = 0
    try:
        with engine.begin() as c:
            rows = c.execute(text(
                "select org_id, agent_id, webhook_secret from agent_registry "
                "where webhook_secret is not null and webhook_secret <> '' "
                "and webhook_secret not like 'enc:v1:%'")).fetchall()
            for r in rows:
                n += c.execute(text(
                    "update agent_registry set webhook_secret = :new "
                    "where org_id = :o and agent_id = :a and webhook_secret = :old"),
                    {"new": seal(r.webhook_secret), "o": r.org_id, "a": r.agent_id,
                     "old": r.webhook_secret}).rowcount
    except Exception:  # noqa: BLE001 — a backfill must never stop the app starting
        _log.exception("agent webhook secret backfill failed")
        return 0
    if n:
        _log.info("sealed %d plain-text agent webhook secret(s)", n)
    return n


__all__ = ["PREFIX", "backfill_agent_webhook_secrets", "seal", "unseal", "unsealed_row"]
