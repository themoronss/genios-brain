from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache
def _fernet(key: str) -> Fernet:
    return Fernet(key.encode())


def encrypt(plaintext: str, key: str) -> bytes:
    """Encrypt raw payload content at rest. key = GENIOS_CRYPTO_KEY (Fernet)."""
    return _fernet(key).encrypt(plaintext.encode())


def decrypt(token: bytes, key: str) -> str:
    return _fernet(key).decrypt(token).decode()


def generate_key() -> str:
    """One-off helper to mint a GENIOS_CRYPTO_KEY."""
    return Fernet.generate_key().decode()
