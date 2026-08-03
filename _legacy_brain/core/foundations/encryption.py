"""Symmetric encryption for customer secrets (OAuth tokens, API keys).

Pattern: Fernet (AES-128-CBC + HMAC) with master key from `.env`.
Replaces the old `policy/connector_crypto.py` — same shape, cleaner API.

Customer secrets live in DB columns as base64 ciphertext:
    >>> encrypt("ya29.a0AfH6...") -> "gAAAAA...base64..."
    >>> decrypt("gAAAAA...") -> "ya29.a0AfH6..."

The master key (GENIOS_CRYPTO_MASTER_KEY) is the only thing in .env; rotating
it requires re-encrypting all stored secrets (handled by a separate rotation
script, not part of normal operation).
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from core.foundations.config import settings


class EncryptionError(Exception):
    """Raised when encrypt/decrypt fails (e.g., wrong key, corrupt ciphertext)."""


def _fernet() -> Fernet:
    """Build Fernet instance from master key. Fails fast on misconfig."""
    key = settings.GENIOS_CRYPTO_MASTER_KEY.encode("utf-8")
    try:
        return Fernet(key)
    except (ValueError, TypeError) as e:
        raise EncryptionError(
            "GENIOS_CRYPTO_MASTER_KEY must be a 32-byte url-safe base64 key. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'"
        ) from e


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns base64 ciphertext (safe to store in TEXT column)."""
    if not plaintext:
        raise EncryptionError("Refusing to encrypt empty string")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a string. Raises EncryptionError on tamper / wrong key."""
    if not ciphertext:
        raise EncryptionError("Refusing to decrypt empty string")
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise EncryptionError("Decryption failed — wrong key or tampered ciphertext") from e


def generate_master_key() -> str:
    """Generate a new master key. Run once during initial setup."""
    return Fernet.generate_key().decode("utf-8")
