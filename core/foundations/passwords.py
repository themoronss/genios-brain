"""Password hashing — bcrypt.

Constant-time verify. No password length cap beyond bcrypt's 72-byte
internal limit (we pre-hash with sha256 for longer inputs so the user can
still use a passphrase).
"""

from __future__ import annotations

import hashlib

import bcrypt


def _normalize(password: str) -> bytes:
    """bcrypt has a 72-byte limit; pre-hash with sha256 to lift it transparently."""
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash. Raises on empty password."""
    if not password:
        raise ValueError("password must be non-empty")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(_normalize(password), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verify. Returns False on any mismatch or malformed hash."""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(_normalize(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
