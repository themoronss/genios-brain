"""
Fernet symmetric encryption for connector credentials (API keys, tokens).

Customer-provided secrets (Inkbox API key, IMAP password, etc.) get
encrypted before persistence in `connector_credentials.metadata`. The DB
never holds plaintext credentials.

Key source: env var `GENIOS_CONNECTOR_KEY` (44-char Fernet key — generate
with `Fernet.generate_key()`). Key rotation requires re-encrypting all
existing rows; not implemented here, deferred until first compliance ask.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "fnc:"  # marker for app-layer encrypted blobs


def _fernet() -> Optional[Fernet]:
    key = os.environ.get("GENIOS_CONNECTOR_KEY")
    if not key:
        logger.warning(
            "GENIOS_CONNECTOR_KEY not set — connector secrets stored in plaintext. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        logger.error(f"GENIOS_CONNECTOR_KEY invalid (must be 44-char Fernet key): {e}")
        return None


def encrypt(plaintext: str) -> str:
    """Encrypt a secret. Returns 'fnc:<token>' or raw plaintext if no key set
    (so dev environments still work — production MUST set the key)."""
    if not plaintext:
        return ""
    f = _fernet()
    if f is None:
        return plaintext  # dev fallback
    return _ENCRYPTED_PREFIX + f.encrypt(plaintext.encode()).decode()


def decrypt(blob: Optional[str]) -> Optional[str]:
    """Decrypt a stored value. Handles legacy plaintext rows + encrypted rows."""
    if not blob:
        return None
    if not blob.startswith(_ENCRYPTED_PREFIX):
        return blob  # legacy plaintext — return as-is
    f = _fernet()
    if f is None:
        logger.error("encrypted credential found but GENIOS_CONNECTOR_KEY not set")
        return None
    try:
        return f.decrypt(blob[len(_ENCRYPTED_PREFIX):].encode()).decode()
    except InvalidToken:
        logger.error("connector credential decrypt failed (key rotated?)")
        return None
