"""
Connector credentials CRUD — per-agent or workspace-level data sources.

Phase 6 (Inkbox integration): each AI agent has its own mailbox + phone
+ SMS line. This module manages the binding between an agent and its
connector secrets. Workspace-level rows (agent_uuid IS NULL) preserve
existing Gmail/HubSpot OAuth flows.

Brain framing: this is the bridge between the agent's body (Inkbox: real
email server, real phone) and the agent's brain (Genios: graph, scope,
intelligence). When email arrives at the body, the body POSTs to Genios
via the webhook URL configured against this connector row.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets as _secrets
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.policy.connector_crypto import decrypt as _decrypt, encrypt as _encrypt

# Sensitive metadata keys that must be encrypted at rest.
_SENSITIVE_KEYS = ("api_key", "password", "oauth_token", "refresh_token", "imap_password")


# Canonical source types. Genios is generic — any provider (Inkbox,
# Postmark, custom email server, Twilio, etc.) can connect by setting
# `metadata.provider` alongside the canonical type. Existing legacy
# values (e.g. 'inkbox_email') stay accepted for back-compat.
KNOWN_SOURCES = frozenset([
    "email", "phone", "sms",
    "gmail", "hubspot", "calendar", "slack", "drive", "docs", "sheets",
    "manual",
    # Legacy / vendor-prefixed values — accepted but no longer used by new code.
    "inkbox_email", "inkbox_phone", "inkbox_sms",
    "custom_email", "custom_phone", "custom_sms",
])


def _hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def mint_secret() -> tuple[str, str]:
    """Return (raw_secret, sha256_hash). Raw shown once to caller."""
    raw = f"whk_{_secrets.token_urlsafe(32)}"
    return raw, _hash_secret(raw)


def verify_signature(payload_bytes: bytes, signature_hex: str, secret_hash_in_db: str, raw_secret: Optional[str] = None) -> bool:
    """
    HMAC-SHA256 verification.

    The DB only stores the SHA-256 of the secret (defence in depth).
    Verifying an incoming signature requires the raw secret — passed in
    via lookup mechanism (e.g. cached at connector creation time, or
    re-issued through a key-rotation API).

    For Phase 6 we use a simpler model: secret is stored as `secret_hash`
    in the DB, and we ALSO keep the raw secret in `metadata.signing_secret`
    so the receiver can re-compute. (DB row remains org-isolated via RLS,
    secret is not loggable, and rotation regenerates both fields.)
    """
    if not raw_secret or not signature_hex:
        return False
    expected = hmac.new(raw_secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex.lower().strip())


def list_for_agent(db: Session, org_id: str, agent_uuid: str):
    return db.execute(
        text("""
            SELECT id::text, source, metadata, is_active, created_at, last_event_at
            FROM connector_credentials
            WHERE org_id = :o AND agent_uuid = :a
            ORDER BY created_at DESC
        """),
        {"o": org_id, "a": agent_uuid},
    ).fetchall()


def find_by_agent_source(db: Session, org_id: str, agent_uuid: str, source: str):
    return db.execute(
        text("""
            SELECT id::text, metadata, is_active
            FROM connector_credentials
            WHERE org_id = :o AND agent_uuid = :a AND source = :s AND is_active = TRUE
            LIMIT 1
        """),
        {"o": org_id, "a": agent_uuid, "s": source},
    ).fetchone()


def find_for_ingest(db: Session, agent_uuid: str, source: str):
    """Look up the active connector row for an incoming webhook.
    Returns the row including the signing secret + hash."""
    return db.execute(
        text("""
            SELECT id::text, org_id::text, metadata, is_active
            FROM connector_credentials
            WHERE agent_uuid = :a AND source = :s AND is_active = TRUE
            LIMIT 1
        """),
        {"a": agent_uuid, "s": source},
    ).fetchone()


def upsert(
    db: Session,
    org_id: str,
    agent_uuid: str,
    source: str,
    metadata: dict,
) -> tuple[str, str]:
    """
    Create or rotate a connector for (agent, source). Returns
    (connector_id, raw_signing_secret). Raw secret is shown once.

    Sensitive metadata fields (api_key, password, etc.) are encrypted at
    rest via Fernet. They round-trip transparently through `decrypt_metadata`.
    """
    raw_secret, sec_hash = mint_secret()
    md = dict(metadata or {})
    md["signing_secret"] = raw_secret  # stored alongside hash for HMAC verify
    # Encrypt sensitive fields before persistence
    for k in _SENSITIVE_KEYS:
        if k in md and md[k]:
            md[k] = _encrypt(str(md[k]))
    # Deactivate any existing row for the same (agent, source)
    db.execute(
        text("""
            UPDATE connector_credentials
            SET is_active = FALSE
            WHERE org_id = :o AND agent_uuid = :a AND source = :s AND is_active = TRUE
        """),
        {"o": org_id, "a": agent_uuid, "s": source},
    )
    cid = db.execute(
        text("""
            INSERT INTO connector_credentials (org_id, agent_uuid, source, metadata, secret_hash, is_active)
            VALUES (:o, :a, :s, CAST(:m AS jsonb), :h, TRUE)
            RETURNING id::text
        """),
        {
            "o": org_id, "a": agent_uuid, "s": source,
            "m": __import__("json").dumps(md),
            "h": sec_hash,
        },
    ).scalar()
    return cid, raw_secret


def deactivate(db: Session, org_id: str, agent_uuid: str, connector_id: str) -> bool:
    res = db.execute(
        text("""
            UPDATE connector_credentials
            SET is_active = FALSE
            WHERE id = :id AND org_id = :o AND agent_uuid = :a AND is_active = TRUE
            RETURNING 1
        """),
        {"id": connector_id, "o": org_id, "a": agent_uuid},
    ).fetchone()
    return res is not None


def touch_last_event(db: Session, connector_id: str) -> None:
    db.execute(
        text("UPDATE connector_credentials SET last_event_at = NOW() WHERE id = :id"),
        {"id": connector_id},
    )


def decrypt_metadata(meta: dict) -> dict:
    """Reverse of upsert's encryption — pulls plaintext back out.
    Used by Celery sync tasks before calling adapter.fetch."""
    out = dict(meta or {})
    for k in _SENSITIVE_KEYS:
        if k in out and out[k]:
            plain = _decrypt(str(out[k]))
            out[k] = plain or ""
    return out


def get_signing_secret(db: Session, agent_uuid: str, source: str) -> Optional[str]:
    """Pull the raw signing secret from metadata for HMAC verify on webhook."""
    row = db.execute(
        text("""
            SELECT metadata
            FROM connector_credentials
            WHERE agent_uuid = :a AND source = :s AND is_active = TRUE
            LIMIT 1
        """),
        {"a": agent_uuid, "s": source},
    ).fetchone()
    if not row or not row[0]:
        return None
    md = row[0] if isinstance(row[0], dict) else __import__("json").loads(row[0])
    return md.get("signing_secret")
