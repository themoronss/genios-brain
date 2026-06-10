"""Encrypted-at-rest customer credential storage.

Wraps core.foundations.encryption for the memory layer's specific needs.
Customer secrets (OAuth tokens, API keys) NEVER appear in plaintext outside this module.

Usage:
    handle = put_secret(session, org_id, conn_id, "oauth_refresh", "ya29.xxx")
    plaintext = get_secret(session, handle)         # decrypt
    rotate_secret(session, handle, "ya29.new")      # re-encrypt new value
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.encryption import decrypt, encrypt
from core.memory.store import SecretRef

SecretType = Literal[
    "oauth_access",
    "oauth_refresh",
    "api_key",
    "service_account",
    "basic",
    "jwt",
    "mtls_cert",
]


def put_secret(
    session: Session,
    *,
    org_id: str,
    connection_id: str,
    secret_type: SecretType,
    plaintext: str,
    expires_at: datetime | None = None,
    actor_id: str = "system",
) -> str:
    """Encrypt and persist a customer secret. Returns the secret_ref id."""
    ciphertext = encrypt(plaintext)
    row = SecretRef(
        connection_id=connection_id,
        org_id=org_id,
        secret_type=secret_type,
        encrypted_value=ciphertext,
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()  # populate row.id

    audit.record(
        org_id=org_id,
        actor_type="system",
        actor_id=actor_id,
        action="secret_accessed",
        target_type="secret_ref",
        target_id=row.id,
        metadata={"op": "put", "secret_type": secret_type, "connection_id": connection_id},
    )
    return row.id


def get_secret(session: Session, secret_ref_id: str, *, actor_id: str = "system") -> str:
    """Fetch and decrypt a customer secret. Audit logged."""
    row = session.get(SecretRef, secret_ref_id)
    if row is None:
        raise KeyError(f"secret_ref {secret_ref_id} not found")

    audit.record(
        org_id=row.org_id,
        actor_type="system",
        actor_id=actor_id,
        action="secret_accessed",
        target_type="secret_ref",
        target_id=row.id,
        metadata={"op": "get", "secret_type": row.secret_type},
    )
    return decrypt(row.encrypted_value)


def rotate_secret(
    session: Session,
    secret_ref_id: str,
    new_plaintext: str,
    *,
    new_expires_at: datetime | None = None,
    actor_id: str = "system",
) -> None:
    """Re-encrypt with new value. Used by OAuth refresh + manual rotation."""
    row = session.get(SecretRef, secret_ref_id)
    if row is None:
        raise KeyError(f"secret_ref {secret_ref_id} not found")
    row.encrypted_value = encrypt(new_plaintext)
    row.expires_at = new_expires_at
    row.rotated_at = datetime.now(UTC)

    audit.record(
        org_id=row.org_id,
        actor_type="system",
        actor_id=actor_id,
        action="secret_accessed",
        target_type="secret_ref",
        target_id=row.id,
        metadata={"op": "rotate", "secret_type": row.secret_type},
    )


def delete_secret(session: Session, secret_ref_id: str, *, actor_id: str = "system") -> None:
    """Hard-delete a secret. Used on disconnect / revoke."""
    row = session.get(SecretRef, secret_ref_id)
    if row is None:
        return

    audit.record(
        org_id=row.org_id,
        actor_type="system",
        actor_id=actor_id,
        action="secret_accessed",
        target_type="secret_ref",
        target_id=row.id,
        metadata={"op": "delete", "secret_type": row.secret_type},
    )
    session.delete(row)
